# Especificación de diseño — Asistente RAG para la prueba de Allianz

Fecha: 31 de agosto de 2026. Versión de diseño: 1.

Estado: especificación aprobada por el usuario el 31 de agosto de 2026; autoriza preparar el plan e iniciar la siguiente fase en Git local, sin publicar en GitHub todavía. No acredita código implementado, dependencias verificadas en conjunto, un golden set publicado ni resultados experimentales.

## 1. Resultado que se quiere entregar

Un asistente RAG local que responda preguntas sobre el manual CIDE/ASCIDE/CICOS y aplique sus criterios a relatos de accidentes. Tendrá tres modos de entrada —Automático, Consultar manual y Analizar siniestro— y dos recorridos de resolución que compartirán ingesta, recuperación, generación y evidencias cuando corresponda. La interfaz permitirá comprobar cada cita contra el PDF original.

El proyecto debe demostrar comprensión del problema y decisiones justificadas con experimentos reproducibles. La ambición técnica se concentrará en la calidad de las evidencias, la resolución fundamentada de casos y la evaluación; no en multiplicar frameworks, agentes o pantallas administrativas.

Decisiones principales:

- Backend Python con arquitectura hexagonal ligera y LangGraph para la orquestación; frontend React independiente dentro del mismo repositorio.
- Ingesta y recuperación intercambiables por configuración; recuperación densa, BM25 e híbrida comparables, con reglas y visión como canales identificados de evidencia.
- OpenAI como proveedor inicial de modelos. Aplicación y servicios locales; las llamadas a modelos y embeddings externos requieren Internet.
- Langfuse local como herramienta de experimentación, datasets, prompts y observabilidad; Ragas como primera opción para generación sintética, métricas y rúbricas.
- Referencia sintética auditada contra el manual, con separación entre desarrollo y reserva, controles independientes y publicación congelada.
- Selección de la configuración de demo por evaluación. La disponibilidad de una técnica no demuestra que mejore los resultados.

## 2. Trazabilidad con el enunciado

La sección Description de las instrucciones describe expresamente preguntas sobre temas del manual y descripciones de accidentes que requieren identificar partes, responsabilidad y circunstancias. Las dos capacidades son un requisito; separarlas en recorridos internos y añadir selección automática son decisiones de diseño. Los cinco ejemplos aportados son accidentes y tendrán prioridad en la demostración y los controles de aceptación.

| Requisito de la prueba | Respuesta del proyecto | Evidencia de cumplimiento |
| --- | --- | --- |
| RAG con un LLM y el manual suministrado | Recuperación sobre ese documento y generación sustentada. | Manifiesto del documento, contexto utilizado, respuesta y citas. |
| Consultas sobre temas del manual | Recorrido documental. | Casos revisados de preguntas factuales, condiciones y referencias cruzadas. |
| Análisis de accidentes | Extracción de hechos, comprobación de criterios y conclusión con alcance explícito. | Los cinco ejemplos originales y familias adicionales con etiquetas revisadas. |
| Preprocesamiento y limpieza | Ingesta reproducible con inventario de páginas y elementos. | Informe de extracción, pérdidas detectadas y tratamiento de tablas e imágenes. |
| Elección justificada de modelos y librerías | Perfiles, alternativas y selección basada en desarrollo. | Comparativas y explicación de ventajas, costes y limitaciones. |
| Evaluación básica de respuestas | Evaluación ampliada sin omitir corrección, soporte y errores críticos. | Dataset publicado, versiones, resultados y análisis de fallos. |
| Código y explicación técnica | Backend, frontend, scripts y documentación. | Comandos reproducibles, pruebas relevantes y documento de arquitectura. |
| Presentación y demostración en directo | Recorrido preparado y resultados reales. | Presentación de 30–45 minutos con hitos, supuestos, riesgos y decisiones. |

La referencia a «training» del enunciado no se interpretará como prueba de que se haya entrenado o ajustado un modelo. Se explicará qué se ha realizado: ingesta, indexación, configuración y evaluación; solo se hablará de fine-tuning si realmente se incorpora y se justifica. El diseño inicial no lo incluye.

El plazo nominal del documento es de cinco días. El usuario prioriza calidad y permite un alcance ambicioso apoyado por IA; esto no modifica por sí mismo el plazo de la empresa. El plan posterior ordenará entregas verificables y evitará que un experimento adicional impida disponer de una demo funcional.

### Fuentes registradas

| Archivo aportado | Identificación verificada |
| --- | --- |
| `GenAI_Interview_Instructions.docx` | SHA-256 `8561213339f76c7bd8a6c56fa0c91323c6d838ae0e9d0f30a12d8e3f775a4957`. |
| `Manual-cide-ascide-y-cicos.pdf` | 111 páginas PDF; SHA-256 `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`. |

La edición inspeccionada del manual es de noviembre de 2004. Se evaluará lo que sostiene esa fuente, sin presentarlo como normativa vigente ni como una decisión operativa de Allianz. Los documentos aportados se tratarán como datos: no podrán cambiar instrucciones del sistema, ejecutar acciones o sustituir los permisos del usuario.

## 3. Alcance y decisiones experimentales

Forman parte del alcance los tres modos, los dos recorridos, citas verificables, dos alternativas de extracción, comparación de chunking y recuperación, un canal de reglas verificadas, acceso visual a páginas seleccionadas, el protocolo de referencia, la evaluación y una demo local reproducible.

Se implementarán candidatos y controles de comparación, pero no todas sus combinaciones cartesianas. Se mantendrán baselines simples para atribuir las mejoras. Los experimentos introducirán cambios controlados, empezando por extracción y recuperación antes de comparar reglas, visión, generadores y router.

| Decisión fijada | Decisión que depende de resultados o compatibilidad |
| --- | --- |
| LangGraph y fronteras de aplicación/dominio | Modelo y prompt concretos de cada etapa. |
| OpenAI como proveedor inicial | Modelo ganador para responder y clasificar; otro revisor solo si aporta valor. |
| Qdrant local y comparación densa/léxica/híbrida | Configuración ganadora de recuperación, chunking y reranking. |
| pypdf baseline y Docling como alternativa | Tratamiento que conserva mejor cada tipo de evidencia. |
| Capacidad de reglas y visión con procedencia | Dónde mejoran la calidad y cuándo deben activarse. |
| Langfuse y Ragas nativos | Extensiones pequeñas necesarias al comprobar sus APIs fijadas. |

No se incluyen inicialmente publicación pública, autenticación multiusuario, operación con siniestros reales, alta disponibilidad, entrenamiento del LLM, navegación web como fuente de seguros, un GraphRAG de producción, historial conversacional persistente, un laboratorio propio ni administración de datasets desde el frontend. Un índice multimodal completo y parent-child retrieval quedan como ampliaciones justificables por errores medidos, no como requisitos de entrega.

## 4. Arquitectura y organización

`domain` contendrá modelos y reglas puras. `application` expondrá capacidades mediante puertos de entrada, implementará casos de uso y servicios, y definirá los puertos de salida que necesita. `infrastructure` contendrá adaptadores, SDKs, FastAPI, LangGraph, configuración y conexiones. `bootstrap.py` compondrá las implementaciones.

Los puertos de entrada son implementados por los casos de uso y llamados por API/CLI. Los puertos de salida son implementados por adaptadores. Un mismo nombre funcional conectará el archivo del puerto con el directorio de sus adaptadores. No se añadirá `cicos/` debajo de `src/` ni un directorio `presentation` separado de infraestructura.

Estructura prevista; los archivos se crearán cuando exista la responsabilidad correspondiente, sin clases vacías para completar el árbol:

```text
backend/
  src/
    domain/
      models/
        claim.py
        evidence.py
        decision.py
      rules/
        applicability.py
        cide_matrix.py
    application/
      models/
      ports/
        inbound/
          answer_question.py
          analyze_claim.py
          resolve_query.py
          ingest_document.py
        outbound/
          document_parser.py
          embedding_provider.py
          evidence_repository.py
          retriever.py
          language_model.py
          question_workflow.py
          claim_workflow.py
          query_workflow.py
      use_cases/
        answer_question_use_case.py
        analyze_claim_use_case.py
        resolve_query_use_case.py
        ingest_document_use_case.py
      services/
    infrastructure/
      adapters/
        inbound/
          api/
            app.py
            routes/
            schemas/
          cli/
        outbound/
          document_parser/
            pypdf_parser.py
            docling_parser.py
          embedding_provider/
            openai_embedding_provider.py
          evidence_repository/
          retriever/
          language_model/
            openai_language_model.py
          question_workflow/
            langgraph_workflow.py
          claim_workflow/
            langgraph_workflow.py
          query_workflow/
            langgraph_workflow.py
          evaluation/
            langfuse_experiments.py
            ragas_evaluators.py
            domain_evaluators.py
      config/
        settings.py
    bootstrap.py
  configs/
  tests/
  pyproject.toml
  uv.lock
frontend/
  src/
  package.json
  pnpm-lock.yaml
data/
docs/
compose.yaml
Makefile
```

La estructura de evaluación albergará integración con los SDKs, no una copia de sus modelos `Dataset`, `Score` o runner. No habrá un puerto propio por cada clase de Langfuse o Ragas. La API y los experimentos invocarán los mismos casos de uso; los evaluadores podrán acceder a evidencias de ejecución que no es necesario enviar al navegador.

### Frontera de LangGraph

Los casos de uso delegarán la coordinación a `question_workflow`, `claim_workflow` o `query_workflow`. Sus adaptadores LangGraph mantendrán el estado técnico y llamarán a servicios de aplicación y reglas de dominio. Aplicación y dominio no importarán LangGraph, FastAPI o los SDKs de proveedores.

El grafo automático invocará los casos de uso documental o de siniestros mediante sus puertos de entrada, inyectados en el arranque. Esos casos no volverán a invocar el coordinador automático. Los servicios llamados desde un grafo tampoco reiniciarán su propio caso de uso. Se evita así la recursión entre coordinación y ejecución.

Backend y frontend tendrán dependencias, lockfiles, comandos y pruebas propios. La raíz coordinará el entorno local; no se añadirán herramientas de monorepo que no sean necesarias.

## 5. Stack y entorno local

| Área | Selección |
| --- | --- |
| Backend | Python 3.14 estándar, uv, FastAPI y Pydantic 2. |
| Modelos internos y puertos | Dataclasses, enums y Protocol; tipos HTTP específicos en el adaptador API. |
| Orquestación | LangGraph, dos grafos de resolución y un grafo pequeño de entrada automática. |
| Configuración | Perfiles YAML validados; secretos y entorno mediante pydantic-settings. |
| Calidad de código | Ruff, Pyright y pytest; no sustituir comprobaciones por scripts que solo imprimen éxito. |
| Ingesta | pypdf y Docling, con artefactos visuales del PDF conservados. |
| Recuperación | Qdrant local; vectores densos, BM25 configurado para español y fusión RRF inicial. |
| Modelos | SDK OpenAI en adaptadores; roles de generación, visión, router y revisión configurados por separado. |
| Evaluación y observabilidad | Langfuse local, su SDK de experimentos, métricas y rúbricas Ragas. |
| Frontend | React, TypeScript estricto, Vite, pnpm, Tailwind y shadcn/ui. |
| Visor y cliente API | PDF.js o wrapper compatible; tipos o cliente generados desde OpenAPI. |
| Ejecución | Desarrollo con uv/pnpm y servicios Compose; la ruta de demo en contenedores se comprobará en CPU. |

Las versiones exactas se fijarán tras comprobar instalación, imports y una conversión representativa en el equipo local. El soporte declarado por una dependencia no acredita la compatibilidad del conjunto. Una incompatibilidad de Python 3.14 o de un componente nativo se resolverá y documentará antes de congelar el entorno. No se mantendrá una instalación rota por conservar una versión propuesta.

La aceleración nativa del Mac será una opción separada de la ruta en contenedores. Se comprobará consumo conjunto de memoria de ingesta, Qdrant y Langfuse. El equipo inspeccionado tiene 24 GiB; eso no equivale a una prueba de capacidad bajo la carga del proyecto.

Los IDs de modelos y su disponibilidad en la cuenta se verificarán antes de ejecutar. Se priorizará capacidad para generar y revisar la referencia; no se rebajará su calidad por defecto. El presupuesto y consumo se registrarán por fase, con concurrencia y reintentos acotados. No hay llamadas pagadas realizadas durante esta fase de especificación.

## 6. Ingesta, evidencias y perfiles

La ingesta separará lectura del documento, extracción, normalización de elementos, chunking, generación de representaciones e indexación. Un parser no decidirá por sí mismo el retriever ni el generador.

Cada elemento conservará documento y hash, página física del PDF, etiqueta impresa independiente, sección cuando se conozca, texto y/o imagen, tipo de contenido, coordenadas verificadas opcionales y versión de extracción. Los valores ausentes se declararán desconocidos. Una descripción generada de una imagen no se presentará como transcripción literal.

Se contrastarán chunks de tamaño fijo con solapamiento frente a segmentación por estructura y secciones. Las tablas conservarán encabezados y notas necesarias; no se convertirán en filas aisladas sin contexto. Las referencias cruzadas podrán ampliar el contexto con límites configurados y procedencia registrada.

El inventario abarcará las 111 páginas, incluyendo páginas con poco texto o contenido escaneado. Durante la inspección se identificaron como controles especiales la DAA escaneada de la página PDF 32 y la matriz de la página PDF 101. Las páginas PDF y las etiquetas impresas no se relacionarán mediante un desplazamiento global supuesto.

Los IDs de evidencia identificarán ubicaciones o unidades del documento original y su versión. Los chunks podrán variar entre parsers; las citas y las anotaciones de evaluación se alinearán con la evidencia original. El registro documental no incluirá preguntas, etiquetas o respuestas del golden set. Las métricas comprobarán que la evidencia llegó realmente al generador, no solo que un chunk comparte un ID o una página.

La matriz CIDE tendrá una transcripción estructurada verificada de sus 18 × 18 posiciones, orientación A/B, encabezados y notas. Su validez como dato no autoriza aplicarla sin sus requisitos. Las celdas o reglas no verificadas no producirán decisiones deterministas.

### Recuperación y visión

Se compararán recuperación densa, BM25 y fusión híbrida; RRF será una configuración inicial, no el ganador anticipado. El procesamiento léxico se fijará para español y se comprobarán siglas, negaciones y términos del manual. El comportamiento en inglés y cualquier traducción de consulta se evaluarán por separado. BM25 se ejecutará localmente, sin activar inferencia cloud de Qdrant.

La visión añadirá imágenes originales seleccionadas de páginas o regiones cuando sean necesarias para interpretar la evidencia. Esto es distinto de construir un índice multimodal completo. Se registrarán selección, páginas, recortes, modelo y consumo; una variante visual no se presentará como una mejora del retriever textual cuando recibió otra información.

Cada perfil fijará parser, chunking, embeddings, retrieval, fusión, reranker si existe, reglas, visión y generador. El router tendrá también modelo y prompt versionados. Los manifiestos recogerán la configuración resuelta. Cambiar embeddings, dimensiones o procesamiento léxico invalidará la reutilización de índices incompatibles; las cachés dependerán de versiones y contenido, no solo de nombres de archivo.

La ingesta tendrá progreso persistente por unidad y reanudación explícita. Una ejecución parcial no se publicará como índice completo. Se conservará el índice anterior hasta validar el nuevo; las consultas se vincularán a una versión coherente del documento y sus artefactos.

## 7. Comportamiento de los recorridos

### Automático

Será el modo inicial del frontend, manteniendo visibles los dos explícitos. Clasificará la intención con salida estructurada: `question`, `claim` o `clarification_required`. Preguntar por una regla va al manual; pedir aplicarla a un accidente, también hipotético, va a siniestros. Un caso con petición de explicación de reglas sigue siendo análisis de siniestros.

Se clasificará la intención, no la presencia de determinadas palabras. Un relato con datos ausentes puede tener intención clara y debe llegar al análisis, que resolverá esa insuficiencia. Una ambigüedad de intención producirá una pregunta breve y terminará la ejecución; no disparará ambos flujos. El router entregará la entrada original al caso de uso elegido, sin reescribir hechos ni responder él mismo al contenido.

Los modos explícitos omitirán el router y no serán cambiados silenciosamente. Un error técnico de clasificación no se disfrazará de ambigüedad; se ofrecerá elegir un modo explícito. La interfaz mostrará el modo detectado y permitirá corregirlo conservando el texto.

### Consulta documental

Recuperar evidencias → rerank y expansión acotada si el perfil los activa → incorporar evidencia visual si corresponde → construir respuesta sustentada → comprobar estructura, referencias y soporte según la política fijada.

El resultado distinguirá respuesta completa, parcial, evidencia insuficiente y consulta fuera de alcance. Se indicará qué no se ha podido establecer. El sistema no completará una falta de soporte con conocimiento general presentado como contenido del manual.

### Análisis de siniestro

Extraer participantes, hechos y atribuciones → conservar contradicciones y desconocidos → recuperar criterios → comprobar aplicabilidad y reglas → construir una conclusión sustentada o condicionada → explicar con evidencias → comprobar coherencia y citas.

Los hechos procederán del relato del usuario y sus aclaraciones. La afirmación de una parte no equivale a reconocimiento por ambas. No se inferirán casillas de una DAA, acuerdos, testigos reconocidos o requisitos administrativos porque parezcan probables.

La aplicabilidad del convenio, la conclusión entre las partes y el alcance material/personal serán dimensiones distintas. Cuando no se pueda establecer una conclusión, el resultado indicará condiciones y preguntas útiles. La falta de un dato no obligará siempre a una abstención total: una respuesta condicionada fundamentada puede ser correcta.

El motor de reglas devolverá resultados con requisitos y procedencia. El generador no podrá convertir un resultado indeterminado en definitivo ni anular silenciosamente una regla aplicada. Si aparece una contradicción entre evidencia y resultado estructurado, se declarará y se evitará emitir una conclusión definitiva no sustentada. No se añadirá una cita a posteriori para aparentar fundamento.

### Garantías comunes

Se acotarán pasos, tamaño de entrada y contexto, timeouts y reintentos. La configuración resuelta formará parte de la ejecución. Las consultas serán independientes; «Añadir información» reenviará el relato y aclaraciones del usuario, sin usar respuestas previas del asistente como hechos.

Una petición válida con evidencia o datos insuficientes no es un fallo técnico. Una caída del proveedor, del índice necesario o una salida inválida tras los reintentos sí lo es. Las comprobaciones estructurales y de referencias reducen errores detectables, pero no certifican corrección semántica.

## 8. API, resultados y experiencia

Los contratos detallados y los estados se desarrollan en el [anexo de API y experiencia](../architecture/2026-08-31-api-y-experiencia-propuesta.md). Las capacidades HTTP son:

| Endpoint | Propósito |
| --- | --- |
| `POST /api/v1/queries/resolve` | Automático: clasificar e invocar el recorrido correspondiente. |
| `POST /api/v1/questions/answer` | Consulta documental explícita. |
| `POST /api/v1/claims/analyze` | Análisis explícito de siniestro. |
| `GET /api/v1/manual` | Metadatos del documento registrado. |
| `GET /api/v1/manual/pdf?version={hash}` | PDF de la versión citada. |
| `GET /api/v1/manual/evidence/{evidence_id}` | Evidencia y localización registradas. |
| `GET /api/v1/demo/cases` | Entradas públicas de desarrollo elegidas para la demo. |
| `GET /health/live`, `GET /health/ready` | Salud del proceso y disponibilidad para admitir consultas. |

El sobre común incluirá `request_id`, `requested_mode`, `resolved_mode`, resultado tipado, evidencias y metadatos de ejecución. Los resultados documental, siniestro y aclaración de intención formarán una unión discriminada. Si hace falta aclarar intención, no habrá modo resuelto ni se afirmará haber ejecutado un recorrido.

Las respuestas se organizarán en bloques con referencias explícitas. Las citas resolverán documento, versión, página PDF, etiqueta impresa y regiones verificadas opcionales. Al abrir una cita se mostrará el PDF junto a la respuesta; sin coordenadas verificadas se navegará a la página sin fingir un resaltado exacto. No se aceptarán URLs o rutas arbitrarias elegidas por el modelo. Si la versión citada falta, no se sustituirá silenciosamente por otra.

Los POST devolverán JSON o SSE mediante `stream: true`, reutilizando el mismo resultado final. Los eventos serán `started`, `stage`, `completed` y `failed`. Mostrarán progreso real y el modo detectado, sin razonamiento interno ni porcentajes ficticios. La respuesta final se presentará tras sus comprobaciones; un evento de progreso no se contabilizará como primer contenido útil.

Un stream interrumpido sin evento terminal se mostrará como interrupción, no como éxito. No se reintentará automáticamente toda la petición duplicando llamadas pagadas. Cancelar será de mejor esfuerzo. SSE no implica reanudación duradera: si se incorpora un checkpointer, tendrá alcance y almacenamiento explícitos.

El frontend generará tipos o cliente desde OpenAPI, renderizará el contenido sin HTML arbitrario y no contendrá claves, acceso a Qdrant o reglas de negocio. Incluirá accesibilidad por teclado, estados que no dependan solo del color y visor adaptado a escritorio y pantalla estrecha. No se añadirán porcentajes de confianza decorativos.

La sección Evaluación abrirá Langfuse local. Las respuestas podrán enlazar su traza cuando esté publicada. No se desarrollará otro editor de datasets, gestor de prompts o panel completo de experimentos.

## 9. Golden set y revisión

El [protocolo de golden set y métricas](../evaluation/2026-08-31-golden-set-y-metricas-rag.md) forma parte de esta especificación y conserva las definiciones detalladas. El manual es la autoridad documental; el golden set es una referencia derivada que puede necesitar correcciones versionadas.

El inventario de evidencia precederá a la generación. Ragas propondrá candidatos a partir de paquetes verificados, con modelos de máxima capacidad adecuados, distribución de consultas y lenguaje configurados. Los sintetizadores se extenderán por su API cuando el dominio lo requiera; no se construirá otro generador general. Las evidencias visuales originales se conservarán durante todo el circuito.

Cada caso tendrá entrada, familia, partición, idioma, intención esperada, hechos y desconocidos, resultado esperado, requisitos, alternativas aceptables, prohibiciones, fuentes y procedencia de revisión. No bastará una respuesta textual modelo. Se incluirán excepciones, tablas, evidencia visual, referencias cruzadas, falta de información, contradicciones, entradas mixtas y variantes en español e inglés.

La revisión tendrá resolución sin ver la etiqueta propuesta, contraste con el PDF original, búsqueda adversarial de excepciones, adjudicación documentada y controles de integridad. No se obtendrán etiquetas ejecutando el mismo motor de reglas que se evalúa. Casos con discrepancias sin resolver quedarán en cuarentena; una ambigüedad real de la fuente puede tener como etiqueta correcta una conclusión indeterminada.

La revisión automática se identificará como tal. El acuerdo entre modelos no será certificado experto. Se registrará cualquier intervención humana por caso y dimensión; si no hay validación pericial, se declarará esa limitación. Langfuse organizará revisiones mediante trazas, anotaciones, scores y colas, sin una interfaz propia.

La orientación inicial es aproximadamente 70 casos, con 50 de desarrollo y 20 de reserva, ajustable por cobertura. Los cinco originales estarán en desarrollo. Paráfrasis, traducciones y variantes de una familia no cruzarán particiones. Las 324 celdas de la matriz constituyen un control de extracción independiente, no 324 accidentes nuevos.

La reserva se congelará antes de ajustar configuraciones; router y generador recibirán únicamente entradas permitidas. No tendrán acceso a etiquetas, rúbricas privadas o ejemplos de reserva. Si los resultados de reserva motivan cambios, se declarará su uso para desarrollo y hará falta otra reserva para sostener una nueva afirmación de generalización. Las correcciones de etiquetas crearán versión y justificación nuevas, con reevaluación de los candidatos comparados.

## 10. Evaluación nativa y selección

El SDK de Langfuse ejecutará los experimentos mediante `run_experiment` contra datasets registrados en nuestra instancia local. Ragas aportará métricas y rúbricas. El código propio se limitará a configurar, invocar los casos de uso, adaptar salidas, realizar comprobaciones específicas y exportar resultados mediante APIs existentes. No habrá un runner paralelo.

Langfuse será el entorno de trabajo de datasets y prompts. Una publicación validada se exportará como instantánea con JSONL, esquema, hashes y revisión: esa instantánea será la referencia canónica congelada para entrega y auditoría. Los cambios se harán en Langfuse y producirán una nueva publicación; no habrá dos editores ni sincronización bidireccional.

Se fijarán versiones concretas de dataset, prompts, modelos y jueces y se comprobará el contenido contra el manifiesto. Dado que las guías consultadas difieren sobre lectura de versiones de datasets, el comportamiento de la versión fijada del SDK se verificará antes de confiar en él. La copia identificada de cada publicación permanecerá sin editar durante comparativas. El esquema tendrá su propia versión en los archivos.

Cada caso y repetición empezará con estado independiente. Los identificadores de persistencia distinguirán experimento, dataset, caso e intento; nunca compartirán memoria entre particiones. Una reanudación del mismo intento no se contabilizará como repetición independiente. La integración registrará el contexto realmente utilizado, las imágenes, las reglas aplicadas y las salidas estructuradas.

| Dimensión | Métricas y lectura |
| --- | --- |
| Recuperación | Evidence Recall@k y con presupuesto de contexto fijo; Hit@k, nDCG cuando haya anotaciones suficientes y suficiencia documental. |
| Respuesta | Corrección factual, requisitos obligatorios y faithfulness respecto al contexto disponible. |
| Citas | Validez, precisión semántica y cobertura por afirmación; admitir soporte conjunto cuando corresponda. |
| Dominio | Exactitud y macro-F1 por decisión, atribución de hechos, invenciones, falsa certeza y errores críticos. |
| Incertidumbre | Abstención correcta e innecesaria, éxito de conclusiones condicionadas, exactitud selectiva y cobertura juntas. |
| Router | Exactitud, macro-F1, matriz de confusión, aclaración necesaria/innecesaria y efecto sobre el resultado integral. |
| Robustez | Paráfrasis, idiomas, pares de contraste, retirada de evidencia decisiva y ruido controlado. |
| Ingeniería | Latencia total y por etapa, p50/p95 con muestra, primer contenido útil, errores, reintentos, tokens, imágenes y coste. |

La recuperación se evaluará con requisitos AND y alternativas OR sobre evidencias originales, descontando duplicados y diferenciando contexto recuperado de contexto final. Reglas e imágenes serán canales registrados aparte. Los jueces visuales recibirán la imagen pertinente; no se afirmará evaluar visión con una descripción no verificada.

Se preferirán métricas nativas y rúbricas Ragas; comparaciones de enums, validez de referencias o controles de la matriz serán deterministas. No se duplicará una métrica equivalente en otro motor. Los jueces se calibrarán con errores conocidos y referencias revisadas, registrando variabilidad, sesgos y fallos técnicos. Una salida vacía no recibirá soporte perfecto por tener un denominador vacío.

La medida integral principal será la proporción de casos que satisfacen la rúbrica obligatoria sin errores críticos. No se usará una media ponderada que compense una conclusión grave incorrecta con buena latencia. La aceptación exigirá cero errores críticos observados en el conjunto de controles fijado; eso no demuestra riesgo cero fuera de la muestra.

El router se medirá aislado y en Automático, comparándolo de forma emparejada con la ruta explícita de referencia. Se distinguirá error de enrutamiento de error del recorrido. Los fallos técnicos contarán en el éxito integral y se informarán por separado; no se ocultarán filtrando solo respuestas válidas.

El coste por petición resuelta incluirá intentos fallidos. Se separarán curación, ingesta, inferencia y jueces, así como caché fría/caliente. Las repeticiones medirán variabilidad sin aumentar artificialmente el número de casos. Con 20 casos de reserva, un caso representa cinco puntos porcentuales; las mejoras pequeñas se presentarán con esa limitación.

UDCG y otras líneas de investigación conservarán su carácter experimental cuando no se puedan reproducir sus requisitos. No se llamará métrica estándar a una aproximación propia. Las definiciones y fuentes técnicas permanecen en el protocolo anexo.

## 11. Operación, privacidad y fallos

Los servicios se publicarán solo en localhost. Los secretos permanecerán fuera de Git y del frontend; las trazas y logs evitarán datos sensibles por defecto. La demo usará los casos sintéticos o proporcionados para la prueba, sin asumir autorización para tratar expedientes reales. Las llamadas externas estarán limitadas a proveedores configurados.

Los prompts se gestionarán en Langfuse y se fijarán por versión. Su contenido efectivo se registrará y podrá conservarse como respaldo congelado, sin otro gestor paralelo. Una caída de telemetría no invalidará por sí sola una respuesta si el resto de dependencias y prompts fijados están disponibles. Si falla la publicación de resultados, el experimento se marcará incompleto.

El chequeo de salud no hará una llamada pagada al LLM por sondeo. La disponibilidad distinguirá configuración, índice y artefactos necesarios de servicios auxiliares. Los errores mostrarán códigos y `request_id`, sin secretos ni trazas internas expuestas al usuario.

Makefile coordinará preparación, arranque, comprobaciones, ingesta, evaluación y demo, conservando comandos independientes por proyecto. Los volúmenes y artefactos necesarios tendrán persistencia; índices, fuentes, publicaciones y resultados quedarán identificados para restaurar una ejecución. No se afirmará que el sistema funciona sin conexión cuando depende de modelos externos.

## 12. Comprobaciones y condiciones de entrega

Las pruebas se centrarán en comportamiento y fronteras: reglas con expectativas independientes, pérdida de evidencia, coherencia de decisiones, llamadas a adaptadores, citas, aislamiento entre casos y errores. No se escribirán pruebas que solo reproduzcan la implementación o certifiquen fixtures artificiales como si fueran el manual.

| Control | Condición de salida |
| --- | --- |
| Entorno | Dependencias bloqueadas, imports y conversión representativa comprobados; comandos documentados. |
| Fuente e ingesta | Hash registrado, 111 páginas contabilizadas, elementos problemáticos revisados y pérdidas declaradas. |
| Reglas | Matriz y notas verificadas; requisitos aplicados; expectativas de prueba independientes. |
| Golden set | Casos admitidos revisados, discrepancias resueltas, familias separadas, cobertura y limitaciones publicadas. |
| Recorridos | Mismos casos de uso para API/CLI/evaluación; estados legítimos de incertidumbre distintos de fallos técnicos. |
| Automático | Clasificación y aclaraciones evaluadas; modos explícitos no invocan el router; texto original conservado. |
| Citas e interfaz | Apertura de la versión y página correctas; resaltado solo verificado; errores e interrupciones visibles. |
| Evaluación | Manifiestos y prompts fijados, referencias no filtradas al sistema, jueces calibrados y resultados conservados. |
| Casos de entrevista | Los cinco originales satisfacen su rúbrica revisada sin errores críticos; no se exige inventar una conclusión definitiva. |
| Demo y entrega | Arranque local reproducible, presentación y arquitectura coherentes con lo ejecutado, límites y fallos documentados. |

Los umbrales adicionales de aceptación se fijarán durante la calibración inicial con desarrollo, antes de la comparativa que pretenda demostrar su cumplimiento y siempre antes de utilizar la reserva. Se registrarán denominadores y alcance. No se inventarán objetivos de latencia o porcentajes de acierto sin conocer carga, costes y distribución de casos. Una entrega parcial se identificará como tal y no sustituirá mediciones ausentes por resultados simulados.

## 13. Riesgos y mitigaciones

| Riesgo | Tratamiento |
| --- | --- |
| Confundir la prueba con un asesor de normativa vigente | Fuente y edición visibles; alcance convencional separado y trazabilidad por afirmación. |
| Extracción incorrecta de imágenes, tablas o notas | Inspección contra PDF original, artefactos visuales y comprobaciones independientes. |
| Golden set contaminado o autovalidado | Revisión ciega, familias, reserva congelada y etiquetas no derivadas del candidato. |
| Juez LLM fiable en apariencia pero sesgado | Calibración con errores conocidos, versiones fijadas y análisis de discrepancias. |
| Complejidad excesiva para la prueba | Núcleo funcional temprano; experimentos secuenciales; reutilizar Langfuse/Ragas; sin laboratorio duplicado. |
| Coste, latencia o memoria superiores a lo previsto | Medición por fase, concurrencia acotada y variantes comparables antes de elegir configuración. |
| Router que empeora un recorrido correcto | Comparación emparejada con modo explícito y corrección visible por el usuario. |
| Cambios de SDK, modelo o dataset | Lockfiles, versiones concretas, manifiestos, hashes y comprobación de compatibilidad. |
| Falsa sensación de producción | Describir garantías comprobadas de demo local, sin atribuir autenticación, HA o operación multiusuario. |

## 14. Hitos y revisión final

El plan de implementación posterior desarrollará estos hitos, con tareas y verificaciones concretas:

1. Entorno reproducible y prueba de compatibilidad de las integraciones seleccionadas.
2. Inventario verificable del manual y baseline funcional de consulta con citas.
3. Curación y congelación de la referencia, junto con calibración de evaluadores.
4. Recorrido de siniestros, reglas verificadas y experimentos controlados de ingesta/recuperación/visión.
5. Modo Automático y experiencia completa con PDF y Langfuse.
6. Selección con desarrollo, evaluación final de reserva y preparación de la presentación y demo.

La curación podrá avanzar junto a la implementación del baseline, pero la reserva se congelará antes de utilizar sus resultados para elegir configuraciones. Las tareas de generación largas tendrán controles de calidad y reanudación; el tiempo dedicado no sustituirá las condiciones de publicación.

Anexos que conservan el detalle y las fuentes investigadas:

- [Stack y fronteras tecnológicas](../architecture/2026-08-31-stack-tecnologico-propuesto.md).
- [API, estados y experiencia](../architecture/2026-08-31-api-y-experiencia-propuesta.md).
- [Golden set, métricas y protocolo experimental](../evaluation/2026-08-31-golden-set-y-metricas-rag.md).

Esta especificación es el punto de entrada al diseño y los anexos desarrollan sus contratos y protocolos. Cualquier cambio de alcance se reflejará en ambos, conservando el historial. La revisión final comprueba coherencia, correspondencia con el enunciado, límites de alcance y criterios de aceptación. Tras su aprobación se redactará el plan con la skill writing-plans de Superpowers; no se inicia la implementación por el hecho de haber escrito este documento.
