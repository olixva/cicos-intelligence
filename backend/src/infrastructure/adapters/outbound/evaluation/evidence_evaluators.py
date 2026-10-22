"""Deterministic evidence-reference and AND/OR coverage metrics."""

from collections.abc import Collection, Sequence

from infrastructure.adapters.outbound.evaluation.golden_schema import EvidenceRequirement


def citation_id_validity(
    *, cited: Collection[str], valid_pool: Collection[str], citations_required: bool = False
) -> float | None:
    """Measure cited identifier validity, independently of requirement coverage."""

    if not cited:
        return 0.0 if citations_required else None
    pool = set(valid_pool)
    return sum(1 for evidence_id in cited if evidence_id in pool) / len(cited)


def evidence_bundle_coverage(
    *, cited: Collection[str], requirements: Sequence[EvidenceRequirement]
) -> float | None:
    """Measure whether each golden evidence requirement has one complete bundle."""

    if not requirements:
        return None
    cited_ids = set(cited)
    covered = sum(
        1
        for requirement in requirements
        if any(set(bundle.all_of).issubset(cited_ids) for bundle in requirement.any_of)
    )
    return covered / len(requirements)
