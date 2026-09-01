"""Application entry point for document questions."""

from dataclasses import dataclass

from application.models.query import QueryExecution, QueryInput
from application.ports.outbound.question_workflow import QuestionWorkflow


@dataclass(frozen=True, slots=True)
class AnswerQuestionUseCase:
    """Delegate technical orchestration through the workflow port."""

    workflow: QuestionWorkflow

    async def execute(self, query: QueryInput) -> QueryExecution:
        return await self.workflow.run(query)
