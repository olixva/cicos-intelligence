# Arquitectura técnica — Allianz RAG

## Propósito y límites

Demo local de recuperación aumentada sobre `Manual-cide-ascide-y-cicos.pdf` (111 páginas, noviembre de 2004). El manual no es derecho vigente. El sistema responde sobre su contenido y analiza aplicabilidad convencional de relatos, sin emitir responsabilidad civil general ni inferir circunstancias D.A.A. ausentes.

## Arquitectura

El backend Python/FastAPI mantiene una separación hexagonal: rutas HTTP y CLI entran por adaptadores; los casos de uso coordinan puertos; los adaptadores de salida conectan Qdrant, OpenAI, Langfuse y el sistema de ficheros. React/Vite consume exclusivamente OpenAPI y SSE; no contiene reglas ni secretos.

Hay dos recorridos LangGraph. El documental recupera evidencia, genera y valida una respuesta sustentada. El de siniestros extrae hechos atribuidos, recupera criterios, aplica reglas deterministas, explica y valida. El modo automático clasifica una única intención; los modos explícitos no pasan por el router.

## Evidencia, reglas y observabilidad

La ingesta publica artefactos versionados con hash de fuente y páginas físicas. Qdrant usa recuperación densa, BM25 español y RRF configurables. Las citas fijan documento, hash y página; el visor sólo resalta regiones verificadas.

La matriz CIDE requiere dos circunstancias D.A.A. explícitas y attestation firmada. Las etiquetas D.A.A. proceden de un formulario externo al manual. Langfuse registra trazas y prompts; la evaluación usa su integración nativa y Ragas cuando exista un golden revisado.

## Estado y retos

Pyright estricto, lint y formato están limpios; la suite backend ejecutó 400 pruebas correctas y una omitida, aunque el proceso conserva un teardown `Error 134` de torch/libc++abi. Frontend y OpenAPI pasaron sus gates en el corte. Aún faltan `session_id` hasta Langfuse, casos públicos de demo, golden revisado, publicación Docling y evaluación humana. No se declaran métricas ni resultados de evaluación inexistentes.
