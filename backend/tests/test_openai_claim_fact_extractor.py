"""OpenAI claim extractor sends only the original claim and maps typed output."""

import asyncio
from dataclasses import dataclass

from domain.models.claim import ClaimInput


@dataclass
class _Response:
    output_parsed: object | None
    status: str = "completed"


class _Transport:
    captured_input: object | None = None

    async def parse(self, **kwargs: object) -> _Response:
        self.captured_input = kwargs["input"]
        from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
            ClaimExtractionSchema,
            ClaimFactSchema,
        )

        return _Response(
            ClaimExtractionSchema(
                party_ids=("A", "B"),
                facts=(
                    ClaimFactSchema(
                        name="vehicle_count",
                        value="3",
                        asserted_by=None,
                        source_text="intervienen tres vehículos",
                    ),
                ),
            )
        )


def test_claim_extraction_to_application_drops_whitespace_only_facts_and_questions() -> None:
    """El proveedor a veces emite ``name`` o ``source_text`` whitespace-only en
    un fact, e ``id``/``prompt``/``reason`` whitespace-only en una pregunta. El
    invariante de no-vacío lo aplica el dataclass (`` `` ``.strip()`` `` `` no
    vacío), no Pydantic ``min_length=1``. El adaptador debe descartar los
    inválidos antes de cruzar al modelo de aplicación en lugar de propagar
    ``ValueError`` que tira la request con 500."""

    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        ClaimExtractionSchema,
        ClaimFactSchema,
        InterviewQuestionSchema,
    )

    parsed = ClaimExtractionSchema(
        party_ids=("A", "B"),
        facts=(
            ClaimFactSchema(
                name="vehicle_count",
                value="2",
                asserted_by=None,
                source_text="dos vehículos",
            ),
            ClaimFactSchema(
                name="   ",  # whitespace-only, Pydantic min_length=1 pasa
                value="x",
                asserted_by=None,
                source_text="  \n  ",
            ),
            ClaimFactSchema(
                name="direct_collision",
                value=None,
                asserted_by=None,
                source_text="   ",  # whitespace-only — Pydantic pasa, dataclass rechaza
            ),
        ),
        interview_status="ask",
        questions=(
            InterviewQuestionSchema(
                id="q1",
                prompt="¿quién circulaba?",
                reason="aporta la norma",
            ),
InterviewQuestionSchema(
                    id="  ",
                    prompt="\t\n",
                    reason=" ",
                ),
        ),
    )

    application = parsed.to_application()

    assert len(application.facts) == 1
    assert application.facts[0].name == "vehicle_count"

    assert application.interview_plan.status == "ask"
    assert len(application.interview_plan.questions) == 1
    assert application.interview_plan.questions[0].id == "q1"


def test_claim_extractor_uses_structured_output_and_never_adds_manual_context() -> None:
    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        OpenAIClaimFactExtractor,
    )

    transport = _Transport()
    result = asyncio.run(
        OpenAIClaimFactExtractor(model="gpt-4.1-mini", transport=transport).extract(
            ClaimInput("A informa que intervienen tres vehículos.", clarifications=("B discrepa.",))
        )
    )

    assert result.party_ids == ("A", "B")
    assert result.facts[0].name == "vehicle_count"
    rendered = str(transport.captured_input)
    assert "tres vehículos" in rendered
    assert "context" not in rendered.lower()


def test_claim_extractor_instructs_the_model_to_return_a_bounded_interview_plan() -> None:
    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        _messages,
    )

    rendered = str(_messages(ClaimInput("A y B chocaron.")))

    assert "plan de entrevista" in rendered.lower()
    assert "no repitas" in rendered.lower()
    assert "matriculación" in rendered.lower()
