"""Safe lookup over a reviewed CIDE matrix; never infer missing prerequisites."""

from collections.abc import Mapping

from domain.models.claim import MatrixCell
from domain.models.decision import MatrixLookup


def lookup_matrix(
    cells: Mapping[tuple[int, int], MatrixCell],
    *,
    a: int | None,
    b: int | None,
    prerequisites_confirmed: bool,
) -> MatrixLookup:
    """Return a cell only after explicit prerequisites and both table positions exist."""
    if not prerequisites_confirmed or a is None or b is None:
        return MatrixLookup(status="undetermined", cell=None)
    cell = cells.get((a, b))
    return (
        MatrixLookup(status="resolved", cell=cell)
        if cell is not None
        else MatrixLookup(status="undetermined", cell=None)
    )


def lookup_daa_matrix(
    cells: Mapping[tuple[int, int], MatrixCell],
    *,
    facts: Mapping[str, str],
    prerequisites_confirmed: bool,
) -> MatrixLookup:
    """Resolve a matrix cell only from an explicit pair of D.A.A. box codes.

    The D.A.A. form has boxes 1–17; matrix label 0 is the reviewed local
    convention for an absent declaration. A free-text manoeuvre is never
    converted here: callers must provide the checked ``A<n>`` and ``B<n>``
    values and confirm that section 12 is the deciding D.A.A. evidence.
    """
    if facts.get("daa_section_12_only", "").strip().lower() != "true":
        return MatrixLookup(status="undetermined", cell=None)
    a = _daa_position(facts.get("daa_box_a"), party="A")
    b = _daa_position(facts.get("daa_box_b"), party="B")
    return lookup_matrix(cells, a=a, b=b, prerequisites_confirmed=prerequisites_confirmed)


def _daa_position(value: str | None, *, party: str) -> int | None:
    """Translate an explicit D.A.A. label into the one-based artifact position."""
    if value is None:
        return None
    code = value.strip().upper()
    if not code.startswith(party):
        return None
    try:
        index = int(code[1:])
    except ValueError:
        return None
    return index + 1 if 0 <= index <= 17 else None
