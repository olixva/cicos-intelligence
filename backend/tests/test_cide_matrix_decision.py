"""La tabla 18×18 sólo decide desde casillas D.A.A. declaradas, y sus cuatro
observaciones no se pueden ignorar.

La tabla estaba transcrita, atestada y con `lookup_daa_matrix` probado, pero
nadie la llamaba: las celdas se cargaban en el arranque y no llegaban al flujo
de siniestros, así que un caso con las casillas declaradas nunca se resolvía.

Cuatro celdas llevan asterisco y una observación del manual («A2 + B4 = Culpable
B, salvo que el A abra la puerta»). Resolverlas como si fueran celdas normales
sería atribuir una culpa que el manual condiciona.
"""

import pytest

from domain.models.claim import MatrixCell
from domain.rules.cide_matrix import MatrixException, decide_from_daa_matrix

_EV = ("sha256:" + "b" * 64 + ":page:101",)


def _cells() -> dict[tuple[int, int], MatrixCell]:
    # Posiciones 1-based: A0→1, A2→3, A4→5, B0→1, B2→3, B4→5.
    return {
        (2, 9): MatrixCell(2, 9, "B", _EV),  # A1 + B8 → culpable B
        (1, 2): MatrixCell(1, 2, "-", _EV),  # A0 + B1 → sin atribución
        (3, 5): MatrixCell(3, 5, "B*", _EV),  # A2 + B4 → culpable B salvo puerta de A
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
            evidence_ids=_EV,
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
    assert decision.evidence_ids == _EV


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
            evidence_ids=_EV,
        )
