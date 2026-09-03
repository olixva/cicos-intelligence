"""Read-only demo cases served without exposing evaluation annotations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict


class DemoCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    text: str
    language: Literal["es", "en"]
    expected_intent: Literal["question", "claim"]


#: Los ejemplos que la interfaz ofrece, en este orden. El conjunto de
#: desarrollo crece con la curación del golden set, pero la demo no debe
#: crecer con él: se eligen casos en castellano que muestran dos consultas
#: respondibles, un siniestro que necesita información adicional, uno no
#: aplicable y otro resuelto. Un identificador que no exista en el conjunto se
#: ignora en silencio: el catálogo de demo nunca debe tumbar la interfaz.
DEFAULT_DEMO_CASE_IDS: tuple[str, ...] = (
    "consulta-es-01-alcoholemia",
    "consulta-synth-21-atestado-ascide-cierra",
    "siniestro-synth-12-b9-marcha-atras",
    "accident-02-pile-up-es",
    "accident-04-lane-change-es",
)


#: La demo necesita mostrar un relato completo que abra una entrevista breve.
#: El caso evaluado mantiene sus anotaciones originales; sólo su presentación
#: pública concreta que falta confirmar la colisión directa.
DEMO_TEXT_OVERRIDES: dict[str, str] = {
    "siniestro-synth-12-b9-marcha-atras": (
        "En una autovía, el vehículo A inició un cambio de carril hacia la izquierda mientras "
        "el vehículo B circulaba correctamente por ese carril. Ambos conductores coinciden en "
        "que A hacía la maniobra y discrepan sobre quién tenía prioridad. El relato no aclara "
        "si los vehículos llegaron a colisionar directamente."
    ),
}


def build_demo_router(
    path: Path = Path("data/evaluation/golden/development.jsonl"),
    case_ids: tuple[str, ...] = DEFAULT_DEMO_CASE_IDS,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

    def get_cases() -> list[DemoCase]:
        if not path.is_file():
            raise HTTPException(status_code=503, detail="Los casos de demo no están disponibles.")
        available: dict[str, DemoCase] = {}
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    raw = json.loads(line)
                    if not isinstance(raw, dict):
                        raise ValueError("case must be an object")
                    raw_object = cast(dict[str, object], raw)
                    safe = _extract_safe_fields(raw_object)
                    case = DemoCase.model_validate(safe)
                    if text := DEMO_TEXT_OVERRIDES.get(case.case_id):
                        case = case.model_copy(update={"text": text})
                    available[case.case_id] = case
        except (OSError, ValueError, TypeError) as error:
            raise HTTPException(
                status_code=503, detail="El catálogo de demo no es válido."
            ) from error
        # Sin selección explícita se sirve el conjunto entero, que es lo que
        # esperan las pruebas de contrato; con ella, sólo los casos elegidos
        # y en el orden pedido.
        cases: list[DemoCase] = (
            [available[case_id] for case_id in case_ids if case_id in available]
            if case_ids
            else list(available.values())
        )
        if not cases:
            raise HTTPException(status_code=503, detail="El catálogo de demo está vacío.")
        return cases

    router.add_api_route("/cases", get_cases, methods=["GET"], response_model=list[DemoCase])
    return router


def _extract_safe_fields(raw_object: dict[str, object]) -> dict[str, object]:
    """Pull only the public input fields out of a full golden dataset item.

    Never forwards ``expected_output`` (references, requirements, evidence) or review
    metadata: the demo catalogue exposes development-set inputs, not evaluation
    annotations.
    """
    golden_input = raw_object.get("input")
    metadata = raw_object.get("metadata")
    if isinstance(golden_input, dict) and isinstance(metadata, dict):
        typed_input = cast(dict[str, object], golden_input)
        typed_metadata = cast(dict[str, object], metadata)
        return {
            "case_id": typed_metadata.get("case_id"),
            "text": typed_input.get("text"),
            "language": typed_input.get("language"),
            "expected_intent": typed_metadata.get("expected_intent"),
        }
    return {key: raw_object[key] for key in DemoCase.model_fields if key in raw_object}
