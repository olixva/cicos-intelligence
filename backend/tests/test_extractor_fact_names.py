"""The extractor must be asked for exactly the facts the ruleset reads.

The prompt used to hardcode four names while the signed ruleset consulted
more. The alcohol rule, whose whole purpose is to stop a wrong exclusion,
could never fire because nothing ever extracted `driver_under_influence`.
"""

from pathlib import Path

from domain.rules.ruleset import fact_names
from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
    OpenAIClaimFactExtractor,
    _messages,  # pyright: ignore[reportPrivateUsage]
)
from infrastructure.config.rules_artifacts import load_rules_artifacts

_RULES = load_rules_artifacts(Path(__file__).resolve().parents[2] / "data" / "rules").rules


def test_fact_names_are_derived_from_the_rules_that_read_them() -> None:
    names = fact_names(_RULES)
    assert "vehicle_count" in names
    assert "chain_collision" in names
    # La regla de no exclusión por alcoholemia lee este hecho.
    assert "driver_under_influence" in names


def test_the_prompt_asks_for_every_fact_the_ruleset_consults() -> None:
    from domain.models.claim import ClaimInput

    extractor = OpenAIClaimFactExtractor(model="m", fact_names=fact_names(_RULES))
    developer = _messages(ClaimInput("relato"), extractor.fact_names)[0]["content"]
    for name in fact_names(_RULES):
        assert name in developer, f"the prompt never asks for {name}"


def test_the_prompt_still_forbids_inventing_values() -> None:
    from domain.models.claim import ClaimInput

    developer = _messages(ClaimInput("relato"), ("vehicle_count",))[0]["content"]
    assert "no inventes" in developer.lower()
