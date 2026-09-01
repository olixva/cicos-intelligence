"""Explicit HTTP endpoint for grounded document questions."""

from fastapi import APIRouter

from application.models.query import QueryInput
from application.ports.inbound.answer_question import AnswerQuestion
from infrastructure.adapters.inbound.api.schemas.question import QuestionRequest, QuestionResponse


def build_question_router(answer_question: AnswerQuestion) -> APIRouter:
    """Bind the question route solely to its inbound application port."""

    router = APIRouter(prefix="/api/v1/questions", tags=["questions"])

    async def answer_question_route(request: QuestionRequest) -> QuestionResponse:
        execution = await answer_question.execute(QueryInput(request.text, request.language))
        return QuestionResponse.from_domain(execution)

    router.add_api_route(
        "/answer",
        answer_question_route,
        methods=["POST"],
        response_model=QuestionResponse,
    )
    return router
