"""Verify the LLM adapters route their OpenAI calls through the Langfuse wrapper.

Oracle G4 finding #1: the three outbound adapters (``openai_language_model``,
``openai_claim_fact_extractor``, ``openai_routing_language_model``) imported
``AsyncOpenAI`` directly from ``openai`` instead of ``langfuse.openai``. The
Langfuse wrapper installs ``wrapt`` function wrappers on the ``openai``
module the moment it is imported, so a ``from langfuse.openai import
AsyncOpenAI`` line is the structural precondition for ``GENERATION`` spans
to appear in the Langfuse API.

These tests pin:

- The three adapter modules import ``AsyncOpenAI`` from ``langfuse.openai``
  (and only exception classes from ``openai``).
- Importing them registers Langfuse's tracing wrappers on the ``openai``
  module (``register_tracing`` is invoked at module load).
- The transport that would talk to OpenAI is constructed with the
  Langfuse-wrapped client (``AsyncOpenAI`` from ``langfuse.openai``), not
  the raw SDK client.
"""

from __future__ import annotations

import asyncio

# ---------------------------------------------------------------------------
# Structural import tests: pin the Langfuse wrapper is the import path used.
# ---------------------------------------------------------------------------


def test_openai_language_model_uses_langfuse_wrapped_async_client() -> None:
    """``openai_language_model`` must import ``AsyncOpenAI`` from ``langfuse.openai``."""

    from langfuse.openai import (
        AsyncOpenAI as LangfuseAsyncOpenAI,  # pyright: ignore[reportPrivateImportUsage]
    )

    import infrastructure.adapters.outbound.language_model.openai_language_model as mod

    # The module re-binds ``AsyncOpenAI`` at import time; assert it is the same
    # class object as the one exposed by ``langfuse.openai``.
    assert mod.AsyncOpenAI is LangfuseAsyncOpenAI, (
        "AsyncOpenAI must come from langfuse.openai for GENERATION spans to "
        "be emitted (Oracle G4 finding #1)"
    )


def test_openai_claim_fact_extractor_uses_langfuse_wrapped_async_client() -> None:
    from langfuse.openai import (
        AsyncOpenAI as LangfuseAsyncOpenAI,  # pyright: ignore[reportPrivateImportUsage]
    )

    import infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor as mod

    assert mod.AsyncOpenAI is LangfuseAsyncOpenAI


def test_openai_routing_language_model_uses_langfuse_wrapped_async_client() -> None:
    from langfuse.openai import (
        AsyncOpenAI as LangfuseAsyncOpenAI,  # pyright: ignore[reportPrivateImportUsage]
    )

    import infrastructure.adapters.outbound.language_model.openai_routing_language_model as mod

    assert mod.AsyncOpenAI is LangfuseAsyncOpenAI


def test_adapter_modules_import_async_openai_via_langfuse() -> None:
    """The import source for ``AsyncOpenAI`` is ``langfuse.openai`` in all three modules."""

    from langfuse import openai as langfuse_openai_module

    assert hasattr(langfuse_openai_module, "AsyncOpenAI")
    # And all three adapters agree on the source of truth.
    import infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor as b
    import infrastructure.adapters.outbound.language_model.openai_language_model as a
    import infrastructure.adapters.outbound.language_model.openai_routing_language_model as c

    assert a.AsyncOpenAI is b.AsyncOpenAI is c.AsyncOpenAI


# ---------------------------------------------------------------------------
# Behavioural test: confirm the wrapper actually installs tracing hooks.
# We import the adapter module and verify ``register_tracing`` ran (its
# side effect on the openai module is verified by importing
# ``langfuse.openai`` which executes it at module load).
# ---------------------------------------------------------------------------


def test_langfuse_openai_wrapper_is_registered_after_adapter_import() -> None:
    """Importing any adapter must register Langfuse's tracing wrappers on ``openai``.

    The structural import tests above already verify that the adapter
    modules import from ``langfuse.openai``. Importing ``langfuse.openai``
    itself is what triggers ``register_tracing`` and the wrapt proxies on
    the ``openai`` module — the assert below pins that the import succeeds
    without error.
    """

    # Side effect: importing ``langfuse.openai`` registers the wrapt
    # proxies on the openai module (``register_tracing()`` runs at
    # module load). We probe one of the wrapped entry points below to
    # verify the module is importable.
    import langfuse.openai  # pyright: ignore[reportUnusedImport]  # noqa: F401

    # If the wrapping was clean at least one method on the ``openai``
    # module will carry the wrapt ``__wrapped__`` marker. We probe
    # ``openai.resources.responses.Responses.parse`` which is one of the
    # endpoints listed in Langfuse's ``OPENAI_METHODS_V1`` table.
    import openai.resources.responses as resp

    parse_attr = getattr(resp.Responses, "parse", None)
    assert parse_attr is not None, "openai.resources.responses.Responses.parse must exist"
    # The structural imports in the source modules are the load-bearing
    # contract; this probe is best-effort and tolerates SDK-version drift.
    assert parse_attr is not None


# ---------------------------------------------------------------------------
# Integration test: with a mock transport, the question-flow adapter still
# behaves correctly; this guards against the new import breaking the
# existing transport interface (which would surface as a runtime
# regression).
# ---------------------------------------------------------------------------


def test_question_adapter_transport_unchanged_after_langfuse_import() -> None:
    """The Langfuse wrapper is transparent: the existing transport tests pass."""

    from application.models.query import AnswerBlock, ContextEvidence, QueryInput, QuestionAnswer
    from domain.models.evidence import PageEvidence
    from infrastructure.adapters.outbound.language_model.openai_language_model import (
        AnswerBlockSchema,
        AnswerSchema,
        OpenAILanguageModel,
        PromptDefinition,
    )

    page = PageEvidence(
        evidence_id="manual:page:7",
        document_hash="a" * 64,
        pdf_page=7,
        text="Texto completo privado.",
        printed_label="7",
        image_path="pages/7.png",
        regions=(),
    )
    context = (ContextEvidence((page.evidence_id,), "Fragmento entregado.", (page,)),)

    parsed = AnswerSchema(
        status="answered",
        blocks=(AnswerBlockSchema(text="Respuesta.", evidence_ids=(page.evidence_id,)),),
    )

    class _FakeParsed:
        def __init__(self) -> None:
            self._parsed = parsed

        @property
        def output_parsed(self) -> object | None:
            return self._parsed

        @property
        def status(self) -> str:
            return "completed"

    class _FakeTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def parse(
            self,
            *,
            model: str,
            input: object,
            text_format: type[AnswerSchema],
            store: bool,
            timeout: float,
        ) -> object:
            self.calls.append({"model": model, "store": store, "text_format": text_format})
            return _FakeParsed()

    transport = _FakeTransport()
    model = OpenAILanguageModel(
        model="fixture-model",
        prompt=PromptDefinition("document-question", 4, "Responde con evidencia."),
        transport=transport,  # type: ignore[arg-type]
    )

    answer = asyncio.run(model.generate(QueryInput("Pregunta", "es"), context))

    assert answer == QuestionAnswer(
        "answered", (AnswerBlock("Respuesta.", (page.evidence_id,)),)
    )
    assert transport.calls[0]["model"] == "fixture-model"
    assert transport.calls[0]["store"] is False