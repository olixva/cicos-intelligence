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
