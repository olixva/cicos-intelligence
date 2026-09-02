# Arquitectura — Allianz CICOS Claims Intelligence

Recreado el 2026-09-02 a partir del código verificado (una sesión anterior perdió, sin
commitear, la versión previa de este documento). Describe el sistema tal y como está
implementado en este corte, no un plan.

## 1. Qué resuelve

Un asistente RAG local sobre el manual CIDE/ASCIDE/CICOS (111 páginas, edición de noviembre
de 2004) que:

- **Responde preguntas** sobre el contenido del manual con citas verificables al PDF original.
- **Analiza relatos de accidentes**: extrae hechos, comprueba aplicabilidad del Convenio,
  aplica reglas deterministas y devuelve una conclusión resuelta, condicionada o indeterminada
  — nunca inventada.
- **Enruta automáticamente** entre ambos recorridos con un clasificador LLM, conservando los
  dos modos explícitos.

## 2. Arquitectura hexagonal

```
backend/src/
  domain/         modelos y reglas puras (sin FastAPI, sin LangGraph, sin SDKs)
  application/    puertos de entrada/salida, casos de uso, servicios
  infrastructure/ adaptadores: FastAPI, LangGraph, OpenAI, Qdrant, Langfuse, CLI
  bootstrap.py    composición de dependencias
```

`domain` no importa nada de `application` ni `infrastructure`. `application` define los
puertos que `infrastructure` implementa. Un mismo nombre funcional conecta el puerto con el
directorio de su adaptador (p. ej. `application/ports/outbound/claim_workflow.py` ↔
`infrastructure/adapters/outbound/claim_workflow/`).

### Frontera de LangGraph

Los casos de uso delegan la coordinación a tres workflows LangGraph (`question_workflow`,
`claim_workflow`, `query_workflow` para el modo Automático). Los grafos mantienen estado
técnico y llaman a servicios de aplicación y reglas de dominio; `domain` y `application` nunca
importan LangGraph. El grafo automático invoca los casos de uso documental/siniestros por sus
puertos de entrada, sin recursión.

## 3. Los tres modos

| Modo | Recorrido LangGraph | Endpoint |
|---|---|---|
| Automático | `classify → (retrieve \| extract_facts) ` | `POST /api/v1/queries/resolve` |
| Consultar manual | `retrieve → generate → validate` | `POST /api/v1/questions/answer` |
| Analizar siniestro | `extract_facts → retrieve_criteria → apply_rules → explain → validate` | `POST /api/v1/claims/analyze` |

El router usa salida estructurada cerrada (`question` / `claim` / `clarification_required`),
recibe la entrada del usuario sin reescribirla y nunca ve etiquetas ni respuestas esperadas.
Los modos explícitos omiten el router por completo.

## 4. Ingesta y evidencias

Dos parsers publicados para el documento verificado (SHA-256
`b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`):

- **`pypdf-6.16.2`** (baseline): texto plano, chunking de tamaño fijo con solapamiento.
  Activo en el índice Qdrant de demo (118 fragmentos).
- **`docling-2.124.0-pdfium-5.13.0-rapidocr-latin-torch-r2-…`** (estructurado): conserva
  regiones/bounding boxes verificadas por página (las 111), Markdown y JSON originales de
  Docling, y diagnósticos por página (tablas no verificadas, OCR ausente/incompleto). Publicado
  también en Qdrant con chunking por secciones (109 fragmentos), pero **no activado** como
  índice de demo: la spec exige elegir la configuración por evaluación, no por disponibilidad.

Cada elemento de evidencia conserva documento, hash, página física del PDF, etiqueta impresa
independiente cuando se conoce, texto y/o imagen, tipo de contenido y versión de extracción.
Los IDs de evidencia (`sha256:<hash>:page:<n>`) identifican el documento original, no un
chunk dependiente del parser.

## 5. Motor de reglas — qué es determinista y qué no

`data/rules/ruleset.v1.json` fija 14 reglas firmadas (con `reviewer_id`, evidencia y
descripción), derivadas del manual y revisadas por el responsable del proyecto. El evaluador
(`domain/rules/ruleset.py`) ejecuta un lenguaje de predicados cerrado (`all`/`any`,
`eq`/`ne`/`is_true`/`is_false`) sobre los hechos que un extractor LLM saca del relato — nunca
al revés: una regla sin condición verificable (`applies_when`) se reporta honestamente como
`insufficient_data`, nunca como si hubiera casado.

De las 14 reglas:

- **5 son la puerta de aplicabilidad y excepciones** (dos vehículos, colisión directa, tercero
  identificado, colisión en cadena, alcohol no excluye) — completamente machine-checkable desde
  el inicio.
- Cada regla declara además **a qué convenio pertenece** (`convention`), leído del
  artefacto y nunca inferido de su `kind`: `manoeuvre` cubre tanto las normas
  subsidiarias ASCIDE como el criterio CIDE de apertura de puertas. Una regla que no
  lo declara resuelve sin nombrar convenio en lugar de suponer uno.
- **1 norma de maniobra subsidiaria ASCIDE — `ascide-b10-lane-change`** (cambio de carril
  reconocido por ambas partes + disparidad de versiones ⇒ culpable quien cambia de carril) se
  completó en este corte: tiene condición verificable y su resultado alimenta la decisión final
  (`decision="resolved"`, convenio leído del artefacto) cuando casa de forma inequívoca.
- **La tabla de culpabilidad CIDE (18×18, `cide-matrix-lookup`) está conectada al flujo.**
  Las 324 celdas estaban transcritas y atestadas desde antes; `decide_from_daa_matrix`
  (`domain/rules/cide_matrix.py`) es lo que faltaba: distingue si la tabla atribuye
  responsabilidad, si la celda es un «-» sin atribución, si una de las **cuatro observaciones
  impresas** bajo la tabla (pág. 101) está pendiente de su hecho decisorio, o si esa
  observación se cumple y retira la atribución. Las observaciones se declaran de forma
  estructurada en el artefacto firmado (`applies_to`/`exception_fact`/`exception_actor`/
  `liable_unless_exception`), nunca en código — una celda con asterisco sin observación
  anotada simplemente no decide. La regla del proyecto se mantiene intacta: las casillas
  A0–A17 sólo entran si el relato las declara explícitamente; nunca se infieren de una
  narración de la maniobra.
- **`ascide-b5`, `ascide-b6`, `ascide-b9` y `cide-door-opening` también están conectadas.**
  Mismo patrón que `ascide-b10`: predicado sobre hechos declarados explícitamente, convenio
  leído del artefacto. `ascide-b6` respeta la excepción que el manual remite a otro apartado
  («Incorporación a la circulación», no verificado en este corte): mientras esa remisión no
  se descarte explícitamente, la regla se abstiene en vez de decidir igual.
- **Sólo `ascide-b11-roundabout` sigue sin condición verificable** (más `convention-scope`,
  que no es una regla de decisión sino el ámbito geográfico). A diferencia de las demás, su
  excepción no retira una atribución: la sustituye por otra («culpable quien accede a la
  rotonda, salvo que ambos tengan daños laterales no angulares, en cuyo caso culpable el de
  daños en el lateral derecho»), lo que exige una segunda regla en el artefacto con su propio
  `applies_when` mutuamente excluyente — un cambio más sustancial que rellenar un predicado
  existente, pendiente.
- **El planificador de entrevista del LLM tenía dos confusiones sistemáticas**, corregidas en
  el prompt: trataba «el relato declara que un dato no consta» como un vacío por preguntar
  (rompía `cide-door-opening`, cuya condición de activación es esa ausencia declarada), y
  trataba «disparidad de versiones» como caso irresoluble (rompía las tres normas subsidiarias
  que existen justamente para resolverla). El planificador decide en la misma llamada que
  extrae los hechos, antes de que `apply_rules` sepa si una norma determinista cubre el caso.

Esta separación es deliberada: **una celda o regla no verificada no produce una decisión
determinista.** El generador no puede convertir un resultado indeterminado en definitivo.

## 6. Golden set y evaluación

El conjunto de desarrollo tiene **10 casos** en `data/evaluation/golden/development.jsonl`
con el schema completo: los 5 de la entrevista técnica y 5 en castellano que cubren un
siniestro que se resuelve, uno en el que abstenerse es lo correcto, dos consultas
documentales y una pregunta fuera de alcance.

Cada caso lleva `input`, `expected_output` y `metadata`, y cita evidencia real del manual
para cada requisito y prohibición. La referencia se construyó con una **revisión de tres
pasos por IA** (resolución independiente ciega → revisión adversarial independiente →
adjudicación), documentada caso a caso — **no** una revisión de un experto humano del
dominio, limitación declarada explícitamente en los metadatos de cada caso. Una segunda
pasada adversarial sobre el lote completo corrigió paquetes de evidencia demasiado
estrictos, requisitos sin cita que los sostuviera y la omisión del orden de prioridad
ASCIDE ante versiones contradictorias (las normas subsidiarias son su quinto criterio,
pág. 111).

Resultado de esa revisión, contrastado contra el manual página a página: de los cinco casos
del enunciado sólo `accident-04-lane-change` se resuelve de forma determinista con los datos
del relato (norma b.10); los otros cuatro caen fuera del Convenio o quedan
condicionados/indeterminados por diseño — abstenerse con criterio es la respuesta correcta
ahí, tal como exige la spec. Verificado ejecutando la aplicación: los cinco casos de demo
devuelven exactamente lo que dice el golden, incluida la abstención sin cifras ante la
pregunta fuera de alcance.

El set congelado se publicó como release `v2-es-2026-09-02` en el dataset
`allianz-rag-golden` de Langfuse (`allianz golden validate/freeze/publish`), con manifiesto,
hash de contenido y de esquema. No hay holdout todavía, y la ampliación más allá de estos
10 casos sigue pendiente.

## 7. Observabilidad

Langfuse local traza los tres workflows, las llamadas OpenAI (generación, extracción,
embeddings) y el router, con `session_id` propagado por hilo. Las claves de proyecto viven en
`.env` (nunca en Git); el healthcheck no hace llamadas pagadas al LLM.

## 8. Frontend

React 19 + Vite + TypeScript estricto, tipos generados desde el `openapi.json` publicado por
FastAPI (sin segunda definición manual de DTOs). Chat con tool calls por etapa, visor PDF con
resaltado sólo cuando hay coordenadas verificadas (fallback honesto a página completa),
historial persistente en localStorage y modo administrador de ingesta. El visor rasteriza
sólo la página que se está mirando, no el manual entero. 96 tests unitarios, build limpio.

## 9. Límites declarados

- Manual de 2004: no es normativa vigente.
- Sin autenticación multiusuario, sin operación con siniestros reales, sin alta disponibilidad.
- El índice estructurado (Docling) existe pero no es el activo en demo.
- 1 de 14 reglas (`ascide-b11-roundabout`) sigue sin condición verificable.
- El golden set no tiene revisión de un experto humano del dominio.
