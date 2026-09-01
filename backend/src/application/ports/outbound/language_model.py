"""Outbound contract for structured document-answer generation."""

from collections.abc import Awaitable, Sequence
from typing import Protocol

from application.models.query import ContextEvidence, QueryInput, QuestionAnswer


class LanguageModelError(RuntimeError):
    """A technical provider failure that must stay distinct from answer status."""


class MissingLanguageModelCredentialsError(LanguageModelError):
    """Provider credentials are absent at the moment a paid operation is requested."""


class ModelTimeoutError(LanguageModelError):
    """The provider did not produce a result within its configured limit."""


class ModelOutputError(LanguageModelError):
    """The provider returned no usable structured answer."""


class LanguageModel(Protocol):
    """Generate a typed answer from exactly the supplied context."""

    def generate(
        self, query: QueryInput, context: Sequence[ContextEvidence]
    ) -> Awaitable[QuestionAnswer]: ...
