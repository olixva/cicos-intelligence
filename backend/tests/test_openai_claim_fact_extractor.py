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
