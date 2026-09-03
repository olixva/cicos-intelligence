# Guion de orador — Allianz CICOS Claims Intelligence

Generado por `docs/entrega/deck/build.mjs` a partir de las notas de las 46 láminas de
`docs/entrega/presentacion.pptx`. No se edita a mano: se regenera con `npm run build` dentro
de `docs/entrega/deck/`. Los mismos textos están en las notas de orador del `.pptx`.

**Reparto de los 45 minutos**: 4 min problema · 4 min plan y riesgos · 12 min arquitectura ·
12 min demo en vivo · 6 min evaluación y límites · 7 min preguntas.

---

## 01 · CICOS Claims Intelligence

*Portada*

APERTURA (30 s). No leer la portada.

Frase de entrada sugerida:
«El enunciado pedía un RAG sobre el manual del Convenio. Lo que me encontré al leer los cinco
accidentes de ejemplo es que cuatro de ellos no tienen una respuesta determinista — y que un
sistema que los resolviera los cinco estaría inventando cuatro. Todo lo que voy a enseñar sale
de esa observación.»

Las cuatro cifras están verificadas hoy contra el repositorio: 111 páginas del manual publicadas,
110 casos en el golden de desarrollo, 14 reglas en el ruleset firmado, 500 pruebas de backend
+ 97 de frontend = 597.

## 02 · Cuarenta y cinco minutos, y un cuarto de ellos con el sistema delante.

*Recorrido*

AGENDA (40 s).

Marcar dos cosas y pasar:
1) El bloque más largo es la demo. Es deliberado.
2) El bloque 05 incluye una lámina de límites: lo que el sistema NO hace se cuenta aquí,
   no en la letra pequeña ni cuando alguien lo pregunte.

RUTA CORTA, si hay que bajar de 45 a 35 minutos (en este orden):
1) Saltar las láminas 17 y 19 — la interfaz y la cita abrible — porque la demo 1 y la 2
   las enseñan en vivo. Están ahí como red de seguridad si la demo falla. (-1:35)
2) Comprimir la 22 (grafo documental) a media frase: los tres nodos y el límite de 8. (-0:25)
3) Fundir 09 (supuestos) y 10 (riesgos) en un solo pase, leyendo sólo los titulares. (-1:00)
4) Recortar la demo 1 a la mitad: se puede ir directo a la 2. (-1:30)
Nunca recortar: la 05 (los cinco veredictos), la demo 3 y la 38 (lo que el sistema no hace).

El apéndice (42-45) no se pasa: está para las preguntas.

## 03 · 01 · El problema

El enunciado parece pedir un buscador sobre un PDF. Los cinco accidentes que adjunta piden otra cosa.

## 04 · El enunciado pide un RAG sobre el manual; los cinco accidentes que adjunta piden criterio.

*01 · El problema*

EL ENCARGO (60 s).

Puntos a decir:
· El enunciado tiene dos mitades y sólo la primera es un problema de RAG clásico.
· La segunda mitad —«identificar partes, responsabilidad y circunstancias»— es un problema
  de aplicación de un convenio con condiciones cerradas. Si eso se resuelve generando texto,
  el sistema queda convincente y no demostrable.
· Los cinco accidentes de la derecha son los que vienen en el enunciado, literalmente.
  Los usé como criterio de aceptación desde el primer día y están en el golden set
  (case_id accident-01 … accident-05).

Enlace a la siguiente lámina: «Los resolví a mano contra el manual antes de escribir código.
Este fue el resultado.»

## 05 · En cuatro de los cinco casos, la respuesta correcta del manual es no concluir.

*01 · El problema*

LOS CINCO VEREDICTOS (90 s). Ésta es la lámina más importante del primer bloque.

Cómo contarla:
· «Antes de escribir una línea de código resolví los cinco casos a mano contra el manual.»
· Recorrer la columna de veredictos de arriba abajo y detenerse en el 4: es el único que se
  resuelve de forma determinista con lo que el propio relato aporta.
· El 2 es el más contraintuitivo: cinco vehículos parece el caso más grave y es el que se cae
  del Convenio por la puerta de entrada (dos vehículos, colisión directa).
· El 5 es el que más se presta a error: mucha gente asume que la alcoholemia excluye el
  Convenio. El manual dice lo contrario en la página 9. Lo que queda fuera son las lesiones
  y lo penal.

Si preguntan «¿entonces vuestro sistema no resuelve casi nada?»:
«Resuelve exactamente lo que el manual permite resolver con los datos del relato. En cuanto
el parte aporta las casillas del apartado 12, la tabla de culpabilidad de 324 celdas entra y
resuelve. Lo veréis en la demo.»

## 06 · Todo el sistema descansa sobre una sola regla: nada se afirma sin poder demostrarlo.

*01 · El problema*

LA TESIS (50 s). Lámina de transición: aquí se fija el criterio con el que hay que juzgar
todo lo que viene después.

· EVIDENCIA: el identificador de evidencia apunta al documento y la página física del PDF,
  no al fragmento del índice. Así una cita sigue siendo válida aunque se cambie el parser
  o el tamaño de chunk.
· DECISIÓN: es la inversión de control importante. El modelo no redacta la conclusión;
  rellena hechos con nombre y el motor de reglas decide.
· ABSTENCIÓN: el sistema tiene un estado explícito para «me falta este dato», y el grafo
  se interrumpe para pedirlo. No es un mensaje de error: es parte del flujo.

## 07 · 02 · Plan, supuestos y riesgos

Cinco días, cinco hitos comprobables. Ningún atajo que no esté escrito.

## 08 · Cinco días construidos de abajo arriba: primero la evidencia, después la inteligencia.

*02 · Plan*

EL PLAN (60 s).

· El orden no es casual: evidencia antes que inteligencia. El día 2 no genera ni una palabra
  con un LLM; sólo publica el manual de forma verificable. Sin eso, cualquier cita posterior
  sería una promesa.
· Cada hito es un comando, no una captura: make check, el recuento de páginas publicadas,
  una cita que abre el PDF, dos reglas resolviendo extremo a extremo, y la release congelada.
· La banda inferior es la gestión de riesgo de proyecto: el plan tenía una salida digna
  si la parte de reglas no salía. No hizo falta usarla.

Si preguntan por desviaciones: el día 4 se alargó. La transcripción de la tabla 18×18 se hizo
dos veces a propósito y eso consumió más de lo previsto; se recortó ampliar el golden a mano,
que se resolvió después con generación asistida y revisión adversarial.

## 09 · Seis supuestos declarados por escrito; ninguno escondido dentro del código.

*02 · Supuestos*

SUPUESTOS (45 s). Ir rápido: leer sólo los titulares en negrita y detenerse en dos.

· «Casillas A0–A17 externas al manual»: es el supuesto más importante y el que más se nota
  en el producto. El manual usa la tabla de culpabilidad pero no define qué maniobra es cada
  casilla — eso está en el impreso de la declaración amistosa. Lo resolví con un catálogo
  aparte, versionado y validado explícitamente, en vez de que el modelo lo adivine.
· «Ámbito administrativo dado por bueno»: si no lo asumiera, todos los casos acabarían
  pidiendo la matrícula y la aseguradora antes de decir nada. Está declarado en el golden.

## 10 · Los cinco riesgos que podían hundir esta prueba, y qué se hizo con cada uno.

*02 · Riesgos*

RIESGOS (60 s). No leer la columna de mitigaciones entera; contar dos y ofrecer el resto.

· Riesgo 1: es EL riesgo de un sistema así. La respuesta no es un prompt mejor: es que el
  modelo no tenga la última palabra. Hay una invariante en el dominio que lanza excepción
  si alguien intenta construir una decisión «resuelta» sin las reglas que la sostienen.
· Riesgo 2: la tabla de culpabilidad son 324 celdas leídas de un PDF de 2004. Un error de
  transcripción es un error de atribución de responsabilidad. Por eso se transcribió dos veces
  y hay un comando que compara ambas transcripciones.

Si preguntan por el riesgo 4 (golden ajustado al sistema): reconocer que es el más difícil
de cerrar del todo, y que la contramedida completa —abrir el holdout una sola vez tras
congelar— está definida y todavía no ejecutada.

## 11 · Seis decisiones técnicas, con el motivo y el precio que se pagó por cada una.

*02 · Decisiones*

DECISIONES (60 s). Es la lámina que el enunciado pide explícitamente («rationale behind the
main technical decisions»). Contar dos y dejar el resto para preguntas.

· Decisión 3 (reglas en artefacto firmado) es la que más se nota: el fichero de reglas lleva
  para cada regla su evidencia en el manual, su descripción, su consecuencia y el identificador
  de quien la revisó. Cambiar una regla no es cambiar código.
· Decisión 5 (híbrida): la búsqueda puramente semántica falla justo donde este manual es más
  útil — cuando alguien pregunta por «la b.10» o por «el artículo 35». BM25 en español
  recupera eso; los embeddings recuperan la intención. La fusión es determinista.

La banda inferior es el argumento de cierre del bloque: la arquitectura compra opcionalidad.

## 12 · 03 · Arquitectura

Evidencia, orquestación y decisión como capas separadas. Cambiar cualquiera de las tres sin tocar las otras dos.

## 13 · El núcleo de negocio no sabe que existen FastAPI, LangGraph, OpenAI ni Qdrant.

*03 · Arquitectura*

HEXAGONAL (75 s). Lámina central del bloque técnico.

Cómo contarla, de dentro afuera:
· El dominio contiene los modelos del Convenio y las reglas. No importa nada externo:
  ni FastAPI, ni LangGraph, ni el SDK de OpenAI, ni el cliente de Qdrant.
· La aplicación define los puertos: 5 de entrada (responder pregunta, analizar siniestro,
  resolver consulta, ingerir documento, inspeccionar manual) y 12 de salida.
· La infraestructura los implementa. Un nombre funcional conecta cada puerto con el
  directorio de su adaptador, así que la correspondencia se ve en el árbol de ficheros.

REMATE: ejecutar el grep de la banda inferior si alguien lo pide. Devuelve cero.
Es la diferencia entre decir «está desacoplado» y demostrarlo.

Si preguntan por el coste: más módulos (111 en el backend) y un bootstrap explícito que
compone las dependencias. A cambio, los tests de dominio no necesitan ni red ni contenedores.

## 14 · Cada pieza del stack es reemplazable porque ninguna está en el centro.

*03 · Arquitectura*

INTERCAMBIABILIDAD (55 s).

· El argumento fuerte no es el dibujo: es que la sustitución YA está ejercitada. pypdf y
  Docling están los dos publicados para el mismo manual, con dos índices distintos en Qdrant,
  y el dominio no distingue uno de otro.
· Los tres puertos de modelo separados son deliberados: generar texto, incrustar y clasificar
  el modo son capacidades distintas y podrían venir de proveedores distintos —o de un modelo
  local para la clasificación, que es la llamada más frecuente y más barata.

Si preguntan «¿esto no es sobreingeniería para cinco días?»: la respuesta honesta es que
costó tiempo el primer día y lo devolvió el cuarto, cuando hubo que meter la tabla de
culpabilidad en el flujo sin romper nada de lo anterior.

## 15 · El sistema usa un modelo para cuatro cosas distintas, y las trata como cuatro decisiones.

*03 · Modelos*

MODELOS (55 s). El enunciado evalúa explícitamente «la capacidad de seleccionar y usar
modelos de lenguaje apropiados». Ésta es esa lámina.

· El argumento: «¿qué modelo usáis?» es la pregunta equivocada. Son cuatro usos con
  exigencias distintas y cada uno está detrás de su propio puerto, así que pueden venir de
  proveedores distintos sin tocar el dominio.
· El router es el ejemplo más claro: es la llamada más frecuente del sistema y la más
  trivial —tres etiquetas—. Ahí un modelo pequeño o local es la decisión correcta en cuanto
  haya volumen, y el cambio es de configuración.
· El embedding es el único que NO se puede cambiar a la ligera: está en la firma del índice.
  Cambiarlo sin reindexar produciría respuestas peores sin que nadie supiera por qué, y por
  eso el alias se niega a moverse a un índice con firma incompatible.

La banda inferior es el punto de MLOps: los prompts viven versionados en Langfuse y la
configuración los fija por nombre y versión. Una ejecución dice con qué prompt corrió.

## 16 · Una sola conversación; tres recorridos deliberados y ninguno opaco.

*03 · Producto*

LOS TRES RECORRIDOS (45 s).

· El modo automático es el que se ve en la demo primero. Lo importante: el clasificador
  devuelve una etiqueta de un conjunto cerrado (question, claim, clarification_required),
  no una respuesta. No reescribe el texto del usuario ni lo enriquece.
· La interfaz enseña siempre qué recorrido se ha seguido, así que el enrutado nunca es una
  caja negra: si se equivoca, se ve, y hay dos botones para forzarlo.
· El tercero es donde está el trabajo de dominio. Se ve en las dos láminas siguientes.

## 17 · La interfaz enseña el razonamiento, no sólo la respuesta.

*03 · Producto*

LA INTERFAZ (50 s). Es una captura real, tomada del sistema corriendo hoy.
SALTABLE si la demo va bien: la demo 2 enseña esto mismo en vivo. Esta lámina es la red
de seguridad para contarlo sin sistema delante.

· Merece la pena detenerse en la columna de reglas que NO casan. Casi todas las demos
  esconden eso. Aquí es deliberado: si el sistema no puede aplicar la tabla de culpabilidad
  porque el relato no trae las casillas, se ve escrito, con el nombre de la regla.
· La consecuencia práctica: un tramitador que discrepe de la conclusión puede señalar el paso
  exacto donde discrepa — el hecho extraído, la regla aplicada o la redacción final.

Si preguntan por qué se enseñan identificadores técnicos como lane_change_acknowledged_by_both:
porque son los mismos nombres que aparecen en el artefacto de reglas firmado. Enseñar un
sinónimo bonito rompería la trazabilidad entre lo que se ve y lo que se evalúa.

## 18 · La ingesta no «sube un PDF»: publica una versión inmutable del conocimiento.

*03 · Evidencia*

INGESTA (60 s).

· Paso 1: el sistema no ingiere cualquier PDF. Comprueba el hash contra el manual verificado.
  En una prueba técnica parece exagerado; en un entorno real es la diferencia entre citar el
  manual y citar «un» manual.
· Paso 2: las páginas en blanco se conservan. Si se descartan, la página 57 del PDF deja de
  ser la 57 y todas las citas anteriores se corrompen en silencio.
· Paso 5: la firma de índice tiene 13 campos (parser, chunker, modelo de embeddings,
  dimensión, métrica de distancia…). Mover el alias a un índice con firma incompatible falla
  en vez de degradar los resultados sin avisar. Hay un comando de rollback y está probado.

La banda de abajo es el detalle que más se agradece a los seis meses: los IDs de evidencia
no dependen del parser, así que reindexar no invalida ni una cita del golden set.

## 19 · Una cita no es una nota al pie: abre el manual por la página que la sostiene.

*03 · Evidencia*

EVIDENCIA ABRIBLE (45 s). Segunda captura real.
SALTABLE si la demo va bien: la demo 1 abre esta misma cita en vivo.

· El detalle que suele pasar desapercibido y que más importa a los seis meses: el
  identificador de evidencia apunta al documento y a la página física, no al fragmento del
  índice. Reindexar con otro parser no invalida ni una cita.
· Página física vs. etiqueta impresa: en este manual no siempre coinciden, y confundirlas
  produce citas que parecen correctas y no lo son. Se guardan por separado.
· Y la honestidad del visor: sin coordenadas verificadas se abre la página completa en vez
  de pintar un resaltado inventado.

## 20 · Dos métodos de ingesta conviven publicados; sólo la evaluación decide cuál se activa.

*03 · Evidencia*

DOS PARSERS (55 s). Ésta suele generar pregunta.

· Docling es objetivamente más capaz: da layout, regiones y bounding boxes por página, que
  es lo que haría falta para resaltar la frase exacta dentro del PDF en vez de abrir la
  página entera.
· Y aun así el índice activo en la demo es el de pypdf. El motivo está en la banda inferior:
  no tengo todavía la comparación de evaluación que demuestre que mejora las respuestas.
  Activarlo porque es más sofisticado sería exactamente el vicio que este proyecto intenta
  evitar.

Si preguntan cuándo se activaría: en cuanto la campaña de evaluación dé métricas de
recuperación y de fidelidad de citas para los dos perfiles sobre los mismos 110 casos.
Es el punto 2 del roadmap.

## 21 · Recuperación híbrida: la semántica encuentra el concepto, BM25 encuentra «b.10».

*03 · Recuperación*

RECUPERACIÓN (55 s).

· El ejemplo concreto que convence: si alguien pregunta «¿qué dice la b.10?», un índice
  puramente vectorial devuelve normas parecidas; BM25 devuelve la b.10. Y al revés: si
  preguntan «¿quién responde cuando uno sale de un garaje?», el léxico no encuentra nada
  y los embeddings sí.
· La fusión es RRF nativo de Qdrant: determinista y en el motor, no un reordenamiento
  hecho a mano en Python que nadie podría reproducir.
· La fila de abajo es gobierno del índice y es lo que hace que esto sea operable: la firma
  de 13 campos evita el fallo clásico de reindexar con otro modelo de embeddings y que las
  respuestas empeoren sin que nadie sepa por qué.

## 22 · El grafo documental es corto, tipado, y no entrega nada sin validarlo antes.

*03 · Workflows*

GRAFO DOCUMENTAL (45 s).

· Tres nodos y ya está. La complejidad de un RAG no está en el grafo, está en lo que rodea
  al grafo: la evidencia por debajo y la validación por arriba.
· El límite de 8 fragmentos es deliberado: más contexto no mejora la respuesta y sí empeora
  la trazabilidad, porque diluye qué fragmento sostiene qué afirmación.
· Los cuatro estados de abajo son la parte que la mayoría de demos esconde. insufficient_
  evidence y out_of_scope son respuestas correctas, y la interfaz las enseña tal cual.

## 23 · El grafo de siniestros se interrumpe y pregunta antes que inventar.

*03 · Workflows*

GRAFO DE SINIESTROS (75 s). Es la lámina técnica que más diferencia esta prueba.

· apply_rules (el nodo oscuro) es donde ocurre todo lo determinista: puerta de aplicabilidad,
  reglas subsidiarias y tabla de culpabilidad. El LLM ya ha terminado su trabajo antes.
· La salida lateral es human-in-the-loop de verdad, con interrupt() de LangGraph y un
  checkpoint. No es «te devuelvo un error y vuelve a escribirlo todo»: el hilo se reanuda
  en el mismo punto con Command(resume=…).
· El ejemplo de la derecha es literal del manual (pág. 101): una de las cuatro observaciones
  impresas bajo la tabla de culpabilidad. Se ve en la demo 3.

Si preguntan por el coste de la interrupción: el estado vive en el checkpointer del grafo,
asociado al hilo. En esta prueba es memoria del proceso; en producción sería una base
persistente, y es un cambio de adaptador, no de diseño.

## 24 · Del lenguaje natural a una decisión auditable, sin ningún salto mágico.

*03 · Motor de reglas*

DEL RELATO A LA DECISIÓN (60 s).

· Recorrer la cadena de izquierda a derecha una vez, despacio. Es el corazón del sistema.
· La caja azul oscuro del centro es un fichero JSON firmado, no código: cada regla lleva su
  identificador, su evidencia en el manual, su descripción, su consecuencia y el identificador
  de quien la revisó.
· La primera garantía de abajo es sutil pero importante: la lista de nombres de hecho que el
  prompt de extracción pide se deriva del ruleset. Si mañana se añade una regla que consulta
  un hecho nuevo, el extractor empieza a pedirlo. No hay dos listas que se desincronicen.
· La tercera garantía es una excepción de dominio de verdad: si el código intentara publicar
  una decisión resuelta sin reglas que la sostengan, lanza. Me saltó a mí durante el
  desarrollo y por eso está.

## 25 · La tabla de culpabilidad se transcribió dos veces a mano — por eso se puede confiar en ella.

*03 · Motor de reglas*

LA TABLA 18×18 (70 s). Es la parte de la que más orgulloso estoy y la que más incomoda
contar, porque el trabajo fue manual a propósito.

· 324 celdas. Un OCR o un extractor de tablas habría dado un resultado plausible y nadie
  habría podido saber si era correcto. Aquí un error de transcripción cambia quién paga.
· Por eso: dos transcripciones independientes, un comando que las compara, y una firma.
· Las cuatro observaciones impresas bajo la tabla («A2+B4 = culpable B, salvo que el A abra
  la puerta») están declaradas de forma estructurada en el artefacto. No hay un if en el
  código que sepa de puertas.
· La banda de abajo es el límite que más se defiende solo: si el parte no trae las casillas
  marcadas, no las deducimos de la narración. Ese dato lo firman los conductores.

Aviso honesto si preguntan: la retícula de colores de la izquierda es ilustrativa, para que
se vea la densidad. La transcripción real está en el artefacto firmado y se puede abrir.

## 26 · 13 de las 14 reglas firmadas ya deciden; la que falta se declara, no se disimula.

*03 · Motor de reglas*

ESTADO DE LAS REGLAS (50 s). Lámina de honestidad dentro del bloque técnico.

· La puerta de aplicabilidad está completa desde el día 4: es lo que permite decir «fuera
  del Convenio» con fundamento en los casos 2 y 3 del enunciado.
· De las normas subsidiarias, seis están conectadas más la tabla de culpabilidad.
· Falta una: b.11, rotondas. Y la explico porque el motivo es interesante: su excepción no
  retira la atribución, la sustituye («culpable quien accede, salvo que ambos tengan daños
  laterales no angulares, en cuyo caso responde el del lateral derecho»). Eso no es rellenar
  un predicado: es una segunda regla con su propia condición mutuamente excluyente.
· Mientras no esté, devuelve insufficient_data. No finge.

## 27 · 04 · Demo en vivo

Cuatro recorridos sobre el sistema real, en local. Lo que hay que creerse no son las láminas.

## 28 · Demo 1 — Enrutado y consulta documental

*04 · Demo en vivo*

DEMO 1 — Enrutado y consulta documental

Guion en pantalla:
· Escribir la pregunta en modo Automático (sin elegir modo).
· Señalar la etiqueta de modo detectado ANTES de leer la respuesta.
· Pulsar la cita y dejar que se vea el PDF abrirse por la página 9.
· Si alguien pregunta por el resaltado: con el índice activo (pypdf) no hay coordenadas
· verificadas, así que se abre la página completa en vez de fingir un resaltado. Con el
· perfil Docling sí las habría. Es la decisión de la lámina de parsers.

Antes de empezar la demo: make local-services-up, make serve-backend, make serve-frontend,
y comprobar GET /health/ready → {"status":"ready"}. Tener Langfuse ya abierto en otra pestaña.

## 29 · Demo 2 — El siniestro que sí se resuelve

*04 · Demo en vivo*

DEMO 2 — El siniestro que sí se resuelve

Guion en pantalla:
· Usar el ejemplo de demo, no escribir el relato a mano (ahorra 40 segundos).
· Expandir «Reglas evaluadas» y recorrer los hechos: insistir en que llevan el texto literal.
· Leer la conclusión en voz alta y abrir la cita de la página 75.
· Rematar: «El modelo no ha decidido esto. Ha rellenado tres hechos y el motor ha aplicado
· una norma firmada que cualquiera puede leer en el artefacto.»

Antes de empezar la demo: make local-services-up, make serve-backend, make serve-frontend,
y comprobar GET /health/ready → {"status":"ready"}. Tener Langfuse ya abierto en otra pestaña.

## 30 · Demo 3 — Abstenerse con criterio, y pedir el dato exacto

*04 · Demo en vivo*

DEMO 3 — Abstenerse con criterio, y pedir el dato exacto

Guion en pantalla:
· Empezar por la colisión múltiple: es el caso que más sorprende (cinco coches, y se cae del
· Convenio por la puerta de entrada).
· Después la matriz: declarar las casillas en el relato, provocar la interrupción, responder
· primero «abrió la puerta el de B» y luego repetir con «el de A» para enseñar las dos ramas.
· Cerrar con la pregunta fuera de alcance (baremo de lesiones): comprobar que NO da cifras.

· Es la demo más importante de las cuatro. Si hay que recortar tiempo, recortar la 1, no ésta.

Antes de empezar la demo: make local-services-up, make serve-backend, make serve-frontend,
y comprobar GET /health/ready → {"status":"ready"}. Tener Langfuse ya abierto en otra pestaña.

## 31 · Demo 4 — Trazabilidad y operación

*04 · Demo en vivo*

DEMO 4 — Trazabilidad y operación

Guion en pantalla:
· Abrir la traza del caso de la demo 2 desde el enlace «Ver en Langfuse» de la propia respuesta.
· Enseñar el desglose por etapa: es donde se ve que el coste real por consulta es pequeño.
· Pasar al modo administrador y enseñar la previsualización de la extracción.
· Rematar con la frase de la banda: producto, modelo y evaluación miran la misma traza.

Antes de empezar la demo: make local-services-up, make serve-backend, make serve-frontend,
y comprobar GET /health/ready → {"status":"ready"}. Tener Langfuse ya abierto en otra pestaña.

## 32 · 05 · Evaluación y límites

110 casos de referencia, un protocolo de medida y una lista explícita de lo que este sistema no hace.

## 33 · 110 casos de referencia construidos contra el manual, no contra el sistema.

*05 · Evaluación*

GOLDEN SET (60 s).

· El punto no es el número. Es que hay una referencia escrita ANTES de mirar lo que el
  sistema contesta, y que está anclada a páginas concretas del manual.
· Los cinco del enunciado son el criterio de aceptación. Los resolví a mano el primer día:
  es la tabla del bloque 01.
· Los 100 sintéticos se generaron a partir del manual y se revisaron de forma adversarial.
  No se aceptaron tal cual: hay una pasada que corrigió paquetes de evidencia demasiado
  estrictos y requisitos sin cita que los sostuviera.
· La release se congela con hash de contenido y de esquema. Eso es lo que impide el vicio
  clásico de retocar el golden cuando los resultados no gustan.

## 34 · Un caso golden no guarda una respuesta: guarda qué debe cumplirse y qué está prohibido.

*05 · Evaluación*

ANATOMÍA DE UN CASO (55 s).

· La idea clave: comparar texto con texto no sirve. «El Convenio no es de aplicación» y
  «este siniestro queda fuera del Convenio» son la misma respuesta. Por eso la referencia
  es una especificación con requisitos, alternativas aceptables y prohibiciones.
· forbidden_facts es mi campo favorito: recoge los errores plausibles. En el alcance por
  detrás, presumir la culpa del que alcanza es exactamente lo que un modelo haría por
  sentido común, y el manual no lo sostiene.
· La banda ámbar es deliberada. Es la limitación más seria del trabajo de evaluación y
  prefiero decirla yo antes de que la pregunten: la revisión es de IA, en tres pasos y
  documentada, pero no es un perito humano.

## 35 · La evaluación está diseñada como un experimento, no como una captura de pantalla.

*05 · Evaluación*

PROTOCOLO DE EVALUACIÓN (60 s). Lámina delicada: hay que ser exacto.
COMPROBADO el 2026-09-03: allianz golden validate devuelve errors: [] e item_count: 110,
y el proyecto de Langfuse en uso todavía no tiene el dataset publicado (la API de datasets
devuelve 0). Por eso la caja ámbar lo pone en "en curso" y no en "construido".

· Contar primero el protocolo. Es lo que se está evaluando en esta prueba: si sé montar una
  evaluación creíble, no si tengo un número bonito.
· «Abstención correcta» como métrica principal es la consecuencia directa del bloque 01:
  en cuatro de los cinco casos del enunciado, acertar es abstenerse.
· La caja ámbar es el estado real. Decirla tal cual, sin apurarse:
  hecho = golden + release congelada + dataset + runner documental;
  en curso = campaña completa y evaluadores de siniestro y router;
  pendiente = holdout, que se abre una sola vez y por eso no se ha abierto.

SI PARA ENTONCES HAY NÚMEROS: sustituir la caja ámbar por las métricas reales
(precisión de enrutado, fidelidad de citas, abstención correcta) e indicar sobre qué
release y qué commit se midieron. No añadir ninguna métrica que no venga de una ejecución.

## 36 · Cada ejecución deja huella: producto, modelo y evaluación miran la misma traza.

*05 · Operación*

OBSERVABILIDAD (45 s).

· Insistir en lo de autoalojado: el material de entrada de este sistema son relatos de
  siniestro. Mandarlos a un SaaS de observabilidad para una prueba técnica habría sido
  cómodo y equivocado.
· El argumento de producto: el enlace de cada respuesta lleva a SU traza. Cuando alguien
  discuta una conclusión, se abre la ejecución exacta con los hechos extraídos, las reglas
  evaluadas y las llamadas al modelo.
· Y el argumento de ingeniería: datasets y experimentos viven en el mismo sitio, así que la
  evaluación no es un cuaderno aparte que se desincroniza.

## 37 · Nada entra sin pasar cinco puertas, y las cinco están verdes hoy.

*05 · Ingeniería*

GATES (40 s). Ir rápido, es una lámina de confianza, no de contenido.

· Las cifras están medidas hoy sobre este repositorio, no son de memoria.
· El punto que merece detenerse: la deriva de contrato. El frontend no tiene una segunda
  definición manual de los tipos de la API; se generan del OpenAPI que publica FastAPI, y
  hay una comprobación que falla si el contrato y el código se separan.
· El tercer bloque de abajo es consecuencia directa de la arquitectura hexagonal: el dominio
  se prueba sin levantar Qdrant ni llamar a ningún modelo.

## 38 · Lo que este sistema no hace — dicho aquí, y no en la letra pequeña.

*05 · Límites*

LÍMITES (50 s). Contarla entera y sin prisa. Es la lámina que más credibilidad da.

Frase de entrada: «Esta es la lámina que normalmente no está en una presentación de
entrega. Va aquí porque es exactamente el mismo criterio que hace que el sistema se
abstenga en un siniestro.»

· El límite 3 es el más importante del dominio: no deducimos las casillas del apartado 12.
· El límite 4 es el más importante de la evaluación: revisión de IA, no de perito.
· El límite 5 es el que un evaluador técnico agradecerá: los 110 casos están en desarrollo.
  Medir sobre ellos y llamarlo generalización sería trampa, y por eso el holdout se abre
  una sola vez.

## 39 · La siguiente iteración avanza por evidencia, no por disponibilidad.

*05 · Siguiente iteración*

ROADMAP (40 s).

· El orden es el mensaje. Los cuatro puntos podrían hacerse en cualquier orden y he elegido
  éste porque los dos primeros son mediciones y los dos últimos son consecuencias.
· Punto 3: reconocer que es la limitación más seria y también la más barata de cerrar.
  Una tarde de una persona del negocio revisando cinco casos vale más que cien sintéticos.
· Cerrar señalando que ninguno de los cuatro toca el dominio: es la factura que paga la
  arquitectura del bloque 03.

## 40 · No es un chatbot sobre un PDF.

*Cierre*

CIERRE (30 s) y paso a preguntas.

Frase de cierre sugerida:
«Si me tuviera que quedar con una sola idea de todo esto: el sistema se abstiene cuando el
manual no da para más, y esa abstención está tan trabajada como las respuestas. En un dominio
donde la salida es quién paga un siniestro, un asistente que siempre responde no es más útil:
es más peligroso.»

Tener abierto en otra ventana: docs/ESTADO.md, data/rules/ruleset.v1.json, la traza de
Langfuse del caso 4 y el golden congelado. Las láminas del apéndice cubren stack, API,
glosario y comandos.

## 41 · A · Apéndice

Material de apoyo para las preguntas: stack, API, glosario del dominio y comandos reproducibles.

## 42 · Las preguntas incómodas, con la respuesta corta y dónde está la larga.

*Apéndice · Preguntas*

Apéndice. NO se pasa en la presentación: está para tenerla a mano en el turno de preguntas
y para repasarla cinco minutos antes de entrar.

La columna de la derecha dice a qué lámina saltar si conviene enseñarla al responder.

## 43 · Stack completo, y el puerto por el que cada pieza es sustituible.

*Apéndice · Stack*

Apéndice. Sólo si preguntan por el stack. La columna de la derecha explica el porqué de cada elección, que suele ser la pregunta real.

## 44 · Superficie de API: un sobre común tipado para los tres recorridos.

*Apéndice · API*

Apéndice. El sobre de respuesta es común a los tres recorridos: identifica el modo seguido, las etapas ejecutadas, las citas y el estado. Es lo que permite que la interfaz enseñe el razonamiento sin lógica duplicada.

## 45 · Glosario mínimo del dominio, para que nadie asienta sin seguirlo.

*Apéndice · Dominio*

Apéndice. Útil si en la sala hay perfiles no aseguradores. Los cinco primeros términos aparecen en la demo.

## 46 · Todo lo que se ha enseñado se reproduce con estos comandos.

*Apéndice · Reproducibilidad*

Apéndice. Si alguien quiere verificar algo en el momento, está aquí. Todos se ejecutan en local y ninguno necesita credenciales externas salvo la clave del modelo.

