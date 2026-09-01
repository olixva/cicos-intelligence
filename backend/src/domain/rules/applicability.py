"""Conservative CIDE/ASCIDE applicability rules over explicitly extracted facts."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ApplicabilityFacts:
    """Only confirmed prerequisites; unknowns are represented by ``None``."""

    vehicle_count: int | None
    direct_collision: bool | None
    third_vehicle_identified: bool | None = None
    chain_collision: bool | None = None


@dataclass(frozen=True, slots=True)
class ApplicabilityAssessment:
    """Three-state applicability with explicit reasons and source evidence."""

    status: Literal["applicable", "not_applicable", "undetermined"]
    reasons: tuple[str, ...]
    missing_information: tuple[str, ...]
    evidence_ids: tuple[str, ...]


def assess_applicability(
    facts: ApplicabilityFacts, *, evidence_ids: tuple[str, ...]
) -> ApplicabilityAssessment:
    """Apply only the verified two-vehicle/direct-collision gate from the manual."""

    if not evidence_ids or any(not evidence_id.strip() for evidence_id in evidence_ids):
        raise ValueError("applicability evidence identifiers must be nonempty")
    reasons: list[str] = []
    missing: list[str] = []
    if facts.vehicle_count is not None and facts.vehicle_count != 2:
        reasons.append("Los Convenios requieren la intervención de exactamente dos vehículos.")
    if facts.third_vehicle_identified is True:
        reasons.append("Hay un tercer vehículo identificado que interviene en el accidente.")
    if facts.chain_collision is True:
        reasons.append("La colisión en cadena no se tramita por Convenio.")
    if reasons:
        return ApplicabilityAssessment("not_applicable", tuple(reasons), (), evidence_ids)
    if facts.vehicle_count is None:
        missing.append("Confirmar cuántos vehículos intervinieron.")
    if facts.direct_collision is None:
        missing.append("Confirmar si existió colisión directa entre los dos vehículos.")
    if facts.vehicle_count == 2 and facts.direct_collision is False:
        reasons.append("Los Convenios requieren colisión directa entre los dos vehículos.")
        return ApplicabilityAssessment("not_applicable", tuple(reasons), (), evidence_ids)
    if missing:
        return ApplicabilityAssessment("undetermined", (), tuple(missing), evidence_ids)
    return ApplicabilityAssessment("applicable", (), (), evidence_ids)
