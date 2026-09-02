"""Convention table lookup must refuse to decide without explicit prerequisites."""


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
