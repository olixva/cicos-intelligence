"""One deterministic rule application, with the inputs and evidence that justify it."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    """A rule that actually ran, never a placeholder for one that did not.

    ``inputs`` records the facts the rule actually saw, so a reader can tell
    an unmet condition apart from a missing datum. ``result`` keeps those two
    cases distinct: ``not_matched`` means the condition was evaluated and did
    not hold, while ``insufficient_data`` means it could not be evaluated.
    """

    rule_id: str
    inputs: tuple[tuple[str, str], ...]
    result: Literal["matched", "not_matched", "insufficient_data"]
    evidence_ids: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("rule_id must be nonempty")
        if not self.rationale.strip():
            raise ValueError("rationale must be nonempty")
        if self.result == "matched" and not self.evidence_ids:
            raise ValueError("a matched rule must cite the evidence that supports it")
