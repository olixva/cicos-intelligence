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


def build_demo_router(path: Path = Path("data/evaluation/golden/development.jsonl")) -> APIRouter:
    router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

    def get_cases() -> list[DemoCase]:
        if not path.is_file():
            raise HTTPException(status_code=503, detail="Los casos de demo no están disponibles.")
        cases: list[DemoCase] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    raw = json.loads(line)
                    if not isinstance(raw, dict):
                        raise ValueError("case must be an object")
                    raw_object = cast(dict[str, object], raw)
                    safe: dict[str, object] = {
                        key: raw_object[key] for key in DemoCase.model_fields if key in raw_object
                    }
                    cases.append(DemoCase.model_validate(safe))
        except (OSError, ValueError, TypeError) as error:
            raise HTTPException(
                status_code=503, detail="El catálogo de demo no es válido."
            ) from error
        if not cases:
            raise HTTPException(status_code=503, detail="El catálogo de demo está vacío.")
        return cases

    router.add_api_route("/cases", get_cases, methods=["GET"], response_model=list[DemoCase])
    return router
