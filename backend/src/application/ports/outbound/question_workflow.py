"""Outbound orchestration port for the document-question flow."""

from collections.abc import Awaitable
from typing import Protocol

from application.models.query import QueryExecution, QueryInput


class QuestionWorkflow(Protocol):
    """Coordinate retrieval, generation, and validation behind an application boundary."""

    def run(self, query: QueryInput) -> Awaitable[QueryExecution]: ...
