# Contratos de API y experiencia de producto

Fecha: 31 de agosto de 2026.

Documento de detalle vinculado a la [especificación consolidada](../superpowers/specs/2026-08-31-allianz-rag-design.md).

Estado: diseño funcional aprobado por el usuario y ampliado, a petición suya, con un modo automático que elige entre los dos flujos. Conserva el stack, los flujos LangGraph y la integración nativa con Langfuse y Ragas ya aprobados. No se ha implementado ni probado la API o la interfaz.

## Decisión principal

La aplicación tendrá tres modos: **Automático**, **Consultar manual** y **Analizar siniestro**. Compartirán navegación, componentes de respuesta y visor de evidencias. Los dos modos explícitos invocarán directamente su caso de uso; Automático determinará cuál necesita la entrada y lo invocará. **Evaluación** abrirá Langfuse local; no será un segundo laboratorio construido en el frontend.

Se retira la propuesta anterior de dejar el enrutamiento automático para después. Automático formará parte del alcance inicial. Se propone como selección inicial del frontend, manteniendo siempre visibles los otros dos modos y mostrando qué flujo ha seleccionado el sistema.

## Enrutamiento automático

Se usará un clasificador LLM con salida estructurada y un conjunto cerrado de decisiones: `question`, `claim` o `clarification_required`. Su modelo y prompt serán configurables y se seleccionarán mediante evaluación; no se presupone que deba ser el modelo más barato ni el mismo generador de respuestas. Una heurística por palabras clave puede servir de baseline experimental, pero no será el criterio de aceptación del modo automático.

| Intención | Ruta |
| --- | --- |
| Consultar una definición, requisito o procedimiento del manual | `question`. |
| Aplicar criterios a un accidente concreto o hipotético | `claim`. |
| Pedir la resolución de un caso y las reglas que la justifican | `claim`, cuyo flujo ya recupera y explica la documentación pertinente. |
| Entrada que no permite identificar qué se quiere resolver | `clarification_required`, con una pregunta breve o selección explícita. |

La presencia de una narración de accidente no fuerza por sí sola `claim`: si la petición real es una definición, sigue siendo documental. Tampoco la falta de hechos del accidente fuerza una aclaración de intención: si el usuario quiere analizarlo, se envía al flujo de siniestros, que gestionará los datos ausentes. Las entradas fuera del alcance conservarán el tratamiento previsto en los flujos; no se inventará una especialidad adicional para responderlas.

El router decidirá el destino sin responder al contenido ni reescribir el relato. El flujo elegido recibirá la entrada original y las aclaraciones explícitas. No tendrá acceso a etiquetas, respuestas esperadas o metadatos privados del golden set. El texto del usuario será un dato a clasificar, sin capacidad para modificar la política de enrutamiento o las reglas del sistema.

Un pequeño grafo de entrada en LangGraph clasificará y seleccionará una rama condicional que invoque una sola vez el caso de uso existente. Los grafos documental y de siniestros seguirán siendo los mismos que usan los modos explícitos y la evaluación, sin copias para Automático. Esto utiliza el patrón de routing documentado por LangGraph. [Routing en LangGraph](https://docs.langchain.com/oss/python/langgraph/workflows-agents#routing).

Los modos explícitos omitirán por completo el clasificador; no podrán ser cambiados silenciosamente por él. Una aclaración de intención terminará esa ejecución con un resultado tipado, sin lanzar ambos flujos ni iniciar un bucle automático. Un fallo del proveedor o una salida inválida, tras los reintentos acotados, será un error técnico de enrutamiento: se ofrecerá elegir un modo explícito, sin simular que se ha entendido la intención. No se usarán porcentajes de confianza autodeclarados como probabilidades calibradas.

## Contratos HTTP mínimos

Todos los endpoints de producto estarán bajo `/api/v1`. Las rutas de salud se mantienen fuera del versionado funcional.

| Ruta | Función |
| --- | --- |
| `POST /api/v1/queries/resolve` | Clasificar la entrada en modo automático e invocar el flujo elegido, o solicitar aclaración de intención. |
| `POST /api/v1/questions/answer` | Responder una pregunta sobre el manual mediante el flujo documental. |
| `POST /api/v1/claims/analyze` | Analizar una descripción del siniestro y sus aclaraciones explícitas. |
| `GET /api/v1/manual` | Metadatos de la edición registrada, hash y número de páginas del PDF. |
| `GET /api/v1/manual/pdf?version={hash}` | Servir la versión del PDF original a la que apunta la respuesta. |
| `GET /api/v1/manual/evidence/{evidence_id}` | Resolver una evidencia registrada y su localización en el documento. |
| `GET /api/v1/demo/cases` | Ejemplos seleccionados para la demostración: solo entradas públicas del conjunto de desarrollo. |
| `GET /health/live` | Comprobar que el proceso está vivo. |
| `GET /health/ready` | Comprobar las dependencias necesarias para admitir consultas. |

La ingesta, curación y ejecución de experimentos se iniciarán desde CLI y las capacidades nativas ya acordadas. No se añadirá una API general de jobs, datasets o experimentos para reproducir Langfuse.

Las entradas incluirán el texto del usuario y el idioma de respuesta. El análisis podrá recibir aclaraciones del usuario identificadas por separado de la descripción original. Un selector avanzado opcional admitirá únicamente nombres de perfiles permitidos por el servidor; nunca rutas de configuración, secretos o parámetros arbitrarios de proveedores. Sin selector se usará el perfil de demo elegido tras evaluar.

Cada consulta inicial será independiente. Añadir información a un siniestro reenviará la descripción y las aclaraciones explícitas y producirá un nuevo análisis. No se tratará una respuesta anterior del asistente como un hecho aportado por el usuario. No se requiere inicialmente historial persistente, cuentas de usuario o memoria conversacional entre casos.

## Respuestas tipadas

Las tres entradas devolverán un sobre común con `request_id`, `requested_mode`, `resolved_mode`, resultado tipado, evidencias y metadatos de ejecución. En los modos explícitos el modo solicitado y resuelto coincidirán. En Automático se registrará `requested_mode: auto` y el modo elegido; si hace falta aclarar la intención, `resolved_mode` será nulo y el resultado será `clarification_required` con una pregunta breve. La unión discriminada de resultados distinguirá respuesta documental, análisis y aclaración, sin fingir que esta última ha ejecutado un flujo. Los metadatos identificarán el perfil efectivo, la configuración y las versiones del documento; podrán incluir duración y referencia a la traza local. Los manifiestos completos permanecerán en los artefactos y Langfuse, sin exponer secretos ni estado interno del grafo al navegador.

Los párrafos o bloques de respuesta tendrán identificadores y referencias explícitas a las evidencias que los sustentan. El frontend no tendrá que deducir citas mediante expresiones regulares sobre texto libre ni interpretar una conclusión jurídica a partir de una frase.

| Resultado documental | Significado |
| --- | --- |
| `answered` | Hay una respuesta sustentada para la pregunta. |
| `partial` | Se responde una parte y se declara qué no puede establecerse. |
| `insufficient_evidence` | La evidencia disponible no permite responder con soporte suficiente. |
| `out_of_scope` | La consulta queda fuera del alcance del manual y de esta aplicación. |

El resultado del análisis de siniestro separará estas dimensiones:

| Campo conceptual | Contenido |
| --- | --- |
| Participantes y hechos | Identificadores estables dentro del caso, hechos extraídos y procedencia en las palabras del usuario. |
| Atribución y contradicciones | Quién afirma cada hecho, acuerdos expresos y versiones incompatibles; lo no indicado permanece desconocido. |
| Aplicabilidad | `applicable`, `not_applicable` o `undetermined`, con motivos y evidencia. |
| Convenio | CIDE, ASCIDE o sin determinar, cuando corresponda según el manual. |
| Decisión | `resolved`, `conditional`, `undetermined` o `not_assessed`. |
| Resultado entre partes | Parte o partes implicadas en la conclusión del convenio, solo cuando pueda establecerse. |
| Condiciones y datos faltantes | Condiciones necesarias, información ausente y preguntas concretas para poder avanzar. |
| Explicación y alcance | Fundamento citado y separación entre el tratamiento del convenio y otras cuestiones de responsabilidad. |

Se validará la coherencia entre campos: una conclusión condicionada debe declarar sus condiciones; un convenio no aplicable no habilita una asignación de responsabilidad general; un participante citado debe existir en la entrada analizada. Los detalles del esquema se fijarán con los modelos de aplicación, evitando duplicar los modelos de dominio en el frontend.

Una petición técnicamente correcta puede terminar con datos insuficientes o una conclusión condicionada y responder HTTP 200. Una caída del proveedor, un timeout o un fallo de recuperación serán errores técnicos estructurados; no se convertirán en una abstención aparentemente válida. Las validaciones de estructura y evidencias reducen fallos detectables, pero no certifican por sí solas que una respuesta sea correcta.

## Citas y visor del manual

Cada evidencia tendrá un identificador asociado al documento original y a su versión, no únicamente al chunk empleado por un recuperador. El backend resolverá ese identificador contra evidencias registradas, sin aceptar páginas, fragmentos o coordenadas inventados por el generador.

| Dato | Regla |
| --- | --- |
| Documento y versión | Identificador y hash del PDF registrado. |
| Página del PDF | Número físico basado en 1, utilizado para navegar. |
| Página impresa | Etiqueta independiente y opcional; no se calculará aplicando un desplazamiento global. |
| Sección | Identificación extraída o verificada; puede faltar. |
| Fragmento | Distinguir cita literal, transcripción verificada y descripción; una descripción no se presentará entre comillas como original. |
| Regiones | Coordenadas opcionales verificadas, normalizadas y con convención explícita respecto a la página visible, su recorte y rotación. |

Al pulsar una cita se abrirá la página correcta en un panel contiguo a la respuesta. Habrá resaltado del fragmento solo cuando existan coordenadas verificadas. En caso contrario se mostrará la página y se indicará que la localización es a nivel de página. Las tablas y documentos escaneados conservarán su imagen original; la evidencia deberá incluir cabeceras o notas cuando sean necesarias para interpretar una celda.

Una afirmación podrá enlazar varias evidencias que la sustentan conjuntamente. La presentación diferenciará el número de página del PDF y la etiqueta impresa para evitar confundirlas. La URL del PDF quedará vinculada a la versión citada; una versión no disponible se comunicará como tal, sin sustituirla por otro documento. Los identificadores se resolverán en el backend: no se admitirá acceso a rutas arbitrarias del disco o a URLs indicadas por el modelo.

## Progreso y errores

Los tres POST admitirán respuesta JSON ordinaria o, mediante `stream: true`, eventos SSE. Se reutilizará el mismo resultado final tipado en ambos formatos.

Se propone usar el soporte SSE de FastAPI y un cliente compatible con POST en el navegador. FastAPI documenta SSE también para POST; el `EventSource` nativo del navegador no permite ese tipo de petición. La compatibilidad del cliente elegido y los contratos generados se comprobará al fijar dependencias. [Documentación oficial de SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/).

Los eventos serán `started`, `stage`, `completed` y `failed`. Mostrarán etapas reales —identificando la intención en Automático, recuperando evidencias, comprobando reglas, preparando la respuesta—, sin porcentajes ficticios ni razonamiento interno del modelo. Un evento de etapa comunicará el modo elegido. La primera versión presentará el contenido final tras las comprobaciones de respuesta y citas, sin mostrar provisionalmente una atribución de responsabilidad que después se retire. Una aclaración de intención se entregará en `completed` como resultado válido, sin confundirla con `failed`.

`completed` contendrá el mismo objeto que devolvería el modo JSON. Los errores anteriores al inicio del stream usarán el estado HTTP correspondiente; una vez iniciado, el fallo se comunicará mediante `failed`. Un cierre sin evento terminal se mostrará como interrupción. No habrá reintentos automáticos de toda la petición que puedan duplicar llamadas pagadas. Cancelar será una operación de mejor esfuerzo, sin prometer que detenga una llamada ya admitida por el proveedor.

Este streaming no requiere una cola de trabajos ni garantiza reanudar ejecuciones al reconectar. Si aparece esa necesidad, se diseñará explícitamente la persistencia correspondiente. La ingesta y curación largas mantienen el mecanismo de progreso persistente aprobado en el documento de arquitectura.

## Pantallas y comportamiento

**Automático.** Entrada libre con ejemplos de ambos flujos y la misma vista de respuesta o análisis que los modos explícitos. Tras clasificar se mostrará «Modo detectado: Consulta del manual» o «Modo detectado: Análisis de siniestro». El usuario podrá cambiarlo y volver a ejecutar conservando su texto; esa corrección será una nueva petición explícita. La necesidad de aclarar la intención se mostrará de forma breve, sin exigir completar el formulario de un accidente antes de saber qué se está preguntando. Automático no añade historial persistente ni una conversación con memoria implícita.

**Consultar manual.** Entrada de pregunta con ejemplos, progreso por etapas y respuesta legible con referencias junto a las afirmaciones. Si el soporte es parcial se distinguirá lo respondido de lo pendiente. El PDF aparecerá al abrir una cita, sin expulsar al usuario de la respuesta.

**Analizar siniestro.** Entrada narrativa y ejemplos seleccionados. El resultado empezará por una conclusión breve y su estado, seguida de aplicabilidad, participantes, hechos, condiciones, datos faltantes y evidencia. La distinción entre resultado confirmado y condicionado estará en el encabezado y junto a la conclusión, no escondida en una nota final. El botón «Añadir información» permitirá contestar las preguntas pendientes y volver a analizar.

**Evidencias.** Panel redimensionable en escritorio, con navegación por página y resaltados cuando sean posibles. En pantallas estrechas se abrirá como vista superpuesta con retorno a la misma posición de la respuesta. Citas y controles serán accesibles con teclado y sus estados no dependerán solo del color.

**Evaluación.** Acceso directo a Langfuse local para datasets, revisión, trazas y comparativas. La respuesta podrá ofrecer «Ver ejecución» cuando exista una traza publicada. No se dibujarán métricas sintéticas o porcentajes de confianza decorativos en las respuestas de producto.

La interfaz identificará la edición del manual de noviembre de 2004 y el alcance de la demostración. No presentará sus conclusiones como comprobación de normativa vigente ni como una decisión operativa de Allianz. El aspecto visual usará los componentes ya elegidos; la composición gráfica detallada se concretará al implementar el frontend.

## Integración y comprobaciones previstas

FastAPI publicará OpenAPI y se generarán los tipos o el cliente TypeScript a partir de ese contrato. Se evitará mantener a mano una segunda definición de los DTO. El manejo del stream será una integración pequeña con una biblioteca compatible, no un nuevo protocolo propio. [Generación de clientes desde FastAPI](https://fastapi.tiangolo.com/advanced/generate-clients/).

Las comprobaciones funcionales cubrirán la coherencia de los estados, aclaraciones sin hechos inventados, correspondencia entre citas y PDF, comportamiento ante una interrupción y distinción entre error técnico y falta de evidencia. También se comprobará que los modos explícitos no llamen al router, que Automático reutilice los mismos casos de uso, que API y evaluación sigan el mismo recorrido y que los ejemplos de demo no expongan referencias esperadas ni contenido del holdout. Se medirá el enrutamiento por separado y su efecto sobre la calidad integral, la latencia y el coste, conforme al protocolo de evaluación actualizado.

El frontend no recibirá claves de proveedores, acceso a Qdrant o reglas de decisión. El contenido generado se renderizará sin HTML arbitrario y los enlaces a fuentes se limitarán al documento registrado. Los servicios se publicarán únicamente en localhost. La comprobación de disponibilidad no hará llamadas pagadas al LLM en cada sondeo; una caída de telemetría no bloqueará una consulta si el resto de dependencias necesarias y los prompts fijados están disponibles.

## Paso posterior

Las decisiones de este bloque se han incorporado a la especificación completa, junto con arquitectura, ingesta, flujos y evaluación. Esa especificación queda preparada para revisión final antes del plan de implementación. Este documento no acredita que se haya escrito o ejecutado el producto.
