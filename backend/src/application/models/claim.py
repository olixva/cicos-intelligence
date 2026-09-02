"""Application execution values for source-grounded convention analysis."""

from dataclasses import dataclass
from typing import Literal

from application.models.query import ContextEvidence
from domain.models.claim import ClaimFact
from domain.models.decision import ClaimAnalysis


InterviewStatus = Literal["ask", "ready", "inconsistent", "coverage_gap"]
AnswerKind = Literal["text", "choice", "boolean"]


@dataclass(frozen=True, slots=True)
class InterviewQuestion:
    """One user-facing fact request, selected by the interview LLM."""

    id: str
    prompt: str
    reason: str
    answer_kind: AnswerKind = "text"
    options: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.prompt.strip() or not self.reason.strip():
            raise ValueError("interview question fields must be nonempty")
        if self.answer_kind not in ("text", "choice", "boolean"):
            raise ValueError("interview question answer_kind is invalid")
        if any(not option.strip() for option in self.options) or len(set(self.options)) != len(
            self.options
        ):
            raise ValueError("interview question options must be nonempty and unique")
        if self.answer_kind == "choice" and not self.options:
            raise ValueError("choice interview questions require options")


@dataclass(frozen=True, slots=True)
class InterviewPlan:
    """The LLM's bounded next-step decision for a claim conversation."""

    status: InterviewStatus
    questions: tuple[InterviewQuestion, ...] = ()
    terminal_reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in ("ask", "ready", "inconsistent", "coverage_gap"):
            raise ValueError("interview plan status is invalid")
        if len(self.questions) > 3 or len({question.id for question in self.questions}) != len(
            self.questions
        ):
            raise ValueError("interview plan questions must be unique and limited to three")
        if self.status == "ask" and not self.questions:
            raise ValueError("ask interview plan requires at least one question")
        if self.status != "ask" and self.questions:
            raise ValueError("terminal interview plan cannot carry questions")
        if self.status in ("inconsistent", "coverage_gap") and not (
            self.terminal_reason and self.terminal_reason.strip()
        ):
            raise ValueError("terminal interview plan requires a reason")


@dataclass(frozen=True, slots=True)
class ExtractedClaimFacts:
    """Structured, attributed observations extracted from the user narrative only."""

    party_ids: tuple[str, ...]
    facts: tuple[ClaimFact, ...]
    interview_plan: InterviewPlan = InterviewPlan("ready")

    def __post_init__(self) -> None:
        if len(set(self.party_ids)) != len(self.party_ids) or any(
            not party_id.strip() for party_id in self.party_ids
        ):
            raise ValueError("claim party identifiers must be nonempty and unique")


@dataclass(frozen=True, slots=True)
class ClaimExecution:
    """A claim result and the exact document evidence supplied to the workflow."""

    result: ClaimAnalysis
    context: tuple[ContextEvidence, ...]
    trace_id: str | None = None
    trace_url: str | None = None
    needs_input: bool = False
    thread_id: str | None = None
    missing_information: tuple[str, ...] = ()
