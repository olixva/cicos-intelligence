# Paquete de entrega

Este directorio reúne los materiales para presentar el prototipo CICOS
Intelligence como TFM. El alcance se contrasta con el
[enunciado original](../enunciado/GenAI_Interview_Instructions.docx).

## Materiales

| Material | Uso |
|---|---|
| [Memoria técnica](memoria.md) | Arquitectura, decisiones, evaluación, riesgos y límites |
| [Presentación](presentacion.pptx) | Exposición de 30–45 minutos |
| [Guion de defensa](guion-defensa.md) | Agenda, demostración sintética y preguntas previsibles |
| [Validación y límites](validacion.md) | Puertas ejecutadas, campañas y límites comprobables |
| [Evidencias](evidencias/README.md) | Manifiestos, métricas y resultados por caso de las campañas finales |
| [Código y documentación](../../README.md) | Aplicación, scripts, configuración y guías de operación |

## Trazabilidad con el enunciado

| Requisito | Evidencia en el repositorio | Resultado y límite |
|---|---|---|
| Consultar el manual CIDE/ASCIDE/CICOS | `data/raw/`, `data/extractions/`, `docs/ingesta-y-recuperacion.md` | RAG local con citas a páginas; fuente de noviembre de 2004 |
| Explicar el “entrenamiento” del modelo | [Memoria, §§2–3](memoria.md) | No se ajustaron pesos ni se hizo fine-tuning; el prototipo recupera contexto en tiempo de consulta y usa modelos preentrenados |
| Analizar relatos de siniestro | `backend/src/`, [reglas y decisión](../reglas-y-decision.md) | Extracción tipada y motor determinista; la evaluación muestra que la resolución de siniestros aún no es fiable |
| Demostrar preguntas y accidentes | [Guion de defensa](guion-defensa.md), `data/evaluation/golden/development.jsonl` | El golden incluye los cinco escenarios de accidente del enunciado y otros casos sintéticos |
| Gestión del proyecto y plan de cinco días | Presentación, diapositiva «Plan de implementación» | Plan propuesto para el plazo del enunciado; la diapositiva no describe una cronología ejecutada |
| Selección de modelos y librerías | [Memoria, §2](memoria.md), [operación](../operacion.md) | Jev para router y guard; OpenAI para respuesta y extracción. La evaluación live de OpenAI se hizo con Luna; Sol queda como default configurado |
| Preprocesamiento del manual | `backend/scripts/`, `data/extractions/`, [ingesta y recuperación](../ingesta-y-recuperacion.md) | Publicación reproducible con parser baseline; la ingesta estructurada Docling se conserva como alternativa experimental |
| Evaluación básica de respuestas | [Evaluación](../evaluacion.md), [anexos](evidencias/README.md) | Golden sintético, métricas deterministas y red-team; no es una validación de expertos ni una evaluación de producción |
| Código fuente y scripts | `backend/`, `frontend/`, `backend/scripts/` | Incluye carga, evaluación, red-team, reglas y comprobación de contrato OpenAPI |

## Límites que acompañan a la entrega

El resultado es un prototipo académico local. El corpus de evaluación es
sintético y no lo adjudicó una persona experta del dominio. El modo `claim`
solicita aclaraciones en una parte alta de los casos y la exactitud de decisión
se apoya en un denominador reducido; por tanto, no se presenta como un
resolutor fiable ni como una decisión operativa de Allianz.

Las pruebas no usan relatos reales ni datos personales. Antes de un piloto real
harían falta revisión experta de las reglas y el golden, revisión del contrato,
DPA y configuración de retención del proveedor Jev, controles de acceso y
privacidad, y validación de costes de Langfuse. TypeSafe publica que no entrena
con solicitudes/respuestas, que la retención depende del acuerdo y que ofrece
ZDR a clientes Enterprise previa configuración; también indica que el
servicio se aloja en Estados Unidos. No se ha verificado que el prototipo tenga
un acuerdo o ZDR. Véanse su [guía de retención](https://help.typesafe.ai/articles/5974925716-how-is-submitted-data-used-or-retained)
y [política de privacidad](https://typesafe.ai/legal/privacy-policy). Se
confirmó la lectura de una traza local por la API de
observaciones; el enlace no se abrió manualmente en la interfaz. Una prueba de
regresión confirma que la respuesta `claim` interrumpida publica la traza y
conserva el hilo para reanudarlo. El manual de 2004 tampoco sustituye normativa
vigente.

No se incluyen claves, archivos `.env`, bases locales ni historiales de chat en
el paquete de entrega.
