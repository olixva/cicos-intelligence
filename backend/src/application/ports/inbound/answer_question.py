"""Inbound port for grounded document questions."""

from collections.abc import Awaitable
from typing import Protocol

from application.models.query import QueryExecution, QueryInput


class AnswerQuestion(Protocol):
    """Answer one question using only registered document evidence."""

    def execute(self, query: QueryInput) -> Awaitable[QueryExecution]: ...
