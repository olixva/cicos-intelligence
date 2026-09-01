"""Application entry point that closes over the routing service."""

from collections.abc import Awaitable, Callable

from application.models.query import QueryInput
from application.ports.inbound.analyze_claim import AnalyzeClaim
from application.ports.inbound.answer_question import AnswerQuestion
from application.ports.outbound.query_classifier import QueryClassifier
from domain.models.routing import RouteExecution


class ResolveQueryUseCase:
    """Bind the inbound port to a routing closure built by the composition root."""

    def __init__(
        self,
        resolve_query_fn: Callable[
            [QueryInput, QueryClassifier, AnswerQuestion, AnalyzeClaim],
            Awaitable[RouteExecution],
        ],
        *,
        classifier: QueryClassifier,
        answer_question: AnswerQuestion,
        analyze_claim: AnalyzeClaim,
    ) -> None:
        self._resolve = resolve_query_fn
        self._classifier = classifier
        self._answer_question = answer_question
        self._analyze_claim = analyze_claim

    async def execute(self, query: QueryInput) -> RouteExecution:
        return await self._resolve(
            query, self._classifier, self._answer_question, self._analyze_claim
        )
