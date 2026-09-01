"""Immutable source-bound values used by deterministic convention rules."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MatrixCell:
    """One reviewed CIDE-table outcome and the source pages supporting it."""

    a: int
    b: int
    outcome: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.a) is not int or type(self.b) is not int:
            raise ValueError("matrix positions must be integers")
        if not self.outcome.strip():
            raise ValueError("matrix outcome must be nonempty")
        if not self.evidence_ids or any(not item.strip() for item in self.evidence_ids):
            raise ValueError("matrix evidence identifiers must be nonempty")
