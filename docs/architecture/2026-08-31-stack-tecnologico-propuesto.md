# Stack tecnológico propuesto

Fecha: 31 de agosto de 2026.

Documento de detalle vinculado a la [especificación consolidada](../specs/2026-08-31-allianz-rag-design.md).

Estado: stack aprobado por el usuario, con LangGraph y preferencia explícita por la máxima integración nativa con Langfuse y Ragas. No se han instalado dependencias ni validado todavía el conjunto completo en ejecución. La arquitectura de carpetas y las garantías del protocolo de evaluación se conservan. El diseño funcional de API y pantallas está recogido en el documento complementario, con el modo Automático solicitado además de los dos explícitos.

## Recomendación

Backend Python con LangGraph como orquestador, lógica de aplicación y dominio separada y adaptadores pequeños; Qdrant local para recuperación densa y léxica; frontend React con Vite; experimentos ejecutados con el SDK de Langfuse, Ragas y evaluadores específicos del dominio.

La prioridad para evaluación y observabilidad será: capacidad nativa, configuración de esa capacidad, extensión mediante la API oficial y, solo si falta una capacidad necesaria, código específico del proyecto. No se crearán runners, registros de datasets, sistemas de puntuación o interfaces que dupliquen Langfuse y Ragas. Las fronteras del dominio seguirán protegidas, pero no habrá una interfaz propia por cada clase del SDK.

Enfoques considerados y decisión actual:

| Enfoque | Ventaja para el proyecto | Coste o límite |
| --- | --- | --- |
| LangGraph, seleccionado | Flujos explícitos, estado tipado, ramas condicionales y posibilidad de reanudar ejecuciones. | Su estado, persistencia y límites de ejecución deben configurarse y comprobarse. |
| Python explícito sin runtime de grafos, alternativa descartada para la orquestación inicial | Pasos, contratos y errores fáciles de seguir y comparar. | Requiere resolver las capacidades de coordinación que queremos mostrar con LangGraph. |
| Framework RAG como núcleo | Integraciones y componentes ya disponibles. | Sus abstracciones pasan a condicionar precisamente las etapas que queremos experimentar. |

LangGraph permite combinar pasos deterministas y llamadas LLM, y no obliga a adoptar las cadenas e integraciones de alto nivel de LangChain. Se utilizará desde el inicio para los dos flujos de consulta; las reglas permanecerán fuera del grafo. Tener dos flujos no exige técnicamente LangGraph, pero su representación explícita y la preferencia del usuario justifican esta elección. No se presupone que añadirlo mejore por sí solo la calidad de las respuestas. [Documentación oficial](https://docs.langchain.com/oss/python/langgraph/overview).

## Los dos flujos LangGraph

| Flujo | Secuencia conceptual |
| --- | --- |
| Consulta del manual | Recuperar → rerank/expandir contexto si corresponde → incorporar evidencia visual si corresponde → generar respuesta → validar soporte y citas. |
| Análisis de siniestro | Extraer hechos y contradicciones → recuperar criterios → evaluar aplicabilidad y reglas → construir conclusión definitiva, condicionada o petición de datos → generar explicación → validar soporte y citas. |

Serán dos grafos con entradas y salidas diferenciadas. Compartirán componentes de recuperación, preparación de evidencia y validación cuando tengan el mismo contrato. Las variantes experimentales se seleccionarán por configuración de esos componentes, sin copiar un grafo completo por cada perfil.

Los nodos encaminarán el trabajo según resultados tipados de la aplicación: evidencia insuficiente, datos del caso ausentes, convenio no aplicable o conclusión sustentada. No todos los nodos serán llamadas LLM. La ausencia de un requisito no implicará siempre terminar sin ayudar: se conservarán las respuestas condicionadas previstas en el protocolo.

Para respetar las dependencias aprobadas, los casos de uso expondrán las capacidades de consulta y análisis y utilizarán puertos de workflow definidos en `application/ports/outbound/`. Las implementaciones LangGraph vivirán en `infrastructure/adapters/outbound/`, con el mismo nombre funcional que su puerto. Los nodos delegarán las operaciones en servicios de aplicación y reglas de dominio. `application` y `domain` no importarán LangGraph; el estado técnico del grafo se traducirá a los modelos de la aplicación en el adaptador. Los servicios llamados desde nodos no volverán a invocar el caso de uso que inicia el mismo grafo.

API, CLI y experimentos utilizarán los mismos casos de uso y, por tanto, los mismos grafos. Habrá límites de pasos y reintentos, estados de error explícitos y progreso por etapas. La persistencia se configurará donde se necesite reanudación; instalar LangGraph no la activa ni garantiza por sí solo la recuperación de una ejecución.

Además de los dos modos explícitos, el usuario ha solicitado Automático. Un grafo de entrada pequeño utilizará un clasificador LLM con salida estructurada y ramas condicionales para invocar el caso de uso documental o el de siniestros, conservando la entrada original. Si la intención no puede determinarse, devolverá una petición de aclaración. El router no ejecutará ambos flujos ni sustituirá sus reglas. Los modos explícitos seguirán accediendo directamente a su caso de uso sin llamar al clasificador. Se reutiliza el patrón de routing nativo, sin añadir un framework de enrutamiento. [Routing en LangGraph](https://docs.langchain.com/oss/python/langgraph/workflows-agents#routing).

La coordinación automática seguirá la misma frontera: capacidad y contratos tipados en aplicación; grafo, estado y conexión al proveedor en adaptadores de infraestructura. El grafo de entrada invocará los casos de uso elegidos mediante sus puertos de entrada, inyectados en el arranque. Ninguno de esos casos volverá a invocar el coordinador automático. Modelo y prompt del router estarán versionados; su latencia, coste, errores y ruta elegida se registrarán dentro de la misma traza Langfuse de la petición.

## Backend

| Pieza | Selección propuesta |
| --- | --- |
| Python | 3.14, distribución estándar; parche exacto fijado al preparar el entorno. |
| Dependencias | uv, `pyproject.toml` y `uv.lock` propios del backend. |
| API y contratos HTTP | FastAPI, Pydantic 2 y OpenAPI. |
| Orquestación | LangGraph, con dos flujos de resolución y un grafo pequeño de entrada para el modo Automático. |
| Dominio y puertos | Dataclasses, enums y Protocol de Python; sin FastAPI ni clientes de proveedores. |
| Configuración | Perfiles YAML validados; secretos y ajustes de entorno mediante pydantic-settings. |
| Lint y formato | Ruff. |
| Tipado | Pyright como comprobación obligatoria del código propio. |
| Pruebas | pytest; soporte asíncrono y pruebas de integración para adaptadores según necesidad. |
| Ingestión | pypdf como baseline y Docling como candidato estructurado. |
| Recuperación | Qdrant local, vectores densos y BM25, con RRF como fusión inicial. |
| Proveedores LLM | SDK del proveedor dentro del adaptador correspondiente; OpenAI como proveedor inicial acordado. |
| Evaluación | Runner del SDK de Langfuse, métricas y rúbricas configuradas en Ragas; funciones específicas únicamente para controles no cubiertos. |
| Registros | Logs estructurados y trazas de LangGraph y proveedores en Langfuse local. |
| Prompts | Gestión y versiones de Langfuse; los experimentos fijarán versiones concretas. |

Python 3.14 es una rama estable y Docling declara soporte para esa versión. Esto no prueba todavía la compatibilidad conjunta de todos los extras, modelos y dependencias nativas: antes de congelar el entorno se comprobarán instalación, imports y una conversión representativa en el Mac del proyecto. Una incompatibilidad se documentará y resolverá explícitamente, sin mantener dependencias rotas por perseguir una versión. [Python](https://www.python.org/downloads/release/python-3140/), [Docling](https://pypi.org/project/docling/).

uv aporta el entorno y el bloqueo de dependencias; Ruff cubre lint y formato. Se ha revisado también ty: su repositorio lo identifica todavía como beta y advierte de cambios incompatibles entre versiones. Por eso propongo Pyright como control obligatorio; ty podría probarse de forma adicional, sin que el proyecto dependa de él. [uv](https://docs.astral.sh/uv/guides/projects/), [Ruff](https://docs.astral.sh/ruff/), [estado de ty](https://github.com/astral-sh/ty).

## Recuperación y configuración

Qdrant permite almacenar representaciones densas y dispersas y fusionar resultados por ranking. La recuperación densa sola y la léxica sola seguirán disponibles como baselines. RRF será el punto de partida, no el ganador declarado antes de evaluar. [Consultas híbridas](https://qdrant.tech/documentation/search/hybrid-queries/).

El análisis léxico se fijará para español. El BM25 documentado por Qdrant utiliza inglés por defecto, por lo que no se copiará esa configuración sin adaptarla. Se comprobarán siglas, negaciones, referencias de artículos y términos propios del manual. En consultas en inglés se medirá por separado el comportamiento léxico y cualquier traducción o reformulación añadida. [BM25 y tratamiento de texto](https://qdrant.tech/documentation/search/text-search/full-text-search/).

BM25 se ejecutará localmente. La ruta concreta —inferencia local soportada por la versión del servidor o cálculo en el cliente— se fijará tras comprobar el despliegue; no se activará inferencia cloud de Qdrant. Los embeddings OpenAI seguirán siendo llamadas externas, tal como se acordó.

Cada perfil elegirá parser, chunking, modelo de embeddings, retrieval, fusión, reranker, reglas, visión y generador. Se validará la compatibilidad entre perfil e índice. Un cambio en embeddings o en el procesamiento léxico no reutilizará silenciosamente un índice incompatible.

Se conservará el manifiesto resuelto de cada experimento, con versiones de modelos, configuración efectiva, prompts y hashes. El reranker y el modelo de la demo se seleccionarán por resultados; no se elegirá un proveedor como ganador en esta fase de diseño.

## Frontend y frontera con el backend

El usuario ha aprobado React + TypeScript estricto + Vite, con pnpm y lockfile propios, en sustitución del Next.js del borrador aportado. La aplicación es local, tiene un backend Python separado y no necesita de momento renderizado en servidor. [Guía de Vite](https://vite.dev/guide/).

Tailwind y shadcn/ui servirán como base visual. El visor del manual usará PDF.js o un wrapper compatible, con navegación a página y resaltado cuando existan coordenadas verificadas. La cita se asociará a una evidencia original, no a un número de chunk. [shadcn/ui con Vite](https://ui.shadcn.com/docs/installation/vite), [PDF.js](https://mozilla.github.io/pdf.js/).

El frontend solo consumirá la API: no tendrá claves de proveedores, acceso directo a Qdrant ni lógica de decisión del dominio. Se generarán los tipos de cliente desde OpenAPI para detectar cambios incompatibles sin compartir código Python. FastAPI publica ese contrato y permite generación de clientes. [FastAPI y OpenAPI](https://fastapi.tiangolo.com/features/).

La separación en `backend/` y `frontend/`, con sus propios comandos, dependencias y pruebas, se mantiene. La raíz solo coordinará servicios, documentación y artefactos de evaluación.

El frontend de producto se centrará en consultas, análisis de siniestros y evidencias. El laboratorio detallado de experimentos será la interfaz nativa de Langfuse, accesible mediante enlaces a sus ejecuciones y trazas. No se construirá otro editor de datasets, gestor de revisiones o panel completo de comparativas. Si la demo necesita un resumen de resultados, será una vista de lectura pequeña basada en resultados existentes, sin otra lógica de evaluación.

## Langfuse y Ragas para los experimentos

La propuesta anterior de construir un runner completo se retira. La ejecución usará `run_experiment` del SDK de Langfuse. Ragas se conectará mediante evaluadores y las métricas del dominio mediante funciones propias, sin duplicar las capacidades de ejecución del SDK. [Integración oficial Langfuse–Ragas](https://langfuse.com/integrations/frameworks/ragas).

El SDK ofrece ejecución concurrente acotada, trazas, aislamiento de errores y evaluadores por caso y por ejecución. El código de estos evaluadores se ejecuta en nuestro proceso Python; no exige desplegar evaluadores administrados dentro del servidor de Langfuse. [Runner oficial](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk).

La integración propia será pequeña: cargar el perfil, verificar los manifiestos, invocar el caso de uso adecuado, adaptar su resultado a las métricas y exportar resultados mediante las APIs existentes. Se utilizarán los tipos de Langfuse y Ragas en esta integración, sin reproducir sus modelos de datos en un framework interno. El resultado de la tarea incluirá respuesta, hechos, decisiones, citas y contexto realmente utilizado. La respuesta esperada solo será accesible a los evaluadores: aunque el SDK entregue un item completo al callback, este pasará únicamente los campos de entrada permitidos al caso de uso.

Langfuse local será el lugar de trabajo de los datasets: inputs, referencias, metadatos, versiones, estado de revisión y particiones. Al congelar una publicación se exportará una instantánea auditada con esquema y hashes; esos archivos conservarán la referencia canónica de esa publicación y servirán para entrega, auditoría y restauración. No habrá dos editores ni sincronización bidireccional: los cambios de trabajo se harán en Langfuse y producirán una nueva publicación congelada cuando se validen. Para las comparativas se utilizarán los datasets registrados en la instancia local. [Comportamiento del runner con datasets](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk).

Se fijará la versión temporal del dataset y se comprobará su contenido contra el manifiesto antes de ejecutar. La documentación de datasets describe lectura y experimentos sobre versiones concretas, aunque la guía general del runner conserva una nota incompatible sobre el uso de la última versión; se comprobará ese comportamiento en la versión de SDK fijada. Como garantía adicional, cada publicación del golden set tendrá una copia identificada por versión que no se editará durante las comparativas. El esquema también se versionará en los archivos, ya que Langfuse versiona los items, no sus esquemas. [Versionado de datasets](https://langfuse.com/docs/evaluation/experiments/datasets).

Ragas será la primera opción tanto para métricas estándar como para criterios configurables: AspectCritic, rúbricas generales y rúbricas por caso cuando correspondan. Las definiciones, escalas, modelos y entradas se fijarán y calibrarán; una rúbrica genérica no sustituirá una comprobación concreta. Las comprobaciones deterministas de tablas, decisiones estructuradas, validez de referencias o cobertura de evidencias que no estén cubiertas se añadirán como funciones pequeñas al mismo runner. No se utilizará un juez LLM para sustituir una comparación que pueda resolverse de forma determinista. [Criterios y rúbricas nativos de Ragas](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/general_purpose/).

Para proponer casos sintéticos se utilizará la generación de testsets de Ragas sobre evidencias previamente preparadas y verificadas, configurando idioma, modelos y distribución de consultas. Los escenarios específicos de siniestros se cubrirán mediante sus mecanismos de extensión cuando sean necesarios. El grafo de conocimiento usado internamente para generar candidatos no exige añadir una base de datos de grafos al producto. Todos los candidatos pasarán la revisión independiente acordada; la salida del generador no se incorporará automáticamente al golden set. Los casos visuales conservarán acceso a la imagen original y no se forzarán a una representación textual que pierda evidencia. [Generación de testsets en Ragas](https://docs.ragas.io/en/stable/concepts/test_data_generation/rag/).

La revisión por personas utilizará anotaciones, scores, comentarios y colas de revisión nativas de Langfuse. Los candidatos y sus comprobaciones se registrarán como trazas u observaciones enlazadas al caso. Una revisión automática se identificará como tal y no se registrará como revisión humana. Las colas organizan el trabajo, pero no certifican que una etiqueta sea correcta. [Annotation Queues](https://langfuse.com/docs/evaluation/evaluation-methods/annotation-queues).

Los prompts de la aplicación se gestionarán en Langfuse. Cada experimento fijará el ID de versión y registrará el contenido efectivo; no dependerá de que una etiqueta mutable como `latest` o `production` siga apuntando al mismo texto. Para los prompts internos de las métricas Ragas se conservarán sus mecanismos de configuración y la versión de librería, sin trasladarlos artificialmente a otro motor. Las exportaciones congeladas serán respaldo y documentación, no otro gestor de prompts. [Versiones de prompts](https://langfuse.com/docs/prompt-management/features/prompt-version-control).

No se ejecutarán simultáneamente una métrica Ragas y un evaluador administrado equivalente solo para duplicar la misma señal. Los evaluadores del SDK serán la ruta inicial: permiten fijar implementación y modelos sin desplegar otro ejecutor de código en el servidor. Se aprovecharán otras capacidades nativas cuando mantengan esas garantías y estén disponibles en la edición local elegida, sin introducir licencias o servicios adicionales por defecto.

Las trazas del grafo y de las llamadas directas a proveedores se correlacionarán con la ejecución del experimento, evitando contabilizar dos veces una misma llamada. Langfuse dispone de integración con LangGraph y permite añadir observaciones del resto de la aplicación. [Integración de trazas](https://langfuse.com/integrations/frameworks/langchain).

## Ejecución local y garantías de ingeniería

- Desarrollo: backend mediante uv, frontend mediante pnpm y servicios locales mediante Docker Compose.
- Demo reproducible: imágenes y dependencias fijadas, volumen persistente de Qdrant y artefactos de ingestión identificados. La ruta íntegra en contenedores se comprobará en CPU; la aceleración nativa del Mac se tratará como una opción separada.
- Evaluación y observabilidad: Langfuse local y sus servicios dependientes forman parte del entorno de experimentación y de la demo completa. Las pruebas unitarias y de reglas no necesitarán levantarlo. Una caída de telemetría no debe invalidar por sí sola una respuesta del RAG, pero un experimento cuya publicación falle se marcará incompleto. Se comprobará el consumo de memoria al compartir equipo con Qdrant y la ingestión documental. [Despliegue local oficial](https://langfuse.com/self-hosting/deployment/docker-compose).
- Interfaz de comandos: Makefile raíz para preparar, arrancar, comprobar, ingerir, evaluar y mostrar la demo; los comandos del backend y frontend también funcionarán por separado.
- Las tareas largas de curación e ingestión tendrán un registro persistente del progreso por unidad y reanudación explícita. No se ejecutarán como tareas en memoria de una petición HTTP.
- API con validación, timeouts, reintentos acotados y errores estructurados; separación entre error técnico y respuesta documental indeterminada.
- Servicios publicados solo en localhost, secretos fuera de Git y del frontend, y ausencia de datos sensibles en logs por defecto.
- Pruebas de reglas con expectativas revisadas, contratos de adaptadores, integraciones relevantes y recorridos de usuario que comprueben respuesta y apertura de citas.

Estas son prácticas para una demo local mantenible y reproducible. No equivalen a certificar un despliegue productivo multiusuario con alta disponibilidad, autenticación y operación continuada.

## Consolidación

Estos acuerdos se han incorporado a la especificación completa, junto con ingesta, evaluación y diseño funcional de API y pantallas. El documento consolidado queda preparado para revisión final antes del plan de implementación. La evaluación se ejecutará mediante la integración nativa descrita, sin diseñar otra API general de experimentos.
