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
