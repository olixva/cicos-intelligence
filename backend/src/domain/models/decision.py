"""Closed deterministic decision values for claims analysis."""

from dataclasses import dataclass
from typing import Literal

from domain.models.claim import ClaimContradiction, ClaimEvidenceBlock, ClaimFact, MatrixCell
from domain.models.rule_evaluation import RuleEvaluation


class InvalidDecisionError(ValueError):
    """Raised when a claim conclusion violates mandatory safety invariants."""


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


@dataclass(frozen=True, slots=True)
class ClaimAnalysis:
    """A bounded convention assessment, distinct from a general liability opinion."""

    applicability: Literal["applicable", "not_applicable", "undetermined"]
    convention: Literal["CIDE", "ASCIDE"] | None
    decision: Literal["resolved", "conditional", "undetermined", "not_assessed"]
    party_ids: tuple[str, ...]
    facts: tuple[ClaimFact, ...]
    contradictions: tuple[ClaimContradiction, ...]
    conditions: tuple[str, ...]
    missing_information: tuple[str, ...]
    blocks: tuple[ClaimEvidenceBlock, ...]
    #: Every rule the deterministic engine actually ran, with its inputs and
    #: evidence. The audit forbids placeholders here: a rule that did not run
    #: is absent, and one that could not be checked says so.
    rules_evaluated: tuple[RuleEvaluation, ...] = ()

    def __post_init__(self) -> None:
        if len(set(self.party_ids)) != len(self.party_ids) or any(
            not party_id.strip() for party_id in self.party_ids
        ):
            raise InvalidDecisionError("claim party identifiers must be nonempty and unique")
        if self.decision == "conditional" and not self.conditions:
            raise InvalidDecisionError("a conditional decision must name its conditions")
        if self.applicability == "not_applicable" and self.decision == "resolved":
            raise InvalidDecisionError("an inapplicable convention cannot resolve a claim")
        if self.decision == "resolved" and not any(
            evaluation.result == "matched" for evaluation in self.rules_evaluated
        ):
            # The last barrier against a generated conclusion with nothing
            # deterministic behind it.
            raise InvalidDecisionError("a resolved decision must cite at least one matched rule")
