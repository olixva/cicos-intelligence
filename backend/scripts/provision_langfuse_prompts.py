"""Create the numbered Langfuse prompts the API needs, idempotently.

Provisioning these was a manual UI step documented only in prose, so a
clean environment could bring every service up and still fail at
startup with 'Prompt not found'. This script closes that gap: it is
safe to re-run, and it never overwrites an existing version.
"""

import argparse
import os
import sys

from langfuse import Langfuse

QUESTION_PROMPT = """\
Eres un asistente que responde EXCLUSIVAMENTE a partir del contexto suministrado, extraído del \
manual CIDE/ASCIDE/CICOS (edición de noviembre de 2004). No es derecho vigente y no debes \
presentarlo como tal.

Reglas obligatorias:
1. Usa únicamente el contexto suministrado. Si no basta, declara evidencia insuficiente en lugar \
de completar con conocimiento general.
2. Cada bloque de respuesta debe citar los evidence_ids que lo sostienen. En un bloque que se \
apoye en varias páginas, cita TODOS sus evidence_ids o ninguno; nunca un subconjunto.
3. No inventes identificadores de evidencia. Sólo puedes citar los que aparecen en el contexto.
4. Distingue respuesta completa, parcial, evidencia insuficiente y consulta fuera de alcance.
5. Indica explícitamente qué no has podido establecer.
6. Responde en el idioma de la consulta, aunque el manual esté en español.

Devuelve el esquema estructurado solicitado por la aplicación."""

ROUTER_PROMPT = """\
Clasifica la INTENCIÓN de la entrada del usuario en exactamente una de estas etiquetas:

- "question": pregunta sobre el contenido, las reglas o los criterios del manual CIDE/ASCIDE/CICOS.
- "claim": relato de un accidente, real o hipotético, sobre el que se pide aplicar los criterios. \
Pedir además que se expliquen las reglas SIGUE siendo "claim".
- "clarification_required": la intención es genuinamente ambigua.

Clasifica la intención, no la presencia de palabras concretas. Un relato con datos ausentes puede \
tener intención clara y debe ir a "claim": el análisis resolverá esa insuficiencia. No respondas \
al contenido ni reescribas los hechos: sólo clasifica."""

PROMPTS = {
    os.environ.get("ALLIANZ_QUESTION_PROMPT_NAME", "document-question"): QUESTION_PROMPT,
    os.environ.get("ALLIANZ_ROUTER_PROMPT_NAME", "auto-router"): ROUTER_PROMPT,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", type=int, default=1, help="version expected by the API")
    args = parser.parse_args()

    client = Langfuse()
    exit_code = 0
    for name, content in PROMPTS.items():
        try:
            existing = client.get_prompt(name, version=args.version, type="text")
        except Exception:
            existing = None
        if existing is not None:
            print(f"{name} v{args.version}: ya existe, no se toca")
            continue
        client.create_prompt(name=name, prompt=content, type="text", labels=["production"])
        try:
            created = client.get_prompt(name, version=args.version, type="text")
        except Exception as error:  # pragma: no cover - surfaced to the operator
            print(f"{name}: creado pero no recuperable en v{args.version}: {error}")
            exit_code = 1
            continue
        print(f"{name} v{created.version}: creado")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
