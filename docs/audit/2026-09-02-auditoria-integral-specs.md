# Auditoría integral contra las specs — 2026-09-02

## Dictamen

El proyecto contiene una base técnica sustancial y una primera demo funcional, pero **no cumple todavía la entrega descrita en la especificación**. La ingestión, API, streaming, recuperación híbrida, workflows y frontend tienen implementación y pruebas unitarias. En cambio, la capa que debía demostrar la calidad del sistema —golden revisado, dataset sintético, experimentos, scores, selección de configuración, matriz validada y holdout— está ausente o es únicamente scaffolding. Tampoco existe una suite E2E que cubra los recorridos reales.

Estados usados: **HECHO** (implementado y verificado), **PARCIAL** (hay implementación útil pero faltan requisitos), **SCAFFOLDING** (contratos/tests aislados sin artefacto operativo), **AUSENTE**, **BLOQUEADO**.

## Matriz de las 21 tareas originales

| # | Entrega original | Estado | Evidencia y brecha principal |
|---:|---|---|---|
| 1 | Auditoría de fuente y comando reproducible | HECHO | El PDF fuente existe; `inspect-manual` y pruebas asociadas existen. |
| 2 | Extracción baseline inmutable | PARCIAL | pypdf se reconstruyó en 0,8 s y detecta 111 páginas. La publicación existente contiene `original.pdf`, pero una ejecución nueva baseline no lo copia; debe normalizarse el contrato. |
| 3 | Extracción estructurada con evidencia visual | PARCIAL | Docling se reconstruyó realmente en ~61 s: 111 páginas, 120 ficheros, 20 MB. Genera 17 warnings; página 32 y tablas 45/65/68/80/101–107 requieren revisión. La publicación Docling no está preservada en `data/`. |
| 4 | Chunking y perfiles completos | PARCIAL | Hay chunkers y perfiles parser/chunker/embedding. Los perfiles no identifican retrieval, reranker, visión, reglas ni generador como exigía la spec. |
| 5 | Qdrant y Langfuse locales | PARCIAL | Servicios vivos. Qdrant conserva colecciones antiguas, pero el alias activo apunta a pypdf baseline (118 puntos), no a Docling. Langfuse recibe trazas, pero no sesiones ni scores. |
| 6 | Catálogo de fuente y citas navegables | PARCIAL | API de manual/PDF y citas funciona. No hay regiones útiles en la publicación activa, por lo que el visor no puede resaltar el fragmento exacto. |
| 7 | Dense, BM25 e híbrido | PARCIAL | Los tres modos y RRF existen en código/Qdrant. No existe evaluación real comparativa ni evidencia de selección; la app usa híbrido hardcodeado. |
| 8 | Consulta documental LangGraph | PARCIAL | Responde preguntas y cita páginas. No está demostrado contra golden; hay fragmentación de trazas y estados/latencias engañosos en UI. |
| 9 | Esquema golden y particiones | SCAFFOLDING | Hay schema y validadores con tests. No existe JSONL de casos, release congelada, hashes ni particiones reales. |
| 10 | Experimentos Langfuse + Ragas | SCAFFOLDING | Existe adaptador para un experimento de preguntas y un evaluador `FactualCorrectness`. Langfuse muestra Datasets, Experiments y Scores vacíos. |
| 11 | Métricas de evidencia, decisión e ingeniería | PARCIAL | Existen coverage, precision/recall de identificadores y coste por éxito. Faltan corrección semántica de citas, decision F1, router, abstención, alucinación, errores críticos, p50/p95 y calibración. |
| 12 | Generación/revisión/congelación del golden | AUSENTE | No hay dataset sintético, revisión humana, freeze, release ni comandos CLI correspondientes. |
| 13 | Matriz y reglas deterministas | SCAFFOLDING | Existe un lookup seguro que se niega a decidir sin datos. No existe artefacto 18×18, doble transcripción, validación de orientación/notas ni corpus de reglas auditado. |
| 14 | Flujo de siniestros con hechos atribuibles | PARCIAL | Extrae hechos y evalúa aplicabilidad básica (dos vehículos/colisión directa). La decisión queda `undetermined`; no resuelve convenio/matriz ni genera explicación final completa. |
| 15 | Visión, expansión y reranking medibles | AUSENTE | No se encontró implementación de visión o reranker, ni ablation/evaluación. |
| 16 | Modo automático | PARCIAL | Hay router tipado y LangGraph. En prueba real, un relato de accidente se clasificó como pregunta; no hay dataset ni métricas del router. |
| 17 | API, estados y streaming | PARCIAL | OpenAPI está actualizado; endpoints y SSE tienen tests. El frontend muestra “clasificando” incluso en modos explícitos y fabrica duraciones iguales/0 ms. |
| 18 | Frontend independiente | PARCIAL | Build, lint, tipos y 51 unit tests pasan. Historial falso/no navegable, sugerencias deficientes y estados no veraces. |
| 19 | Visor PDF | PARCIAL | Abre el PDF, pero tiene dos cierres y no resalta texto/región; el hover de fuentes usa un BorderBeam azul distractor. |
| 20 | Selección experimental, holdout e informe | AUSENTE | No hay ejecuciones, resultados, thresholds, ganador, holdout ni informe reproducible. |
| 21 | Demo reproducible, documentación y presentación | PARCIAL | Hay README/docs y demo local. No hay presentación; `docs/e2e-report.md` sobreafirma una cobertura que no corresponde al E2E actual. Builds Docker bloqueados por falta de espacio. |

## Pruebas ejecutadas

- Backend: **292 passed, 1 skipped**. Pyright: **0 errores**. Ruff lint pasa; Ruff format falla en **25 archivos**.
- Frontend: **10 ficheros / 51 tests passed**, ESLint y TypeScript pasan; build Vite pasa con aviso de chunks >500 kB.
- E2E oficial: **2 casos**, 1 pasa y 1 falla por locator ambiguo. No cubre backend real, historial, PDF, Langfuse, errores ni edge cases.
- OpenAPI: snapshot actualizado.
- Ingestión real: pypdf y Docling completan sobre el PDF de 111 páginas; Docling conserva imágenes y emite advertencias de revisión.
- Docker: ambos builds fallan antes de construir por `no space left on device` en `colima-allianz` (6,384 GB de imágenes y 1,542 GB de volúmenes; no se borró nada).
- Navegador real: probados auto, pregunta, siniestro, citas, visor, sidebar e integración Langfuse. Se reprodujeron los defectos descritos por el usuario.
- Langfuse real: 36 root traces/134 observations, 0 scores; Datasets, Experiments y Sessions vacíos. Prompts existentes, pero trazas fragmentadas y enlaces directos inválidos.
- Qdrant real: alias activo a baseline pypdf; existe una colección Docling antigua, no seleccionada.

## Riesgos que impiden declarar la demo correcta

1. **No hay ground truth**: no es posible afirmar precisión, cobertura o ausencia de alucinaciones.
2. **El flujo de siniestros no concluye la tarea de negocio**: aplicabilidad parcial no equivale a resolución CIDE/ASCIDE/CICOS.
3. **La matriz no está validada**: automatizarla antes de doble revisión puede producir decisiones incorrectas.
4. **Observabilidad incompleta**: sin session_id, scores y trace URL oficial no se pueden auditar conversaciones ni abrir trazas con fiabilidad.
5. **La interfaz comunica eventos falsos**: fases y tiempos no proceden de telemetría backend.
6. **Cobertura E2E casi inexistente**: los tests verdes no representan el comportamiento visto por el usuario.

## Qué debe reservarse para el agente más potente

- Diseño del golden y guía de anotación, especialmente casos ambiguos y política de abstención.
- Validación semántica de la matriz 18×18 y reglas de convenio con revisión humana independiente.
- Definición de métricas/umbrales y lectura crítica de resultados experimentales.
- Rediseño del contrato de eventos/trazas para que estados, sesiones y latencias sean verdaderos.

Las tareas mecánicas —persistencia de historial, retoques CSS, cierre único del visor, ampliación de Playwright, CLI y CI— sí pueden delegarse con seguridad una vez fijados esos contratos.
