# Golden set y evaluación del RAG de Allianz

Fecha de investigación: 31 de agosto de 2026.

Estado: protocolo de diseño, anexo de la [especificación consolidada](../superpowers/specs/2026-08-31-allianz-rag-design.md). Recoge la prioridad de calidad solicitada y concreta la evaluación; todavía no se han generado los casos, calibrado los jueces ni ejecutado comparativas.

Actualización de arquitectura del 31 de agosto: se sustituye el runner de experimentos propio por el SDK de Langfuse integrado con Ragas. Esta revisión cambia la herramienta de ejecución, no los controles de calidad del golden set ni los criterios de aceptación.

Preferencia posterior del usuario: maximizar el uso directo de Langfuse y Ragas y minimizar componentes adicionales. Se utilizarán sus modelos de datos, runner, métricas, rúbricas, herramientas de generación y funciones de revisión antes de considerar extensiones propias. Las instantáneas congeladas serán artefactos de auditoría, no un segundo sistema de gestión.

Ampliación funcional acordada: evaluar también el modo Automático, que decide entre consulta documental y análisis de siniestro. El enrutamiento se medirá de forma aislada y dentro de la petición completa, conservando los modos explícitos para diagnosticar los errores de cada flujo.

## 1. Decisiones principales

- La calidad de las etiquetas tiene prioridad sobre la rapidez de generación y el número de ejemplos. Se dedicará el tiempo necesario a comprobarlas, con controles de salida explícitos.
- El manual proporcionado es la autoridad documental para esta prueba. El golden set es una referencia derivada, versionada y auditable; puede contener errores que habrá que corregir de forma trazable.
- Se evaluará lo que sostiene esa edición del manual, de noviembre de 2004, sin presentarlo como normativa vigente ni confundir la responsabilidad convencional con toda la responsabilidad jurídica de un accidente.
- Se separan cuatro trabajos: curar la referencia, comprobar los evaluadores, comparar los sistemas y medir su funcionamiento técnico.
- La generación, la revisión y la evaluación se configurarán por separado del sistema candidato, sin reutilizar sus respuestas como etiquetas. Se priorizarán modelos de máxima capacidad disponibles y revisión visual cuando proceda, sin presuponer que un modelo más caro garantiza la corrección.
- No se declarará «revisado por un experto» o «verificado por una persona» cuando únicamente haya revisión por IA. El acuerdo entre modelos tampoco demuestra que una etiqueta sea verdadera.

## 2. Construcción y comprobación del golden set

### 2.1. Inventario de evidencias antes de generar preguntas

Se revisará el manual completo y se construirá un mapa de temas, reglas, requisitos, excepciones, referencias cruzadas y elementos visuales. Cada elemento conservará el hash del documento, la página del PDF y la numeración impresa por separado, junto con el texto o región visual que permite comprobarlo.

Los contenidos de los documentos se tratarán como datos de la prueba, no como instrucciones operativas para el asistente. Los textos externos de investigación servirán para diseñar la evaluación, no para añadir reglas de seguros a la referencia.

La extracción que utilice el RAG no será el único acceso a la fuente durante la curación. Los pasajes relevantes se contrastarán con el PDF renderizado para detectar errores compartidos por el parser y el generador del dataset. Las fuentes visuales conservarán la imagen original; una descripción producida por IA no la sustituye.

La matriz CIDE exige una comprobación específica: transcripción independiente, comparación celda a celda con el original, revisión de encabezados, orientación A/B y notas. Sus 324 celdas se comprobarán como datos estructurados; no se contarán como 324 escenarios independientes de evaluación integral. Las respuestas de referencia de los escenarios no se obtendrán ejecutando el mismo motor de reglas que se quiere evaluar.

### 2.2. Cobertura y familias de casos

Los aproximadamente 70 casos y el reparto inicial 50/20 son una orientación, no un límite de calidad ni una garantía de cobertura. El tamaño definitivo dependerá de las familias y excepciones cubiertas. Se publicará también qué partes del manual quedan sin evaluar.

La matriz de cobertura incluirá:

- Consultas factuales sencillas y respuestas que necesitan varias secciones.
- Escenarios de accidentes, requisitos de aplicación y jerarquía de pruebas.
- Tablas, notas, interpretación visual y referencias cruzadas.
- Reglas generales frente a excepciones que cambian la conclusión.
- Información suficiente, datos ausentes, contradicciones y preguntas fuera del alcance documental.
- Respuestas definitivas, respuestas condicionadas y peticiones concretas de información adicional.
- Variantes lingüísticas en español e inglés, sin alterar el significado.
- Intenciones documentales y de aplicación a casos, consultas mixtas y entradas con intención ambigua; se distinguirán de los accidentes cuya intención está clara pero a los que les faltan hechos.
- Casos difíciles para la seguridad: hechos inventados, citas incorrectas, instrucciones maliciosas insertadas en el contexto y extrapolaciones a normativa actual.

Las categorías de integración, razonamiento, lógica, tablas y abstención de LIT-RAGBench, publicado en LREC 2026, aportan una lista útil para comprobar esta cobertura. Adoptamos esa taxonomía como inspiración; no afirmamos reproducir su benchmark ni utilizar una supuesta métrica universal «LIT». [Fuente primaria](https://aclanthology.org/2026.lrec-1.427/).

Los cinco ejemplos de la entrevista permanecerán en desarrollo. Paráfrasis, traducciones y variaciones del mismo escenario compartirán `family_id` y no cruzarán la separación entre desarrollo y reserva. Compartir una regla del manual entre particiones es inevitable y permitido; duplicar esencialmente el mismo caso no lo es.

### 2.3. Generación basada en evidencias

Primero se prepara un paquete de evidencias suficiente, con la regla y sus condiciones. Después se redactan la consulta o el escenario y la referencia. El generador tendrá acceso a ese paquete y podrá consultar otras partes pertinentes del manual; no se aceptará una conclusión porque resulte plausible con conocimiento general de seguros.

La propuesta de candidatos se apoyará en Testset Generation de Ragas, configurando los modelos de máxima capacidad, idioma y tipos de consulta. Cuando hagan falta escenarios particulares del manual, se preferirá extender sus sintetizadores a crear un motor de generación paralelo. Las evidencias originales y los metadatos de procedencia se conservarán durante la conversión. Generar un candidato no lo convierte en una etiqueta verificada. [Generación nativa de Ragas](https://docs.ragas.io/en/stable/concepts/test_data_generation/rag/).

Se generarán pares de contraste: dos casos que solo cambian en un requisito decisivo. También variantes que deberían conservar el resultado. Cada transformación se verificará: intercambiar A/B, por ejemplo, no implica asumir que toda regla del manual es simétrica.

Cada caso contendrá al menos:

| Campo | Contenido |
| --- | --- |
| Identidad | ID, familia, versión, idioma, categoría, dificultad y partición. |
| Entrada | Pregunta o relato exacto que recibirá el sistema. |
| Enrutamiento esperado | Ruta documental, análisis de siniestro o aclaración de intención, adjudicada según la política del producto; no se inferirá de la ruta del candidato. |
| Hechos | Hechos expresos, quién los afirma, contradicciones y datos desconocidos. |
| Resultado esperado | Aplicabilidad, convención, responsabilidad y grado de determinación, cuando proceda. |
| Requisitos de respuesta | Afirmaciones obligatorias, condiciones y explicaciones necesarias. |
| Alternativas aceptables | Formulaciones y conclusiones equivalentes válidas, sin exigir copiar una respuesta modelo. |
| Evidencia | Pasajes o regiones originales y conjuntos alternativos de soporte válido. |
| Prohibiciones | Hechos que no se pueden inventar, conclusiones injustificadas y excepciones que no se pueden omitir. |
| Revisión | Autoría humana o modelo, configuración, comprobaciones, discrepancias y resolución. |

Se distinguirán hechos aportados por el usuario, afirmaciones documentales e inferencias. «Un conductor lo afirma» no equivale a «ambos conductores lo reconocen». La falta de un dato no se rellenará con la suposición más probable.

### 2.4. Revisión separada y resolución de discrepancias

Cada candidato recorrerá estas comprobaciones:

1. **Resolución sin ver la etiqueta propuesta.** Otro contexto de revisión recibe la pregunta y la fuente original y produce una solución independiente de la respuesta del generador.
2. **Contraste de evidencias.** Se comprueba cada requisito, excepción y conclusión con el manual; para tablas e imágenes se examina el soporte visual.
3. **Revisión adversarial.** Se busca una interpretación alternativa, un dato ausente o una excepción que invalide la conclusión. Se comprueban especialmente las afirmaciones prohibidas.
4. **Adjudicación documentada.** Toda discrepancia se resuelve con evidencias. El consenso por votación no sustituye a esa resolución. Los casos no resueltos quedan en cuarentena.
5. **Controles automáticos.** Esquema, referencias existentes, coherencia entre etiquetas, duplicados, familias, integridad de archivos y ausencia de contaminación entre particiones.

Si la respuesta correcta es que el manual o el relato no permiten determinar una conclusión, esa ambigüedad puede formar parte del caso. Lo que no se admite es una disputa de anotación sin resolver presentada como una respuesta definitiva.

Se podrá incorporar otro proveedor como revisor para reducir errores correlacionados. Dos llamadas al mismo modelo con distintos roles aportan contraste, pero no se presentarán como dos expertos independientes.

La revisión humana se registrará por caso y por dimensión revisada. Los casos críticos y aquellos con discrepancias necesitan especial atención. Si no contamos con una persona experta en el dominio, se declarará esa limitación: «referencia sintética auditada contra el manual» no significa «certificación pericial».

Las revisiones humanas utilizarán las colas, anotaciones y comentarios de Langfuse sobre trazas u observaciones enlazadas a cada candidato. Las comprobaciones automáticas quedarán identificadas como evaluaciones de máquina. No se desarrollará una interfaz adicional de revisión ni se marcará una cola completada por una persona cuando no haya intervenido. [Colas de anotación](https://langfuse.com/docs/evaluation/evaluation-methods/annotation-queues).

### 2.5. Condiciones para publicar una versión

Una versión solo se considerará lista cuando:

- Todos los casos admitidos hayan completado el circuito de revisión y tengan procedencia verificable para sus etiquetas y evidencias.
- No queden discrepancias de anotación abiertas dentro del conjunto admitido.
- Las referencias visuales y estructuradas estén comprobadas contra el original.
- La cobertura y las exclusiones estén documentadas; no haya duplicados de familias entre particiones.
- Existan un informe de revisión, un registro de cambios y un manifiesto con hashes y versiones.

Estas son condiciones observables de aceptación, no una promesa de perfección. El tiempo empleado se registrará, pero no será una prueba de corrección.

### 2.6. Congelación y reserva

La reserva se congelará antes de ajustar prompts, reglas, umbrales o configuraciones con resultados del sistema. Quienes curan sus etiquetas pueden revisarlas antes de congelarlas; esa revisión no equivale a utilizarlas para optimizar el candidato.

El flujo del sistema evaluado recibirá únicamente las entradas. El runner de experimentos gestionará también las referencias para entregarlas a los evaluadores, pero su callback no pasará etiquetas, rúbricas privadas ni metadatos de evaluación al caso de uso o al generador de respuestas. Tampoco se incorporarán a su índice. No se incluirán preguntas o respuestas de reserva en ejemplos del prompt.

La selección de configuración se hará con desarrollo. La reserva se utilizará para la evaluación final de una configuración previamente fijada. Si sus resultados motivan cambios, se declarará que ha sido utilizada para desarrollo y hará falta nueva reserva para una nueva afirmación de generalización.

Un error real en una etiqueta se corregirá con nueva versión, justificación y reevaluación de todas las configuraciones comparadas. No se modificarán etiquetas silenciosamente para favorecer al sistema. Una reserva local con controles de acceso y registro es una separación operativa, no un benchmark custodiado por una entidad externa.

## 3. Métricas: qué medimos y cómo se interpreta

No habrá una única puntuación ponderada que permita compensar conclusiones graves incorrectas con buena latencia o estilo. Se distinguirán calidad de recuperación, respuesta, citas, decisiones de dominio y fiabilidad operativa.

### 3.1. Recuperación y suficiencia

| Métrica | Definición para este proyecto | Precaución |
| --- | --- | --- |
| Evidence Recall@k | Proporción de unidades de evidencia necesarias presentes en los primeros k resultados. | Se comparan evidencias originales, no IDs de chunks dependientes del parser. |
| Evidence Recall con presupuesto B | La misma cobertura en el contexto que cabe en un presupuesto de entrada fijado. | Es la comparación principal entre chunkers de distinto tamaño; se registra aparte el consumo de imágenes. |
| Hit@k | Si aparece al menos una evidencia pertinente. | Puede ser alto aunque falte la excepción decisiva. |
| nDCG@k | Calidad del orden usando relevancia previamente anotada. | Se usa solo con anotaciones suficientes y comparables; no mide por sí sola la corrección final. |
| Context sufficiency | Fracción de casos cuyo contexto final contiene toda la información documental necesaria para la respuesta esperada. | Se separa de los datos del accidente que faltan en la entrada del usuario. |

Las evidencias tendrán requisitos AND y alternativas OR: puede ser necesario recuperar una regla **y** su excepción, mientras que dos pasajes equivalentes pueden ofrecer soportes alternativos. Recuperar una página o un chunk con metadatos correctos no cuenta como recuperar la evidencia si el contenido necesario no llegó al generador. Los duplicados no aumentan el recall.

Se registrarán tanto los candidatos recuperados como el contexto final después de reranking, expansión y truncado. Si el sistema usa reglas estructuradas, se registrará ese canal de evidencia por separado, sin atribuir su cobertura al retriever textual.

La evaluación de suficiencia complementa la relevancia: un pasaje puede tratar el tema y no permitir contestar. Este enfoque está respaldado por el trabajo Sufficient Context, presentado en ICLR 2025. Nuestra separación entre ausencia documental y datos del relato es una adaptación al caso de uso. [Fuente primaria](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/).

### 3.2. Respuesta y citas

| Métrica | Qué comprueba | Método |
| --- | --- | --- |
| Precisión, recall y F1 factual | Corrección de afirmaciones y cobertura de la referencia. | Ragas FactualCorrectness como diagnóstico, con juez calibrado. |
| Cumplimiento de requisitos | Requisitos obligatorios y condiciones del caso que satisface la respuesta. | Rúbrica por afirmaciones, con comprobaciones deterministas cuando sea posible. |
| Faithfulness | Soporte de afirmaciones documentales en el contexto efectivamente disponible. | Juez de soporte; no equivale a corrección frente al manual completo. |
| Validez de referencias | Existencia de documento, página, pasaje o región citada. | Comprobación determinista. |
| Precisión de citas | Proporción de citas que aportan soporte a la afirmación asociada. | Verificación semántica o visual, permitiendo soporte conjunto. |
| Cobertura de citas | Proporción de afirmaciones que requieren fuente y están respaldadas por sus citas. | Evaluación por afirmación y conjunto de citas. |

Ragas FactualCorrectness compara respuesta y referencia mediante descomposición en afirmaciones e inferencia de soporte. Se fijarán la granularidad, el modelo y la versión. Si una afirmación adicional no aparece en la referencia, no se declarará automáticamente falsa: se revisará contra el manual y se distinguirá información correcta adicional de invención. [Documentación primaria de Ragas](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/factual_correctness/).

Las métricas de citas se inspiran en ALCE, que separa soporte del texto e irrelevancia de citas. Nuestra unidad será la afirmación verificable y se admitirán pruebas conjuntas. Las llamaremos métricas adaptadas hasta verificar que reproducen exactamente las definiciones e implementación originales; una cita existente o temáticamente relacionada no basta. [Artículo de ALCE](https://aclanthology.org/2023.emnlp-main.398/).

Los hechos del accidente se comprobarán contra el relato y su atribución, no contra el manual. Las reglas se comprobarán contra el manual. Una conclusión aplicada al accidente puede necesitar ambas fuentes. El juez que evalúe una evidencia visual deberá recibir la imagen pertinente; no se puntuará visión utilizando únicamente una descripción no verificada.

### 3.3. Métricas propias del dominio y abstención

- **Exactitud y macro-F1 de decisiones:** aplicabilidad, convención y responsabilidad, desglosadas por campo y clase. Los resultados condicionados o indeterminados serán etiquetas explícitas.
- **Precisión y cobertura de extracción:** hechos extraídos frente a hechos expresos relevantes, con corrección de atribución y conservación de contradicciones.
- **Tasa de hechos inventados:** hechos emitidos sin soporte en la entrada, sin contar como hechos afirmados los valores declarados desconocidos.
- **Tasa de conclusión definitiva injustificada:** casos que exigían condiciones o información adicional y recibieron una conclusión definitiva; se informa el denominador específico.
- **Abstención correcta y abstención innecesaria:** se evalúan por separado, distinguiendo abstenerse por falta de evidencia, pedir datos concretos y dar una respuesta condicionada útil.
- **Selective accuracy y coverage:** exactitud entre respuestas definitivas y proporción de entradas con respuesta definitiva. Se informan juntas, además del éxito de las respuestas condicionadas, para impedir que abstenerse siempre parezca buen rendimiento.
- **Errores críticos por caso:** invención de pruebas, omisión de una excepción decisiva, cita falsa que sostiene la conclusión o atribución de responsabilidad fuera del alcance permitido.

La combinación de exactitud selectiva y cobertura permite observar el coste de abstenerse. No se presentará una confianza autodeclarada del LLM como probabilidad calibrada. Una curva riesgo-cobertura solo se añadirá si existe una señal y una política de umbrales verificables, ajustadas en desarrollo. [Investigación de Google sobre contexto suficiente y generación selectiva](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/).

### 3.4. Robustez y diagnóstico de fallos

Se ejecutarán pruebas controladas con contexto suficiente, retirada de evidencia decisiva, ruido irrelevante e información engañosa. Las alteraciones sintéticas permanecerán en fixtures de prueba identificados y nunca se mezclarán con el manual original ni con su índice normal.

También se compararán paráfrasis, traducciones, cambios de orden y pares de contraste. Se medirá la degradación de corrección, soporte y decisiones respecto a la condición controlada, además de la consistencia cuando no debería cambiar la respuesta.

Ragas ofrece Noise Sensitivity y RAGChecker separa métricas de recuperación y generación a nivel de afirmaciones. Usaremos ese enfoque de diagnóstico, sin instalar dos frameworks completos para calcular lo mismo. Las puntuaciones nativas de esos frameworks y nuestras diferencias entre condiciones llevarán nombres distintos. [Ragas Noise Sensitivity](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/noise_sensitivity/), [repositorio oficial de RAGChecker](https://github.com/amazon-science/RAGChecker).

### 3.5. Ingeniería y observabilidad

| Dimensión | Medidas |
| --- | --- |
| Latencia | Tiempo total y por etapa; p50 y p95 con tamaño de muestra, concurrencia y repeticiones. |
| Streaming | Tiempo hasta el primer contenido útil y hasta completar la respuesta; no confundir un evento de progreso con un token de respuesta. |
| Fiabilidad | Errores, timeouts, rate limits, reintentos, uso de fallback y salidas inválidas respecto al esquema. |
| Consumo | Tokens de entrada y salida, imágenes y llamadas por petición; caché y datos ausentes explícitos. |
| Coste | Estimación por petición y por petición resuelta correctamente, con tarifa y fecha; ingestión, curación, jueces e inferencia por separado. |
| Reproducibilidad | Documento, dataset, código, configuración, prompts, modelos, dependencias y artefactos identificados por versión o hash. |

El coste por petición resuelta incluirá el gasto de los intentos fallidos del conjunto evaluado, dividido entre los éxitos definidos de antemano. No se calculará únicamente sobre peticiones exitosas. Una medición ausente no se sustituye por cero.

Se separarán ejecuciones con caché fría y caliente. Un p95 estimado con muy pocas peticiones se presentará como exploratorio. Las comprobaciones de calidad se ejecutarán con la misma política de reintentos y fallback que el sistema, y se desglosarán por ruta utilizada.

OpenTelemetry dispone de convenciones para consumo de tokens, duración de llamadas y otras señales GenAI. La especificación consultada está en estado Development y actualmente vive en un repositorio separado; se fijará la versión al instrumentar. No se etiquetarán nuestras métricas de negocio como métricas estándar de OpenTelemetry. [Convenciones oficiales GenAI](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-metrics.md).

### 3.6. Investigación reciente: UDCG

Redefining Retrieval Evaluation in the Era of LLMs, EACL 2026, propone UDCG para considerar utilidad y distracción del contexto. Es una línea relevante, pero no será una dependencia obligatoria del proyecto. [Artículo](https://aclanthology.org/2026.eacl-long.391/).

El método original de anotación utiliza probabilidades del modelo; el artículo reconoce limitaciones para APIs comerciales sin acceso a esa información, así como para extrapolar los resultados a otros idiomas y tareas. No calcularemos una media subjetiva de utilidad y la llamaremos UDCG. Solo se incorporará como experimento si se puede reproducir un método definido y validar su aplicabilidad. Mientras tanto, las pruebas de suficiencia, ruido y corrección final cubren preguntas prácticas relacionadas. [Método y limitaciones en el PDF](https://aclanthology.org/2026.eacl-long.391.pdf).

### 3.7. Enrutamiento del modo Automático

La etiqueta de intención se revisará independientemente de la respuesta final. Una pregunta que solicita aplicar reglas a un accidente irá a siniestros aunque el escenario sea hipotético o le falten datos; pedir una definición no pasa a ser análisis únicamente por mencionar un accidente. En consultas mixtas que piden resolver el caso y explicar sus reglas se espera el flujo de siniestros. La ambigüedad de intención se anotará explícitamente, sin premiar aclaraciones innecesarias en casos claros.

Se medirán exactitud, macro-F1 y matriz de confusión sobre las tres decisiones (`question`, `claim`, `clarification_required`), junto con soporte por clase. Se desglosarán la tasa de aclaración necesaria, la de aclaración innecesaria y la calidad de la pregunta de aclaración. Los fallos técnicos del router tendrán su propia tasa y contarán como fallo en el éxito integral; no se convertirán en la clase de aclaración ni desaparecerán del denominador. Una evaluación adicional sobre salidas válidas deberá indicar esa cobertura.

Habrá tres lecturas complementarias: clasificación aislada; calidad de cada flujo con ruta explícita de referencia para diagnóstico; y calidad de extremo a extremo en Automático. La comparación emparejada mostrará cuánto cambia el éxito por caso, las citas, los errores críticos, la latencia y el coste al introducir el router. Acertar la intención no equivale a responder correctamente. Las entradas cuya referencia sea aclarar intención no se forzarán por una ruta ficticia en el diagnóstico de los dos flujos.

Las comparaciones de etiquetas se implementarán como evaluadores deterministas pequeños del SDK de Langfuse y métricas agregadas por ejecución. Ragas seguirá evaluando la respuesta final y, cuando corresponda, la rúbrica de la aclaración. No se creará otro runner ni se utilizará un juez LLM para comparar dos enums.

El router recibirá solo la entrada permitida, sin la etiqueta de intención ni la respuesta esperada. Su modelo y prompt se fijarán con desarrollo antes de usar reserva. Los casos repetidos en modo explícito y automático conservarán la misma familia y no se contarán como nuevas muestras independientes. El tiempo y coste del router formarán parte de la petición completa, además de mostrarse por separado en su observación Langfuse.

## 4. Comprobar también a los evaluadores

Antes de usar un juez LLM para ordenar configuraciones se preparará un conjunto de calibración separado, con respuestas correctas e incorrectas verificadas. Incluirá errores sutiles: excepciones eliminadas, responsabilidades intercambiadas, condiciones convertidas en hechos y citas válidas que no sostienen la conclusión.

Las rúbricas serán concretas y evaluarán criterios separables. El juez no verá el nombre de la configuración candidata; las comparaciones por pares alternarán el orden para detectar sesgos. Se fijarán prompts, versión y configuración del juez, y se revisarán las discrepancias y la variabilidad entre ejecuciones.

Se informarán errores del juez, acuerdo y matriz de confusión contra etiquetas revisadas. Si la referencia de calibración no tiene validación humana, no se describirá ese resultado como acuerdo con expertos. Los fallos técnicos del evaluador se contabilizarán aparte, sin borrarlos del informe ni convertirlos en ceros de calidad del candidato.

Las recomendaciones oficiales de OpenAI insisten en evaluaciones específicas para la tarea y en calibrar los evaluadores automáticos con revisión humana; también advierten de sesgos de posición y longitud. Esa es la base metodológica, no una garantía de que cualquier juez potente sea fiable. [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

## 5. Protocolo de experimentación y decisión

1. Congelar la referencia, las rúbricas, las familias y las métricas principales antes de comparar candidatos.
2. Evaluar extracción e ingestión contra evidencias revisadas, independientemente de la generación.
3. Comparar parser y chunking manteniendo fijo el resto; después comparar recuperación densa, híbrida y reranking.
4. Medir por separado la aportación de reglas y visión. Una variante que recibe evidencia adicional se presentará como tal.
5. Comparar modelos sobre las configuraciones justificadas por desarrollo; no ajustar cada variable simultáneamente.
6. Evaluar el router y el modo Automático con desarrollo, manteniendo fijos los flujos elegidos y comparando con la ejecución explícita.
7. Seleccionar con desarrollo y ejecutar la reserva con la configuración final congelada, incluyendo el enrutamiento automático cuando se evalúe ese modo.

La métrica principal de recuperación será la cobertura de evidencia necesaria con presupuesto controlado. La métrica principal integral será la proporción de casos que cumplen la rúbrica obligatoria y no presentan errores críticos. Como complementos se mostrarán suficiencia, F1 factual, soporte de citas, abstención, latencia y coste.

La selección exigirá ausencia de errores críticos observados en el conjunto de controles fijado antes de comparar. Cualquier fallo crítico bloqueará la aceptación de esa versión hasta analizarlo. Cero errores observados no significa riesgo cero fuera de la muestra.

Los resultados se desglosarán por categorías y familias. Se mostrarán diferencias emparejadas y, cuando el tamaño lo permita, intervalos calculados respetando las familias. Las repeticiones medirán variabilidad del modelo, no se contarán como nuevos casos independientes. Con 20 casos de reserva, un caso equivale a cinco puntos porcentuales: no se venderán mejoras pequeñas como concluyentes.

No se tomarán decisiones principales con BLEU, ROUGE, similitud de embeddings, longitud de respuesta ni una puntuación genérica de «relevancia». Tampoco se premiarán respuestas vacías con una puntuación perfecta de soporte: los denominadores vacíos se marcarán como no aplicables y la falta de respuesta se reflejará en la rúbrica correspondiente.

## 6. Encaje en la arquitectura y entregables

Se utilizará el runner de experimentos del SDK de Langfuse contra nuestra instancia local. Ragas aportará métricas seleccionadas y sus mecanismos de criterios y rúbricas configurables. Solo los controles específicos no cubiertos se implementarán como funciones conectadas al mismo runner. Se conservará una capa pequeña para preparar configuraciones y exportar JSONL y manifiestos mediante las APIs existentes; no se construirá otro motor de experimentos. [Integración Langfuse–Ragas](https://langfuse.com/integrations/frameworks/ragas).

La prioridad será reutilizar la métrica, configurar su criterio o rúbrica, extender la API oficial y, por último, implementar una comprobación específica si resulta necesaria. AspectCritic y las rúbricas por caso de Ragas pueden expresar parte de los criterios semánticos del protocolo. Las comparaciones deterministas seguirán siendo código determinista. Los criterios propios conservarán su definición y calibración aunque la implementación provenga de una librería. [Métricas de propósito general de Ragas](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/general_purpose/).

La ejecución y los evaluadores del SDK vivirán en el proceso Python local. Los experimentos llamarán a los mismos casos de uso y grafos LangGraph que la API. Recibirán el contexto realmente suministrado al generador, además de las salidas estructuradas, para que la evaluación no reconstruya a posteriori una evidencia diferente. Los errores del sistema, del evaluador y de publicación en Langfuse se distinguirán y conservarán.

Cada caso y repetición empezará con estado independiente. Si se utiliza un checkpointer de LangGraph, su identificador distinguirá experimento, versión del dataset, caso y repetición, evitando compartir memoria entre ejemplos o particiones. Una reanudación solo reutilizará el estado del mismo intento y configuración; una repetición destinada a medir variabilidad no reutilizará una respuesta generada previamente como si fuera nueva.

Langfuse local será el entorno operativo para trabajar con candidatos, referencias, metadatos, versiones y particiones separadas. Cada publicación validada del golden set se exportará como una instantánea auditada: esos archivos, su esquema y sus hashes serán la referencia canónica congelada de la publicación. No se mantendrá otra base de datos ni un editor paralelo. Los cambios posteriores se harán en el dataset de trabajo y requerirán nueva validación y publicación. Cada ejecución identificará versión y hash de contenido, esquema, prompts, jueces y configuración; los items cargados deberán coincidir con el manifiesto. [Datasets y versionado](https://langfuse.com/docs/evaluation/experiments/datasets).

El protocolo de curación seguirá siendo específico del proyecto, implementado sobre generación Ragas y datasets, trazas, scores y revisiones de Langfuse. Ninguna herramienta certifica las etiquetas ni hace innecesaria la adjudicación. Las exportaciones de experimentos se mantendrán como artefactos de auditoría y para elaborar la presentación.

La comparación detallada de ejecuciones y la revisión de trazas se harán en la interfaz de Langfuse. El frontend de producto podrá enlazar esas vistas o mostrar un resumen pequeño de lectura; no duplicará el laboratorio de evaluación. Los prompts de la aplicación se gestionarán en Langfuse y se fijarán por versión en experimentos; los prompts internos de las métricas conservarán la configuración nativa de Ragas.

Se mantiene la convención aprobada de `domain`, `application/ports`, `application/use_cases` e `infrastructure/adapters`. Las librerías de evaluación quedarán en adaptadores de salida; CLI y API llamarán a los mismos casos de uso. El esquema exacto de contratos se concretará en la especificación de implementación.

Los artefactos previstos son:

- Inventario de evidencias y matriz de cobertura del manual.
- Dataset con desarrollo y reserva, ficha descriptiva, historial de revisión y manifiesto de versiones.
- Paquete independiente de comprobación de tablas y reglas.
- Conjunto de calibración y resultados de validación de jueces.
- Catálogo versionado de métricas con fórmulas, denominadores y tratamiento de errores.
- Resultados por caso, trazas y comparativas con análisis de fallos.
- Resumen para la entrevista que permita explicar por qué gana una configuración y cuáles son sus límites.

El trabajo realizado en esta fase es la investigación y definición del protocolo. La generación del golden set y las mediciones se ejecutarán después como trabajo explícito del proyecto, sin atribuirles resultados antes de realizarlas.
