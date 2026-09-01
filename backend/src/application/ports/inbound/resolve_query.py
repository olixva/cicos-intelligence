"""Inbound port for the closed-enum auto router."""

from collections.abc import Awaitable
from typing import Protocol

from application.models.query import QueryInput
from domain.models.routing import RouteExecution


class ResolveQuery(Protocol):
    """Dispatch one user query to exactly one of the existing flows."""

    def execute(self, query: QueryInput) -> Awaitable[RouteExecution]: ...
