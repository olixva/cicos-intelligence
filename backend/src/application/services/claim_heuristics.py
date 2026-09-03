"""Heurísticas de texto para detectar intención de relato de siniestro.

Módulo compartido por ``routing.resolve_query`` y por
``input_guardrails.guardrail_message``. Cuando el usuario envía un
texto que parece un relato de siniestro (alcance, colisión, semáforo
y maniobra, etc.) pero incluye palabras incidentales que el guardrail
o el router barato (gpt-5.6-luna) podrían malinterpretar
(``tiempo`` en "no consigue detenerse a tiempo", ``hora``,
``parte`` en "parte amistoso"), el cortafuegos detecta el contexto
real y deja pasar el texto al flujo de análisis.

Se usa dos veces:
- En el guardrail (``input_guardrails.py``): si el texto tiene
  vocabulario de relato de siniestro, NO se bloquea por
  ``tiempo/clima``.
- En el router (``routing.py``): si el router clasifica como
  ``clarification_required`` o ``question`` pero el texto tiene
  vocabulario de relato, se fuerza ``claim``.

Umbral: 2+ matches. Marcadores sueltos (p. ej. un texto que sólo
contiene "siniestro" una vez) no overridean — son falsos positivos
demasiado fáciles.
"""

from __future__ import annotations

import re

# Marcadores típicos de relato de siniestro. 15 patrones para cubrir
# la variedad de redacción: vehículos etiquetados, vocabulario de
# colisión, semáforo, maniobra, D.A.A., etc.
_CLAIM_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bveh[ií]culo\s+[a-z]\b", re.IGNORECASE),
    re.compile(r"\bveh[ií]culos?\s+[a-z]\s+y\s+[a-z]\b", re.IGNORECASE),
    re.compile(r"\bsiniestro\b", re.IGNORECASE),
    re.compile(r"\bcolisi[oó]n\b", re.IGNORECASE),
    re.compile(r"\bchoc[oóaáe]+\b", re.IGNORECASE),
    re.compile(r"\bD\.\s?A\.\s?A\.\b", re.IGNORECASE),
    re.compile(r"\bmaniobra\b", re.IGNORECASE),
    re.compile(r"\bsem[aá]foro\b", re.IGNORECASE),
    re.compile(r"\bculpable\b", re.IGNORECASE),
    re.compile(r"\bfren[oóaá]\b", re.IGNORECASE),
    re.compile(r"\btrasera?\b", re.IGNORECASE),
    re.compile(r"\bmatr[ií]cula\b", re.IGNORECASE),
    re.compile(r"\bparte\s+amistoso\b", re.IGNORECASE),
    re.compile(r"\balcance\b", re.IGNORECASE),
    re.compile(r"\bimpacto\b", re.IGNORECASE),
)

_CLAIM_TEXT_THRESHOLD = 2


def looks_like_claim_text(text: str) -> bool:
    """True si el texto tiene al menos ``_CLAIM_TEXT_THRESHOLD`` marcadores
    de relato de siniestro. Sirve para detectar casos donde palabras
    incidentales (``tiempo``, ``hora``, ``parte``, etc.) aparecen en un
    contexto claramente de colisión entre vehículos y no deben
    interpretarse como pregunta meteorológica o administrativa."""
    return (
        sum(1 for pattern in _CLAIM_TEXT_PATTERNS if pattern.search(text)) >= _CLAIM_TEXT_THRESHOLD
    )
