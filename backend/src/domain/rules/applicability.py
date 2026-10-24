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
    accident_location_in_scope: bool | None = None
    vehicles_registered_in_spain: bool | None = None
    insurer_adhered: bool | None = None
    vehicles_habitually_parked_in_spain: bool | None = None


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
    """Apply the source-grounded territory, vehicle, and collision gates."""

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

    scope_reasons, scope_missing, scope_status = _assess_convention_scope(facts)
    if scope_status == "not_applicable":
        return ApplicabilityAssessment("not_applicable", scope_reasons, (), evidence_ids)
    if facts.vehicle_count is None:
        missing.append("Confirmar cuántos vehículos intervinieron.")
    if facts.direct_collision is None:
        missing.append("Confirmar si existió colisión directa entre los dos vehículos.")
    missing.extend(scope_missing)
    if facts.vehicle_count == 2 and facts.direct_collision is False:
        reasons.append("Los Convenios requieren colisión directa entre los dos vehículos.")
        return ApplicabilityAssessment("not_applicable", tuple(reasons), (), evidence_ids)
    if missing:
        return ApplicabilityAssessment("undetermined", (), tuple(missing), evidence_ids)
    return ApplicabilityAssessment("applicable", (), (), evidence_ids)


def _assess_convention_scope(
    facts: ApplicabilityFacts,
) -> tuple[
    tuple[str, ...], tuple[str, ...], Literal["applicable", "not_applicable", "undetermined"]
]:
    """Evaluate the scope disjunction without treating unknown facts as false.

    The source requires an in-scope accident location and either the Spanish
    registration/adhering-insurer basis or habitual parking in Spain. If the
    place is outside the listed geography while habitual parking is asserted,
    the wording needs domain review; keep it undetermined instead of guessing.
    """
    registered_basis: bool | None
    if facts.vehicles_registered_in_spain is False or facts.insurer_adhered is False:
        registered_basis = False
    elif facts.vehicles_registered_in_spain is True and facts.insurer_adhered is True:
        registered_basis = True
    else:
        registered_basis = None

    habitual = facts.vehicles_habitually_parked_in_spain
    location = facts.accident_location_in_scope
    if location is False:
        if habitual is True:
            return (
                (),
                (
                    "Confirmar el alcance territorial de un vehículo habitualmente estacionado "
                    "en España cuando el accidente ocurre fuera del EEE o del Sistema de "
                    "Certificado Internacional.",
                ),
                "undetermined",
            )
        if habitual is False:
            return (
                (
                    "El accidente y los vehículos declarados quedan fuera del ámbito territorial "
                    "del Convenio.",
                ),
                (),
                "not_applicable",
            )

    if location is True:
        if registered_basis is True or habitual is True:
            return (), (), "applicable"
        if registered_basis is False and habitual is False:
            return (
                (
                    "Los vehículos no cumplen los requisitos de matrícula española y seguro con "
                    "entidad adherida, ni tienen estacionamiento habitual en España.",
                ),
                (),
                "not_applicable",
            )

    missing: list[str] = []
    if location is None:
        missing.append(
            "Confirmar si el accidente ocurrió en el EEE o en un país adherido al Sistema de "
            "Certificado Internacional."
        )
    if registered_basis is None:
        if facts.vehicles_registered_in_spain is None:
            missing.append("Confirmar si los vehículos están matriculados en España.")
        if facts.insurer_adhered is None:
            missing.append("Confirmar si sus aseguradoras están adheridas al Convenio.")
    if habitual is None:
        missing.append("Confirmar si algún vehículo tiene estacionamiento habitual en España.")
    return (), tuple(missing), "undetermined"
