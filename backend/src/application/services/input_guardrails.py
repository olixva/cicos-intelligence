"""Deterministic safety and scope checks before expensive document workflows."""

import re

from application.services.claim_heuristics import looks_like_claim_text

_WEATHER = re.compile(r"\b(tiempo|clima|temperatura|llueve|lloverá|llovera)\b", re.IGNORECASE)
_INSULT = re.compile(
    r"\b(inútil|inutil|imbécil|imbecil|idiota|estúpido|estupido|tonto)\b", re.IGNORECASE
)


def guardrail_message(text: str) -> str | None:
    """Return a user-facing refusal for clearly unsupported or abusive input.

    El chequeo de clima/tiempo (``_WEATHER``) se salta cuando el texto
    contiene vocabulario claro de relato de siniestro: la heurística
    compartida ``looks_like_claim_text`` detecta que 'no consigue
    detenerse a tiempo' o 'parte amistoso a las dos de la tarde' son
    contexto de colisión, no preguntas meteorológicas. Sin este
    cortafuegos, un alcance trasero claro se quedaba bloqueado por
    contener la palabra 'tiempo' (caso real reportado).
    """
    if _INSULT.search(text):
        return (
            "No puedo continuar con insultos. Mantengamos una conversación respetuosa "
            "sobre CIDE/ASCIDE/CICOS."
        )
    if _WEATHER.search(text) and not looks_like_claim_text(text):
        return (
            "Sólo puedo responder sobre el manual CIDE/ASCIDE/CICOS y los siniestros que "
            "cubre; no puedo informar del tiempo."
        )
    return None
