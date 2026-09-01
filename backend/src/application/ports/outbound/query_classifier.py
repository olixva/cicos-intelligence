"""Outbound port that classifies a query into a closed routing decision."""

from collections.abc import Awaitable
from typing import Protocol

from application.models.query import QueryInput
from domain.models.routing import RouteClassification


class QueryClassifier(Protocol):
    """Produce exactly one closed-enum routing decision per query."""

    def classify(self, query: QueryInput) -> Awaitable[RouteClassification]: ...
