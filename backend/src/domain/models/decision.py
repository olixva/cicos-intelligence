"""Closed deterministic decision values for claims analysis."""

from dataclasses import dataclass
from typing import Literal

from domain.models.claim import MatrixCell


@dataclass(frozen=True, slots=True)
class MatrixLookup:
    """A table outcome is either explicitly resolved or safely indeterminate."""

    status: Literal["resolved", "undetermined"]
    cell: MatrixCell | None

    def __post_init__(self) -> None:
        if self.status == "resolved" and self.cell is None:
            raise ValueError("resolved matrix lookup requires a cell")
        if self.status == "undetermined" and self.cell is not None:
            raise ValueError("undetermined matrix lookup must not contain a cell")
