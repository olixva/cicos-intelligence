"""Immutable claim facts and source-bound values used by convention rules."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ClaimInput:
    """User-provided accident narrative kept separate from later clarifications."""

    text: str
    language: Literal["es", "en"] = "es"
    clarifications: tuple[str, ...] = ()
    session_id: str | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("claim text must be nonempty")
        if self.language not in ("es", "en"):
            raise ValueError("claim language must be es or en")
        if any(not item.strip() for item in self.clarifications):
            raise ValueError("claim clarifications must be nonempty")
        if self.session_id is not None and not self.session_id.strip():
            raise ValueError("claim session_id must be nonempty")


@dataclass(frozen=True, slots=True)
class ClaimFact:
    """One extracted statement, retaining who asserted it and its literal origin."""

    name: str
    value: str | None
    asserted_by: str | None
    source_text: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.source_text.strip():
            raise ValueError("claim fact name and source text must be nonempty")


@dataclass(frozen=True, slots=True)
class ClaimContradiction:
    """Incompatible attributed statements; it never creates a shared fact."""

    fact_name: str
    statements: tuple[ClaimFact, ...]

    def __post_init__(self) -> None:
        if not self.fact_name.strip() or len(self.statements) < 2:
            raise ValueError("a contradiction needs a fact name and two statements")
        if any(statement.name != self.fact_name for statement in self.statements):
            raise ValueError("contradiction statements must concern the named fact")


@dataclass(frozen=True, slots=True)
class ClaimEvidenceBlock:
    """One claim explanation passage and its immutable supporting evidence IDs."""

    text: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.text.strip() or any(not item.strip() for item in self.evidence_ids):
            raise ValueError("claim evidence block is invalid")


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
