"""Motor de reglas de dominio: aplicabilidad, ruleset firmado y tabla CIDE."""

import json
from pathlib import Path

import pytest

from domain.models.claim import MatrixCell
from domain.models.rule_evaluation import RuleEvaluation
from domain.rules.artifact_validation import (
    evidence_pool_from_publications,
    validate_ruleset,
)
from domain.rules.cide_matrix import MatrixException, decide_from_daa_matrix
from domain.rules.ruleset import LoadedRule, RulesetError, evaluate_ruleset

# --------------------------------------------------------------------------
# Applicability guards are evidence-bound and never infer missing prerequisites.
# --------------------------------------------------------------------------


def test_more_than_two_vehicles_is_not_applicable() -> None:
    from domain.rules.applicability import ApplicabilityFacts, assess_applicability

    result = assess_applicability(ApplicabilityFacts(3, True), evidence_ids=("manual:page:56",))

    assert result.status == "not_applicable"
    assert result.evidence_ids == ("manual:page:56",)


def test_unknown_prerequisite_stays_undetermined() -> None:
    from domain.rules.applicability import ApplicabilityFacts, assess_applicability

    result = assess_applicability(ApplicabilityFacts(None, None), evidence_ids=("manual:page:56",))

    assert result.status == "undetermined"
    assert result.missing_information == (
        "Confirmar cuántos vehículos intervinieron.",
        "Confirmar si existió colisión directa entre los dos vehículos.",
    )


def test_two_vehicles_with_direct_collision_is_applicable_at_the_gate() -> None:
    from domain.rules.applicability import ApplicabilityFacts, assess_applicability

    result = assess_applicability(ApplicabilityFacts(2, True), evidence_ids=("manual:page:56",))

    assert result.status == "applicable"


# --------------------------------------------------------------------------
# The ruleset evaluator runs the reviewed artifact, not hand-written logic.
#
# Conditions live in the signed ruleset so a human reviewer can read what the
# system will decide. The evaluator only executes a tiny closed predicate
# language over the facts extracted from the claim, and it always reports one
# evaluation per rule so the interface can show what ran and what could not.
# --------------------------------------------------------------------------


_EV = ("sha256:" + "b" * 64 + ":page:56",)


def _rule(rule_id: str, applies_when: dict[str, object] | None, **kw: object) -> LoadedRule:
    return LoadedRule(
        rule_id=rule_id,
        kind=str(kw.get("kind", "applicability")),
        description=str(kw.get("description", "Regla de prueba.")),
        prerequisites=tuple(kw.get("prerequisites", ())),  # type: ignore[arg-type]
        outcome=str(kw.get("outcome", "consecuencia")),
        evidence_ids=_EV,
        applies_when=applies_when,
    )


def test_a_rule_whose_condition_holds_is_matched_with_its_evidence() -> None:
    rule = _rule("dos-vehiculos", {"field": "vehicle_count", "op": "ne", "value": "2"})
    (result,) = evaluate_ruleset((rule,), {"vehicle_count": "5"})
    assert result.result == "matched"
    assert result.evidence_ids == _EV
    assert ("vehicle_count", "5") in result.inputs


def test_an_exclusion_rule_that_does_not_fire_is_not_described_as_unmet() -> None:
    """Regresión de legibilidad: la mayoría de puertas son reglas de exclusión.

    `cide-requires-two-vehicles` se activa cuando `vehicle_count != 2`. El texto
    anterior decía «No se cumple con vehicle_count=2», que el lector interpreta
    como «no hay dos vehículos» —justo lo contrario de lo ocurrido—.
    """
    rule = _rule(
        "cide-requires-two-vehicles",
        {"field": "vehicle_count", "op": "ne", "value": "2"},
        description="Los Convenios exigen la intervención de sólo dos vehículos.",
    )
    (result,) = evaluate_ruleset((rule,), {"vehicle_count": "2"})

    assert result.result == "not_matched"
    assert "No se activa con vehicle_count=2" in result.rationale
    assert "No se cumple" not in result.rationale


def test_a_rule_that_fires_states_the_consequence_its_reviewer_signed() -> None:
    rule = _rule(
        "cide-requires-two-vehicles",
        {"field": "vehicle_count", "op": "ne", "value": "2"},
        outcome="vehicle_count != 2 ⇒ Convenio no aplicable.",
    )
    (result,) = evaluate_ruleset((rule,), {"vehicle_count": "5"})

    assert result.result == "matched"
    assert "Se activa con vehicle_count=5" in result.rationale
    assert "Convenio no aplicable" in result.rationale


def test_a_rule_whose_condition_fails_is_reported_as_not_matched() -> None:
    rule = _rule("dos-vehiculos", {"field": "vehicle_count", "op": "ne", "value": "2"})
    (result,) = evaluate_ruleset((rule,), {"vehicle_count": "2"})
    assert result.result == "not_matched"


def test_a_missing_fact_is_insufficient_data_and_never_a_guess() -> None:
    rule = _rule("dos-vehiculos", {"field": "vehicle_count", "op": "ne", "value": "2"})
    (result,) = evaluate_ruleset((rule,), {})
    assert result.result == "insufficient_data"
    assert result.inputs == ()


def test_every_rule_produces_an_evaluation_even_when_none_match() -> None:
    rules = (
        _rule("a", {"field": "x", "op": "eq", "value": "1"}),
        _rule("b", {"field": "y", "op": "eq", "value": "1"}),
        _rule("c", None, prerequisites=("z",)),
    )
    results = evaluate_ruleset(rules, {"x": "2"})
    assert [r.rule_id for r in results] == ["a", "b", "c"]
    assert {r.result for r in results} == {"not_matched", "insufficient_data"}


def test_a_rule_without_a_condition_reports_insufficient_data_not_a_match() -> None:
    """A rule we cannot evaluate yet must never be presented as satisfied."""
    rule = _rule("b10-cambio-carril", None, prerequisites=("lane_change_acknowledged_by_both",))
    (result,) = evaluate_ruleset((rule,), {"lane_change_acknowledged_by_both": "true"})
    assert result.result == "insufficient_data"


def test_boolean_operators_read_the_extracted_string_values() -> None:
    rule = _rule("cadena", {"field": "chain_collision", "op": "is_true"})
    (matched,) = evaluate_ruleset((rule,), {"chain_collision": "true"})
    (unmatched,) = evaluate_ruleset((rule,), {"chain_collision": "false"})
    assert matched.result == "matched"
    assert unmatched.result == "not_matched"


def test_all_and_any_compose_conditions() -> None:
    both = {"all": [{"field": "a", "op": "is_true"}, {"field": "b", "op": "is_true"}]}
    either = {"any": [{"field": "a", "op": "is_true"}, {"field": "b", "op": "is_true"}]}
    assert evaluate_ruleset((_rule("r", both),), {"a": "true", "b": "true"})[0].result == "matched"
    assert evaluate_ruleset((_rule("r", both),), {"a": "true", "b": "false"})[0].result == (
        "not_matched"
    )
    assert evaluate_ruleset((_rule("r", either),), {"a": "true", "b": "false"})[0].result == (
        "matched"
    )


def test_an_unknown_operator_is_rejected_rather_than_silently_ignored() -> None:
    rule = _rule("r", {"field": "a", "op": "regex_match", "value": ".*"})
    with pytest.raises(RulesetError, match="regex_match"):
        evaluate_ruleset((rule,), {"a": "x"})


def test_a_non_object_condition_branch_is_rejected_at_the_ruleset_boundary() -> None:
    """A malformed compound condition must not escape as an AttributeError."""
    rule = _rule("r", {"all": ["not-a-condition"]})

    with pytest.raises(RulesetError, match="condition branch"):
        evaluate_ruleset((rule,), {"a": "x"})


def test_the_rationale_names_the_rule_and_what_was_seen() -> None:
    rule = _rule(
        "cadena",
        {"field": "chain_collision", "op": "is_true"},
        description="La colisión en cadena no se tramita por Convenio.",
    )
    (result,) = evaluate_ruleset((rule,), {"chain_collision": "true"})
    assert isinstance(result, RuleEvaluation)
    assert "cadena" in result.rationale.lower()


def test_is_false_or_absent_fires_when_the_fact_is_missing() -> None:
    """Guard negativa: la regla debe disparar por defecto cuando el hecho
    simplemente no consta en el relato. Semántica intencional para
    ``ascide-b6-exit-from-parking`` (la nota de la regla dice explícitamente:
    «mientras exit_disputed_as_incorporation no conste como false, la regla
    no decide» — pero el motor lo modeló como ``is_false`` estricto, lo que
    rompe el caso normal en el que el hecho no se menciona)."""

    rule = _rule(
        "ascide-b6-exit-from-parking",
        {
            "all": [
                {"field": "exit_manoeuvre_by", "op": "ne", "value": ""},
                {"field": "exit_disputed_as_incorporation", "op": "is_false_or_absent"},
            ]
        },
        kind="manoeuvre",
    )
    (result,) = evaluate_ruleset((rule,), {"exit_manoeuvre_by": "A"})

    assert result.result == "matched"
    assert result.evidence_ids == _EV
    # El campo opcional no aparece en inputs porque no se consultó en facts.
    assert all(name != "exit_disputed_as_incorporation" for name, _ in result.inputs)


def test_is_false_or_absent_fires_when_the_fact_is_explicitly_false() -> None:
    rule = _rule(
        "ascide-b6-exit-from-parking",
        {
            "all": [
                {"field": "exit_manoeuvre_by", "op": "ne", "value": ""},
                {"field": "exit_disputed_as_incorporation", "op": "is_false_or_absent"},
            ]
        },
    )
    (result,) = evaluate_ruleset(
        (rule,),
        {"exit_manoeuvre_by": "A", "exit_disputed_as_incorporation": "false"},
    )
    assert result.result == "matched"


def test_is_false_or_absent_does_not_fire_when_the_fact_is_true() -> None:
    """Si el relato afirma explícitamente que la maniobra está disputada
    como incorporación, la regla NO debe disparar — eso es justo lo que el
    guard negativo protege."""

    rule = _rule(
        "ascide-b6-exit-from-parking",
        {
            "all": [
                {"field": "exit_manoeuvre_by", "op": "ne", "value": ""},
                {"field": "exit_disputed_as_incorporation", "op": "is_false_or_absent"},
            ]
        },
    )
    (result,) = evaluate_ruleset(
        (rule,),
        {"exit_manoeuvre_by": "A", "exit_disputed_as_incorporation": "true"},
    )
    assert result.result == "not_matched"
    assert result.evidence_ids == ()


def test_is_false_still_treats_absent_as_insufficient_data() -> None:
    """El operador ``is_false`` (estricto) NO cambia su semántica. Si el
    hecho falta, la regla sigue marcando ``insufficient_data`` — eso es
    deliberado para reglas como ``cide-requires-direct-collision`` donde la
    intención es "si NO hubo colisión directa, no aplica" (hecho ausente
    = desconocido, no decisión)."""

    rule = _rule(
        "cide-requires-direct-collision",
        {"field": "direct_collision", "op": "is_false"},
    )
    (result,) = evaluate_ruleset((rule,), {})
    assert result.result == "insufficient_data"


# --------------------------------------------------------------------------
# A rule evaluation must carry its own inputs, result and evidence.
#
# The audit forbids placeholder rules: the claim flow may only claim that
# a rule ran if it can say which inputs it saw, what it concluded and
# which manual page supports it.
# --------------------------------------------------------------------------


_EVIDENCE = ("sha256:" + "0" * 64 + ":page:56",)


def test_rule_evaluation_keeps_inputs_and_evidence() -> None:
    evaluation = RuleEvaluation(
        rule_id="cide-requires-two-vehicles",
        inputs=(("vehicle_count", "2"), ("direct_collision", "true")),
        result="matched",
        evidence_ids=_EVIDENCE,
        rationale="Dos vehículos con colisión directa.",
    )
    assert evaluation.inputs == (("vehicle_count", "2"), ("direct_collision", "true"))
    assert evaluation.result == "matched"


def test_rule_evaluation_rejects_a_matched_result_without_evidence() -> None:
    with pytest.raises(ValueError, match="evidence"):
        RuleEvaluation(
            rule_id="cide-requires-two-vehicles",
            inputs=(("vehicle_count", "2"),),
            result="matched",
            evidence_ids=(),
            rationale="Sin evidencia.",
        )


def test_rule_evaluation_rejects_an_empty_rationale() -> None:
    with pytest.raises(ValueError, match="rationale"):
        RuleEvaluation(
            rule_id="cide-requires-two-vehicles",
            inputs=(),
            result="insufficient_data",
            evidence_ids=(),
            rationale="   ",
        )


def test_rule_evaluation_rejects_an_empty_rule_id() -> None:
    with pytest.raises(ValueError, match="rule_id"):
        RuleEvaluation(
            rule_id="  ",
            inputs=(),
            result="not_matched",
            evidence_ids=(),
            rationale="Regla sin identificador.",
        )


def test_rule_evaluation_is_hashable_and_frozen() -> None:
    """Evaluations travel inside a frozen ClaimAnalysis; they must not mutate."""
    evaluation = RuleEvaluation(
        rule_id="cide-requires-two-vehicles",
        inputs=(("vehicle_count", "3"),),
        result="not_matched",
        evidence_ids=_EVIDENCE,
        rationale="Intervienen tres vehículos.",
    )
    assert hash(evaluation)
    with pytest.raises(AttributeError):
        evaluation.result = "matched"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# The shipped ruleset. These guard the delivery: a rule whose evidence stops
# resolving, or an attestation that decays, must fail loudly rather than let
# the claim workflow keep deciding on it.
# ---------------------------------------------------------------------------


_REPO = Path(__file__).resolve().parents[2]
_RULESET = _REPO / "data" / "rules" / "ruleset.v1.json"
_DOCUMENT_HASH = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"


def test_shipped_ruleset_validates_with_a_complete_attestation() -> None:
    report = validate_ruleset(
        _RULESET,
        expected_document_hash=_DOCUMENT_HASH,
        evidence_pool=evidence_pool_from_publications([_REPO / "data" / "extractions"]),
    )
    assert report.errors == ()
    assert report.attestation_complete


def test_shipped_ruleset_covers_the_five_interview_accidents() -> None:
    """Each accident in the brief must have a rule that speaks to it."""
    rules = {rule["rule_id"] for rule in json.loads(_RULESET.read_text(encoding="utf-8"))["rules"]}
    assert {
        "cide-requires-two-vehicles",  # accidents 1 and 2
        "cide-requires-direct-collision",
        "chain-collision-excludes-convention",  # accident 2
        "third-vehicle-identified-excludes-convention",  # accident 3
        "ascide-b5-parked-vehicle",  # accident 3
        "ascide-b10-lane-change",  # accident 4
        "alcohol-does-not-exclude-convention",  # accident 5
        "ascide-traffic-light-amber",  # accident 1
        "cide-matrix-lookup",  # accident 1
    } <= rules


def test_every_shipped_rule_cites_evidence_and_a_reviewer() -> None:
    """A rule without a page behind it is exactly the placeholder the audit forbids."""
    for rule in json.loads(_RULESET.read_text(encoding="utf-8"))["rules"]:
        assert rule["evidence_ids"], rule["rule_id"]
        assert rule["reviewer_id"].strip(), rule["rule_id"]
        assert rule["description"].strip(), rule["rule_id"]


def test_no_shipped_attestation_carries_a_placeholder_hash() -> None:
    """A zeroed transcription hash would make the attestation decorative."""
    for artifact in (_RULESET, _REPO / "data" / "rules" / "cide-matrix.v1.json"):
        attestation = json.loads(artifact.read_text(encoding="utf-8"))["attestation"]
        for entry in attestation["transcriptions"]:
            assert entry["transcription_sha256"] != "0" * 64, artifact.name
        assert "pendiente" not in attestation["divergence_resolution"].lower()


def test_a_resolved_decision_requires_a_matched_rule() -> None:
    """The invariant that stops a conclusion with nothing deterministic behind it."""
    from domain.models.decision import ClaimAnalysis, InvalidDecisionError

    with pytest.raises(InvalidDecisionError, match="matched rule"):
        ClaimAnalysis(
            applicability="applicable",
            convention="CIDE",
            decision="resolved",
            party_ids=("A", "B"),
            facts=(),
            contradictions=(),
            conditions=(),
            missing_information=(),
            blocks=(),
            rules_evaluated=(),
        )


def test_an_inapplicable_convention_cannot_stay_conditional_either() -> None:
    """`resolved` ya estaba bloqueado; `conditional` sobre un Convenio ya
    descartado es el mismo error: no hay nada que condicionar, sólo declarar
    que no procede."""
    from domain.models.decision import ClaimAnalysis, InvalidDecisionError

    with pytest.raises(InvalidDecisionError, match="not_assessed"):
        ClaimAnalysis(
            applicability="not_applicable",
            convention=None,
            decision="conditional",
            party_ids=("A", "B"),
            facts=(),
            contradictions=(),
            conditions=("¿Cuál fue el primer impacto?",),
            missing_information=("¿Cuál fue el primer impacto?",),
            blocks=(),
        )


def test_a_resolved_decision_is_allowed_when_a_rule_matched() -> None:
    from domain.models.decision import ClaimAnalysis

    analysis = ClaimAnalysis(
        applicability="applicable",
        convention="CIDE",
        decision="resolved",
        party_ids=("A", "B"),
        facts=(),
        contradictions=(),
        conditions=(),
        missing_information=(),
        blocks=(),
        rules_evaluated=(
            RuleEvaluation(
                rule_id="cide-requires-two-vehicles",
                inputs=(("vehicle_count", "2"),),
                result="matched",
                evidence_ids=_EVIDENCE,
                rationale="Dos vehículos.",
            ),
        ),
    )
    assert analysis.decision == "resolved"


def test_shipped_lane_change_rule_matches_on_acknowledged_lane_change() -> None:
    """Regression for accident-04: b.10 must be machine-checkable, not just documented."""
    from infrastructure.config.rules_artifacts import load_rules_artifacts

    artifacts = load_rules_artifacts(
        _REPO / "data" / "rules",
        expected_document_hash=_DOCUMENT_HASH,
        evidence_roots=(_REPO / "data" / "extractions",),
    )
    (evaluation,) = [
        result
        for result in evaluate_ruleset(
            artifacts.rules,
            {"lane_change_acknowledged_by_both": "true", "contradictory_versions": "true"},
        )
        if result.rule_id == "ascide-b10-lane-change"
    ]
    assert evaluation.result == "matched"
    assert evaluation.evidence_ids


def test_shipped_lane_change_rule_does_not_match_without_disparity() -> None:
    from infrastructure.config.rules_artifacts import load_rules_artifacts

    artifacts = load_rules_artifacts(
        _REPO / "data" / "rules",
        expected_document_hash=_DOCUMENT_HASH,
        evidence_roots=(_REPO / "data" / "extractions",),
    )
    (evaluation,) = [
        result
        for result in evaluate_ruleset(
            artifacts.rules,
            {"lane_change_acknowledged_by_both": "true", "contradictory_versions": "false"},
        )
        if result.rule_id == "ascide-b10-lane-change"
    ]
    assert evaluation.result == "not_matched"


def test_shipped_amber_rule_matches_when_one_driver_admits_amber() -> None:
    from infrastructure.config.rules_artifacts import load_rules_artifacts

    artifacts = load_rules_artifacts(
        _REPO / "data" / "rules",
        expected_document_hash=_DOCUMENT_HASH,
        evidence_roots=(_REPO / "data" / "extractions",),
    )
    (evaluation,) = [
        result
        for result in evaluate_ruleset(
            artifacts.rules,
            {"traffic_light_junction": "true", "admitted_amber": "true"},
        )
        if result.rule_id == "ascide-traffic-light-amber"
    ]

    assert evaluation.result == "matched"


def _shipped_evaluation(rule_id: str, facts: dict[str, str]):
    from infrastructure.config.rules_artifacts import load_rules_artifacts

    artifacts = load_rules_artifacts(
        _REPO / "data" / "rules",
        expected_document_hash=_DOCUMENT_HASH,
        evidence_roots=(_REPO / "data" / "extractions",),
    )
    (evaluation,) = [
        result for result in evaluate_ruleset(artifacts.rules, facts) if result.rule_id == rule_id
    ]
    return evaluation


def test_shipped_parked_vehicle_rule_matches_when_declared() -> None:
    evaluation = _shipped_evaluation(
        "ascide-b5-parked-vehicle",
        {"one_vehicle_parked": "true", "collision_with_parked_vehicle": "true"},
    )
    assert evaluation.result == "matched"


def test_shipped_parked_vehicle_rule_does_not_match_a_moving_dispute() -> None:
    """Un vehículo detenido ante un semáforo no es un vehículo aparcado."""
    evaluation = _shipped_evaluation(
        "ascide-b5-parked-vehicle",
        {"one_vehicle_parked": "false", "collision_with_parked_vehicle": "true"},
    )
    assert evaluation.result == "not_matched"


def test_shipped_exit_from_parking_rule_matches_the_exiting_vehicle() -> None:
    evaluation = _shipped_evaluation(
        "ascide-b6-exit-from-parking",
        {"exit_manoeuvre_by": "A", "exit_disputed_as_incorporation": "false"},
    )
    assert evaluation.result == "matched"


def test_shipped_exit_from_parking_rule_defers_to_the_incorporation_exception() -> None:
    """El manual remite esta excepción a otro apartado no verificado: la regla
    debe abstenerse, no decidir igualmente."""
    evaluation = _shipped_evaluation(
        "ascide-b6-exit-from-parking",
        {"exit_manoeuvre_by": "A", "exit_disputed_as_incorporation": "true"},
    )
    assert evaluation.result == "not_matched"


def test_shipped_reverse_vs_rear_impact_rule_matches_the_front_damage_vehicle() -> None:
    evaluation = _shipped_evaluation(
        "ascide-b9-reverse-vs-rear-impact",
        {"contradictory_versions": "true", "front_damage_vehicle": "B"},
    )
    assert evaluation.result == "matched"


def test_shipped_reverse_vs_rear_impact_rule_needs_a_real_disparity() -> None:
    evaluation = _shipped_evaluation(
        "ascide-b9-reverse-vs-rear-impact",
        {"contradictory_versions": "false", "front_damage_vehicle": "B"},
    )
    assert evaluation.result == "not_matched"


def test_shipped_door_opening_rule_matches_only_when_the_action_is_unspecified() -> None:
    evaluation = _shipped_evaluation(
        "cide-door-opening",
        {
            "door_involved": "true",
            "door_opening_specified": "false",
            "door_vehicle": "A",
        },
    )
    assert evaluation.result == "matched"


def test_shipped_door_opening_rule_defers_when_the_action_is_specified() -> None:
    """Si el anverso de la D.A.A. precisa la acción, se resuelve por el Código
    de Circulación — algo que esta regla no cubre y no debe fingir cubrir."""
    evaluation = _shipped_evaluation(
        "cide-door-opening",
        {
            "door_involved": "true",
            "door_opening_specified": "true",
            "door_vehicle": "A",
        },
    )
    assert evaluation.result == "not_matched"


# --------------------------------------------------------------------------
# Convention table lookup must refuse to decide without explicit prerequisites.
# --------------------------------------------------------------------------


def test_matrix_does_not_decide_without_confirmed_prerequisites() -> None:
    from domain.rules.cide_matrix import lookup_matrix

    result = lookup_matrix({}, a=1, b=2, prerequisites_confirmed=False)

    assert result.status == "undetermined"
    assert result.cell is None


def test_matrix_does_not_decide_when_a_or_b_is_unknown() -> None:
    from domain.rules.cide_matrix import lookup_matrix

    result = lookup_matrix({}, a=None, b=2, prerequisites_confirmed=True)

    assert result.status == "undetermined"
    assert result.cell is None


def test_matrix_resolves_only_from_explicit_daa_codes() -> None:
    """A checked A1/B8 pair maps to the 1-based matrix positions (2, 9)."""
    from domain.models.claim import MatrixCell
    from domain.rules.cide_matrix import lookup_daa_matrix

    result = lookup_daa_matrix(
        {(2, 9): MatrixCell(2, 9, "B", ("manual:page:101",))},
        facts={"daa_box_a": "A1", "daa_box_b": "B8", "daa_section_12_only": "true"},
        prerequisites_confirmed=True,
    )

    assert result.status == "resolved"
    assert result.cell is not None
    assert result.cell.outcome == "B"


def test_matrix_refuses_a_narrative_without_confirmed_daa_checkboxes() -> None:
    """No text description is a substitute for an explicitly declared D.A.A. pair."""
    from domain.models.claim import MatrixCell
    from domain.rules.cide_matrix import lookup_daa_matrix

    result = lookup_daa_matrix(
        {(2, 9): MatrixCell(2, 9, "B", ("manual:page:101",))},
        facts={"daa_box_a": "A1", "daa_box_b": "B8"},
        prerequisites_confirmed=True,
    )

    assert result.status == "undetermined"
    assert result.cell is None


# --------------------------------------------------------------------------
# La tabla 18×18 sólo decide desde casillas D.A.A. declaradas, y sus cuatro
# observaciones no se pueden ignorar.
#
# La tabla estaba transcrita, atestada y con `lookup_daa_matrix` probado, pero
# nadie la llamaba: las celdas se cargaban en el arranque y no llegaban al flujo
# de siniestros, así que un caso con las casillas declaradas nunca se resolvía.
#
# Cuatro celdas llevan asterisco y una observación del manual («A2 + B4 = Culpable
# B, salvo que el A abra la puerta»). Resolverlas como si fueran celdas normales
# sería atribuir una culpa que el manual condiciona.
# --------------------------------------------------------------------------


_EV_PAGE_101 = ("sha256:" + "b" * 64 + ":page:101",)


def _cells() -> dict[tuple[int, int], MatrixCell]:
    # Posiciones 1-based: A0→1, A2→3, A4→5, B0→1, B2→3, B4→5.
    return {
        (2, 9): MatrixCell(2, 9, "B", _EV_PAGE_101),  # A1 + B8 → culpable B
        (1, 2): MatrixCell(1, 2, "-", _EV_PAGE_101),  # A0 + B1 → sin atribución
        (3, 5): MatrixCell(3, 5, "B*", _EV_PAGE_101),  # A2 + B4 → culpable B salvo puerta de A
    }


def _door_exception() -> tuple[MatrixException, ...]:
    return (
        MatrixException(
            note_id="obs-a2-b4",
            text="A2 + B4 = Culpable B, salvo que el A abra la puerta.",
            positions=((3, 5),),
            fact="door_opened_by",
            actor="A",
            liable_unless_exception="B",
            evidence_ids=_EV_PAGE_101,
        ),
    )


def _facts(**extra: str) -> dict[str, str]:
    return {"daa_box_a": "A1", "daa_box_b": "B8", "daa_section_12_only": "true", **extra}


def test_a_declared_pair_attributes_liability_with_its_cell_evidence() -> None:
    decision = decide_from_daa_matrix(
        _cells(), exceptions=(), facts=_facts(), prerequisites_confirmed=True
    )

    assert decision.status == "attributes"
    assert decision.liable_party == "B"
    assert decision.evidence_ids == _EV_PAGE_101


def test_a_narrative_without_declared_boxes_never_reaches_the_table() -> None:
    """La regla del proyecto: las casillas A0–A17 no se infieren de un relato."""
    decision = decide_from_daa_matrix(
        _cells(),
        exceptions=(),
        facts={"vehicle_count": "2", "direct_collision": "true"},
        prerequisites_confirmed=True,
    )

    assert decision.status == "undetermined"
    assert decision.liable_party is None


def test_a_dash_cell_reports_that_the_table_attributes_nothing() -> None:
    decision = decide_from_daa_matrix(
        _cells(),
        exceptions=(),
        facts=_facts(daa_box_a="A0", daa_box_b="B1"),
        prerequisites_confirmed=True,
    )

    assert decision.status == "no_attribution"
    assert decision.liable_party is None


def test_a_starred_cell_asks_for_its_exception_fact_before_deciding() -> None:
    decision = decide_from_daa_matrix(
        _cells(),
        exceptions=_door_exception(),
        facts=_facts(daa_box_a="A2", daa_box_b="B4"),
        prerequisites_confirmed=True,
    )

    assert decision.status == "needs_exception_fact"
    assert decision.liable_party is None
    assert decision.missing_fact == "door_opened_by"
    assert decision.exception_text is not None
    assert "abra la puerta" in decision.exception_text


def test_a_starred_cell_attributes_when_the_exception_is_ruled_out() -> None:
    decision = decide_from_daa_matrix(
        _cells(),
        exceptions=_door_exception(),
        facts=_facts(daa_box_a="A2", daa_box_b="B4", door_opened_by="B"),
        prerequisites_confirmed=True,
    )

    assert decision.status == "attributes"
    assert decision.liable_party == "B"


def test_a_starred_cell_withdraws_the_attribution_when_the_exception_holds() -> None:
    """«Culpable B, salvo que el A abra la puerta»: si A la abre, el manual no
    dice quién responde. Inventarlo sería exactamente lo que la spec prohíbe."""
    decision = decide_from_daa_matrix(
        _cells(),
        exceptions=_door_exception(),
        facts=_facts(daa_box_a="A2", daa_box_b="B4", door_opened_by="A"),
        prerequisites_confirmed=True,
    )

    assert decision.status == "exception_applies"
    assert decision.liable_party is None
    assert decision.exception_text is not None


def test_an_unknown_pair_stays_undetermined_instead_of_guessing() -> None:
    decision = decide_from_daa_matrix(
        _cells(),
        exceptions=(),
        facts=_facts(daa_box_a="A9", daa_box_b="B9"),
        prerequisites_confirmed=True,
    )

    assert decision.status == "undetermined"


def test_the_table_is_not_applied_without_confirmed_prerequisites() -> None:
    decision = decide_from_daa_matrix(
        _cells(), exceptions=(), facts=_facts(), prerequisites_confirmed=False
    )

    assert decision.status == "undetermined"


def test_an_exception_actor_outside_the_two_parties_is_rejected() -> None:
    with pytest.raises(ValueError, match="actor"):
        MatrixException(
            note_id="obs-mala",
            text="…",
            positions=((3, 5),),
            fact="door_opened_by",
            actor="C",
            liable_unless_exception="B",
            evidence_ids=_EV_PAGE_101,
        )


# --------------------------------------------------------------------------
# Safety invariants for attributable claim facts and convention decisions.
# --------------------------------------------------------------------------


def test_contradictory_statements_keep_their_respective_attribution() -> None:
    from domain.models.claim import ClaimContradiction, ClaimFact

    first = ClaimFact("traffic_light", "verde", "A", "A declara que tenía verde")
    second = ClaimFact("traffic_light", "rojo", "B", "B declara que A tenía rojo")

    contradiction = ClaimContradiction("traffic_light", (first, second))

    assert contradiction.statements == (first, second)


def test_conditional_claim_requires_visible_conditions() -> None:
    from domain.models.decision import ClaimAnalysis, InvalidDecisionError

    with pytest.raises(InvalidDecisionError, match="conditional"):
        ClaimAnalysis(
            applicability="undetermined",
            convention=None,
            decision="conditional",
            party_ids=("A", "B"),
            facts=(),
            contradictions=(),
            conditions=(),
            missing_information=("Confirmar las circunstancias.",),
            blocks=(),
            rules_evaluated=(
                RuleEvaluation(
                    rule_id="cide-requires-two-vehicles",
                    inputs=(("vehicle_count", "2"),),
                    result="matched",
                    evidence_ids=("sha256:" + "b" * 64 + ":page:56",),
                    rationale="Dos vehículos con colisión directa.",
                ),
            ),
        )


def test_inapplicable_convention_cannot_return_a_resolved_decision() -> None:
    from domain.models.decision import ClaimAnalysis, InvalidDecisionError

    with pytest.raises(InvalidDecisionError, match="inapplicable"):
        ClaimAnalysis(
            applicability="not_applicable",
            convention=None,
            decision="resolved",
            party_ids=("A", "B"),
            facts=(),
            contradictions=(),
            conditions=(),
            missing_information=(),
            blocks=(),
            rules_evaluated=(
                RuleEvaluation(
                    rule_id="cide-requires-two-vehicles",
                    inputs=(("vehicle_count", "2"),),
                    result="matched",
                    evidence_ids=("sha256:" + "b" * 64 + ":page:56",),
                    rationale="Dos vehículos con colisión directa.",
                ),
            ),
        )


# --------------------------------------------------------------------------
# Interview-plan values keep the LLM conversation bounded and renderable.
# --------------------------------------------------------------------------


def test_interview_plan_rejects_an_ask_state_without_questions() -> None:
    from application.models.claim import InterviewPlan

    with pytest.raises(ValueError, match="requires at least one question"):
        InterviewPlan(status="ask")


def test_interview_question_rejects_duplicate_options() -> None:
    from application.models.claim import InterviewQuestion

    with pytest.raises(ValueError, match="unique"):
        InterviewQuestion(
            id="vehicle_a_signal",
            prompt="¿Qué color tenía el semáforo de A?",
            reason="Puede cambiar la prioridad.",
            answer_kind="choice",
            options=("Rojo", "Rojo"),
        )


def test_ready_interview_plan_has_no_questions() -> None:
    from application.models.claim import InterviewPlan, InterviewQuestion

    question = InterviewQuestion(
        id="vehicle_a_signal",
        prompt="¿Qué color tenía el semáforo de A?",
        reason="Puede cambiar la prioridad.",
        answer_kind="choice",
        options=("Rojo", "Verde", "No se sabe"),
    )

    with pytest.raises(ValueError, match="cannot carry questions"):
        InterviewPlan(status="ready", questions=(question,))
