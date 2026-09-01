"""Typed local doubles shared by question-workflow tests."""

from collections.abc import Sequence

from application.models.query import ContextEvidence, QueryInput, QuestionAnswer
from application.models.retrieval import Chunk
from application.ports.outbound.language_model import LanguageModelError
from application.ports.outbound.retriever import RetrievalRequest
from domain.models.evidence import PageEvidence


class FakeRetriever:
    def __init__(self, chunks: Sequence[Chunk]) -> None:
        self._chunks = tuple(chunks)
        self.requests: list[RetrievalRequest] = []

    async def retrieve(self, request: RetrievalRequest) -> tuple[Chunk, ...]:
        self.requests.append(request)
        return self._chunks


class FakeEvidenceRepository:
    def __init__(self, pages: Sequence[PageEvidence]) -> None:
        self._pages = {page.evidence_id: page for page in pages}

    def get(self, evidence_id: str) -> PageEvidence:
        return self._pages[evidence_id]


class FakeLanguageModel:
    def __init__(self, answer: QuestionAnswer) -> None:
        self.answer = answer
        self.calls: list[tuple[QueryInput, tuple[ContextEvidence, ...]]] = []

    async def generate(
        self, query: QueryInput, context: Sequence[ContextEvidence]
    ) -> QuestionAnswer:
        effective_context = tuple(context)
        self.calls.append((query, effective_context))
        return self.answer


class FailingLanguageModel:
    async def generate(
        self, query: QueryInput, context: Sequence[ContextEvidence]
    ) -> QuestionAnswer:
        del query, context
        raise LanguageModelError("provider transport failed")
