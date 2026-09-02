"""Loading the signed artifacts is a startup decision, never a silent default.

If the matrix or the ruleset fails validation the process must fail loudly.
Degrading to "no rules" without saying so is exactly how a demo ends up
claiming a decision nothing supports.
"""

import json
from pathlib import Path

import pytest

from domain.rules.ruleset import LoadedRule
from infrastructure.config.rules_artifacts import (
    RulesArtifactsUnavailable,
    load_rules_artifacts,
)

_REPO = Path(__file__).resolve().parents[2]


def test_loads_the_shipped_artifacts() -> None:
    artifacts = load_rules_artifacts(_REPO / "data" / "rules")
    assert len(artifacts.rules) == 14
    assert all(isinstance(rule, LoadedRule) for rule in artifacts.rules)
    assert len(artifacts.matrix_cells) == 324


def test_loads_the_four_printed_matrix_observations() -> None:
    """Las cuatro observaciones bajo la tabla (pág. 101) sólo deciden lo que
    el manual dice: no un patrón genérico deducido del asterisco."""
    artifacts = load_rules_artifacts(_REPO / "data" / "rules")
    by_id = {exception.note_id: exception for exception in artifacts.matrix_exceptions}

    assert set(by_id) == {"obs-a2-b4", "obs-b2-a4", "obs-a16-b0", "obs-b16-a0"}
    a2_b4 = by_id["obs-a2-b4"]
    assert a2_b4.fact == "door_opened_by"
    assert a2_b4.actor == "A"
    assert a2_b4.liable_unless_exception == "B"
    a2_position = (
        artifacts.row_labels.index("A2") + 1,
        artifacts.column_labels.index("B4") + 1,
    )
    assert a2_position in a2_b4.positions
    # La celda que gobierna cada observación debe llevar de verdad el asterisco.
    for exception in artifacts.matrix_exceptions:
        for position in exception.positions:
            assert "*" in artifacts.matrix_cells[position].outcome, exception.note_id


def test_rules_keep_the_order_of_the_artifact() -> None:
    artifacts = load_rules_artifacts(_REPO / "data" / "rules")
    raw = json.loads((_REPO / "data" / "rules" / "ruleset.v1.json").read_text(encoding="utf-8"))
    assert [rule.rule_id for rule in artifacts.rules] == [r["rule_id"] for r in raw["rules"]]


def test_a_missing_ruleset_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(RulesArtifactsUnavailable, match="ruleset"):
        load_rules_artifacts(tmp_path)


def test_an_unsigned_matrix_is_refused(tmp_path: Path) -> None:
    """An artifact without a complete attestation must not drive decisions."""
    source = _REPO / "data" / "rules"
    (tmp_path / "ruleset.v1.json").write_text(
        (source / "ruleset.v1.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    matrix = json.loads((source / "cide-matrix.v1.json").read_text(encoding="utf-8"))
    matrix["attestation"]["signed_by"] = []
    (tmp_path / "cide-matrix.v1.json").write_text(json.dumps(matrix), encoding="utf-8")

    with pytest.raises(RulesArtifactsUnavailable, match="attestation|signed"):
        load_rules_artifacts(tmp_path)
