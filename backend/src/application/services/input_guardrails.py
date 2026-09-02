"""Deterministic safety and scope checks before expensive document workflows."""

import re

_WEATHER = re.compile(r"\b(tiempo|clima|temperatura|llueve|lloverá|llovera)\b", re.IGNORECASE)
_INSULT = re.compile(
    r"\b(inútil|inutil|imbécil|imbecil|idiota|estúpido|estupido|tonto)\b", re.IGNORECASE
)


def guardrail_message(text: str) -> str | None:
    """Return a user-facing refusal for clearly unsupported or abusive input."""
    if _INSULT.search(text):
        return "No puedo continuar con insultos. Mantengamos una conversación respetuosa sobre CIDE/ASCIDE/CICOS."
    if _WEATHER.search(text):
        return "Sólo puedo responder sobre el manual CIDE/ASCIDE/CICOS y los siniestros que cubre; no puedo informar del tiempo."
    return None
