import {
  W, H, M, CW, RIGHT, C, F, tb, rect, rrect, ell, card, pill, chip, dot, arrow,
  title, deck, band, notes, page, divider, hline,
} from './lib.mjs';

export function chapterThree(pres, ctx) {
  divider(pres, ctx, {
    num: '03',
    name: 'Arquitectura',
    promise: 'Evidencia, orquestación y decisión como capas separadas.\nCambiar cualquiera de las tres sin tocar las otras dos.',
  });
  hexagonal(pres, ctx);
  intercambiable(pres, ctx);
  modelos(pres, ctx);
  recorridos(pres, ctx);
  interfaz(pres, ctx);
  ingesta(pres, ctx);
  evidenciaAbrible(pres, ctx);
  parsers(pres, ctx);
  retrieval(pres, ctx);
  grafoDocumental(pres, ctx);
  grafoSiniestros(pres, ctx);
  relatoADecision(pres, ctx);
  matriz(pres, ctx);
  estadoReglas(pres, ctx);
}

/* ------------------------------------------------------------- hexagonal */

function hexagonal(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Arquitectura' });
  title(s, 'El núcleo de negocio no sabe que existen FastAPI, LangGraph, OpenAI ni Qdrant.');
  deck(s, 'El dominio define el problema, la aplicación define los puertos, la infraestructura los implementa.');

  // Anillo de aplicación y núcleo de dominio.
  rrect(s, { x: 3.62, y: 2.62, w: 6.1, h: 2.86, rectRadius: 0.14, fill: { color: C.band } });
  tb(s, 'APLICACIÓN', {
    x: 3.62, y: 2.8, w: 6.1, h: 0.26, align: 'center',
    fontFace: F.head, fontSize: 11, bold: true, charSpacing: 1.4, color: C.navy,
  });
  tb(s, 'casos de uso · servicios · 5 puertos de entrada · 12 puertos de salida', {
    x: 3.62, y: 3.06, w: 6.1, h: 0.24, align: 'center', fontSize: 11, color: C.navy,
  });

  rrect(s, { x: 4.28, y: 3.44, w: 4.78, h: 1.72, rectRadius: 0.12, fill: { color: C.navy } });
  tb(s, 'DOMINIO', {
    x: 4.28, y: 3.72, w: 4.78, h: 0.4, align: 'center',
    fontFace: F.head, fontSize: 20, bold: true, color: C.paper,
  });
  tb(s, 'modelos · reglas del Convenio · decisiones\ncero dependencias externas', {
    x: 4.28, y: 4.18, w: 4.78, h: 0.66, align: 'center', fontSize: 12, color: C.pale, lineSpacingMultiple: 1.1,
  });

  // Adaptadores de entrada (izquierda) y de salida (derecha).
  const inbound = [['API HTTP + SSE', 'FastAPI'], ['Línea de comandos', 'allianz']];
  tb(s, 'ADAPTADORES DE ENTRADA', {
    x: M, y: 2.32, w: 2.7, h: 0.24, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft,
  });
  inbound.forEach(([a, b], i) => {
    const y = 3.32 + i * 0.86;
    card(s, { x: M, y, w: 2.7, h: 0.68, fill: C.ice });
    tb(s, a, { x: M + 0.18, y: y + 0.11, w: 2.34, h: 0.24, fontSize: 12.5, bold: true, color: C.ink });
    tb(s, b, { x: M + 0.18, y: y + 0.37, w: 2.34, h: 0.22, fontFace: F.mono, fontSize: 10, color: C.muted });
    s.addShape('line', { x: M + 2.7, y: y + 0.34, w: 0.92, h: 0, line: { color: C.blue, width: 1.25 } });
  });

  const outbound = [
    ['Orquestación', 'LangGraph'],
    ['Modelos y embeddings', 'OpenAI'],
    ['Índice vectorial y léxico', 'Qdrant'],
    ['Extracción del PDF', 'pypdf · Docling'],
    ['Trazas y experimentos', 'Langfuse'],
  ];
  const xr = RIGHT - 2.7;
  tb(s, 'ADAPTADORES DE SALIDA', {
    x: xr, y: 2.32, w: 2.7, h: 0.24, align: 'right', fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft,
  });
  outbound.forEach(([a, b], i) => {
    const y = 2.66 + i * 0.58;
    card(s, { x: xr, y, w: 2.7, h: 0.52, fill: C.ice });
    tb(s, a, { x: xr + 0.16, y: y + 0.06, w: 2.4, h: 0.22, fontSize: 11.5, bold: true, color: C.ink });
    tb(s, b, { x: xr + 0.16, y: y + 0.28, w: 2.4, h: 0.2, fontFace: F.mono, fontSize: 9.5, color: C.muted });
    s.addShape('line', { x: 9.72, y: y + 0.26, w: xr - 9.72, h: 0, line: { color: C.blue, width: 1.25 } });
  });

  // La prueba: el dominio no importa ninguna de esas tecnologías.
  rrect(s, { x: M, y: 6.26, w: CW, h: 0.62, rectRadius: 0.1, fill: { color: C.navy } });
  tb(s, 'grep -rE "fastapi|langgraph|openai|qdrant" backend/src/domain/', {
    x: M + 0.3, y: 6.42, w: 5.9, h: 0.3, fontFace: F.mono, fontSize: 11, color: C.sky,
  });
  tb(s, '→   0 resultados.   La frontera no es una intención de diseño: es comprobable.', {
    x: 6.9, y: 6.41, w: 5.5, h: 0.3, fontSize: 12, bold: true, color: C.paper,
  });

  notes(s, [
    'HEXAGONAL (75 s). Lámina central del bloque técnico.',
    '',
    'Cómo contarla, de dentro afuera:',
    '· El dominio contiene los modelos del Convenio y las reglas. No importa nada externo:',
    '  ni FastAPI, ni LangGraph, ni el SDK de OpenAI, ni el cliente de Qdrant.',
    '· La aplicación define los puertos: 5 de entrada (responder pregunta, analizar siniestro,',
    '  resolver consulta, ingerir documento, inspeccionar manual) y 12 de salida.',
    '· La infraestructura los implementa. Un nombre funcional conecta cada puerto con el',
    '  directorio de su adaptador, así que la correspondencia se ve en el árbol de ficheros.',
    '',
    'REMATE: ejecutar el grep de la banda inferior si alguien lo pide. Devuelve cero.',
    'Es la diferencia entre decir «está desacoplado» y demostrarlo.',
    '',
    'Si preguntan por el coste: más módulos (111 en el backend) y un bootstrap explícito que',
    'compone las dependencias. A cambio, los tests de dominio no necesitan ni red ni contenedores.',
  ].join('\n'));
}

/* -------------------------------------------------------- intercambiable */

function intercambiable(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Arquitectura', dark: true });
  title(s, 'Cada pieza del stack es reemplazable porque ninguna está en el centro.', { dark: true, size: 29 });
  deck(s, 'La prueba de que la frontera es real no es el diagrama: es que dos parsers y dos índices ya conviven publicados sin que el dominio se haya enterado.', { dark: true, y: 2.02 });

  const cols = [
    ['ORQUESTACIÓN', 'LangGraph', 'question_workflow\nclaim_workflow\nquery_workflow', 'Los casos de uso hablan con un puerto. Sustituir el orquestador no toca el dominio.'],
    ['INGESTA', 'pypdf · Docling', 'document_parser\nevidence_repository', 'Dos parsers publicados a la vez para el mismo documento verificado.'],
    ['RECUPERACIÓN', 'Qdrant híbrido', 'retriever\nindex_publisher', 'Denso, BM25 y fusión son política del adaptador, no del caso de uso.'],
    ['MODELOS', 'OpenAI', 'language_model\nembedding_provider\nquery_classifier', 'Tres puertos distintos: generar, incrustar y clasificar no son la misma capacidad.'],
  ];

  const cw = 2.828, y0 = 2.62, ch = 3.34;
  cols.forEach(([head, now, ports, why], i) => {
    const x = M + i * (cw + 0.26);
    card(s, { x, y: y0, w: cw, h: ch, dark: true });
    tb(s, head, { x: x + 0.26, y: y0 + 0.28, w: cw - 0.52, h: 0.24, fontFace: F.head, fontSize: 10.5, bold: true, charSpacing: 1.2, color: C.sky });
    tb(s, now, { x: x + 0.26, y: y0 + 0.6, w: cw - 0.52, h: 0.34, fontFace: F.head, fontSize: 17, bold: true, color: C.paper });
    rrect(s, { x: x + 0.26, y: y0 + 1.06, w: cw - 0.52, h: 0.96, rectRadius: 0.08, fill: { color: C.deep } });
    tb(s, ports, { x: x + 0.4, y: y0 + 1.16, w: cw - 0.8, h: 0.8, fontFace: F.mono, fontSize: 9.5, color: C.sky, lineSpacingMultiple: 1.1 });
    tb(s, why, { x: x + 0.26, y: y0 + 2.2, w: cw - 0.52, h: 1.0, fontSize: 11.5, color: C.pale, lineSpacingMultiple: 1.06 });
  });

  band(s, '12 puertos de salida y 5 de entrada. Ninguna decisión del Convenio cambia si mañana se sustituye el proveedor de modelos, el índice o el orquestador.', { tone: 'dark', y: 6.24 });

  notes(s, [
    'INTERCAMBIABILIDAD (55 s).',
    '',
    '· El argumento fuerte no es el dibujo: es que la sustitución YA está ejercitada. pypdf y',
    '  Docling están los dos publicados para el mismo manual, con dos índices distintos en Qdrant,',
    '  y el dominio no distingue uno de otro.',
    '· Los tres puertos de modelo separados son deliberados: generar texto, incrustar y clasificar',
    '  el modo son capacidades distintas y podrían venir de proveedores distintos —o de un modelo',
    '  local para la clasificación, que es la llamada más frecuente y más barata.',
    '',
    'Si preguntan «¿esto no es sobreingeniería para cinco días?»: la respuesta honesta es que',
    'costó tiempo el primer día y lo devolvió el cuarto, cuando hubo que meter la tabla de',
    'culpabilidad en el flujo sin romper nada de lo anterior.',
  ].join('\n'));
}

/* ---------------------------------------------------------------- modelos */

function modelos(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Modelos' });
  title(s, 'El sistema usa un modelo para cuatro cosas distintas, y las trata como cuatro decisiones.');
  deck(s, '«Elegir el modelo» no es una decisión, son cuatro: cada uso tiene su exigencia, su coste y su frecuencia — y cada uno vive detrás de su propio puerto.');

  const uses = [
    ['RESPONDER', 'Generación documental', 'OPENAI_ANSWER_MODEL',
      'Redacta sólo sobre el contexto recuperado y con una cita por bloque. Es la llamada que más exige en calidad de escritura y respeto a la fuente.', C.navy],
    ['EXTRAER', 'Hechos del siniestro', 'OPENAI_CLAIM_EXTRACTION_MODEL',
      'Salida estructurada con esquema cerrado (extra="forbid", strict). No redacta la conclusión: rellena un vocabulario de hechos con nombre.', C.blue],
    ['CLASIFICAR', 'Intención del usuario', 'ALLIANZ_ROUTER_MODEL',
      'Tres etiquetas y nada más. Es la llamada más frecuente y la más barata: candidata natural a un modelo pequeño, o local.', C.teal],
    ['INCRUSTAR', 'El manual, una sola vez', 'text-embedding-3-small\n1536 dimensiones · coseno',
      'Fijado en el perfil del índice y grabado en su firma de 13 campos: cambiarlo obliga a reindexar, y el sistema no deja hacerlo por accidente.', C.amber],
  ];

  const cw = 2.828, y0 = 2.5, ch = 3.3;
  uses.forEach(([tag, name, cfg, desc, color], i) => {
    const x = M + i * (cw + 0.26);
    card(s, { x, y: y0, w: cw, h: ch });
    tb(s, tag, { x: x + 0.26, y: y0 + 0.28, w: cw - 0.52, h: 0.24, fontFace: F.head, fontSize: 10.5, bold: true, charSpacing: 1.2, color });
    tb(s, name, { x: x + 0.26, y: y0 + 0.58, w: cw - 0.52, h: 0.56, fontFace: F.head, fontSize: 15, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    rrect(s, { x: x + 0.26, y: y0 + 1.2, w: cw - 0.52, h: 0.6, rectRadius: 0.08, fill: { color: C.ice } });
    tb(s, cfg, { x: x + 0.36, y: y0 + 1.3, w: cw - 0.72, h: 0.44, fontFace: F.mono, fontSize: 8.5, color: C.navy, lineSpacingMultiple: 1.1 });
    tb(s, desc, { x: x + 0.26, y: y0 + 1.94, w: cw - 0.52, h: 1.2, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.06 });
  });

  band(s, 'Y los prompts no se editan: se versionan. La configuración los fija por nombre y versión —document-question v1, auto-router v1—, así que cambiar un prompt es publicar una versión trazable, no una edición silenciosa.', { tone: 'navy' });

  notes(s, [
    'MODELOS (55 s). El enunciado evalúa explícitamente «la capacidad de seleccionar y usar',
    'modelos de lenguaje apropiados». Ésta es esa lámina.',
    '',
    '· El argumento: «¿qué modelo usáis?» es la pregunta equivocada. Son cuatro usos con',
    '  exigencias distintas y cada uno está detrás de su propio puerto, así que pueden venir de',
    '  proveedores distintos sin tocar el dominio.',
    '· El router es el ejemplo más claro: es la llamada más frecuente del sistema y la más',
    '  trivial —tres etiquetas—. Ahí un modelo pequeño o local es la decisión correcta en cuanto',
    '  haya volumen, y el cambio es de configuración.',
    '· El embedding es el único que NO se puede cambiar a la ligera: está en la firma del índice.',
    '  Cambiarlo sin reindexar produciría respuestas peores sin que nadie supiera por qué, y por',
    '  eso el alias se niega a moverse a un índice con firma incompatible.',
    '',
    'La banda inferior es el punto de MLOps: los prompts viven versionados en Langfuse y la',
    'configuración los fija por nombre y versión. Una ejecución dice con qué prompt corrió.',
  ].join('\n'));
}

/* ------------------------------------------------------------- recorridos */

function recorridos(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Producto' });
  title(s, 'Una sola conversación; tres recorridos deliberados y ninguno opaco.');
  deck(s, 'El usuario puede elegir el recorrido o dejar que el sistema lo encamine. Lo que no puede pasar es que no sepa cuál se ha seguido.');

  const modes = [
    ['MODO AUTOMÁTICO', 'por defecto', 'classify → consulta | siniestro',
      'Un clasificador de salida cerrada decide el recorrido. Recibe el texto del usuario sin reescribirlo y nunca ve la respuesta esperada.',
      'POST /api/v1/queries/resolve', C.navy],
    ['CONSULTAR EL MANUAL', 'explícito', 'retrieve → generate → validate',
      'Respuesta por bloques y cada bloque con su cita. Al pulsarla se abre el PDF original por la página que la sostiene.',
      'POST /api/v1/questions/answer', C.blue],
    ['ANALIZAR SINIESTRO', 'explícito', 'extract → retrieve → apply_rules → explain → validate',
      'Hechos atribuidos, reglas evaluadas —las que casan y las que no— y una decisión resuelta, condicionada o indeterminada.',
      'POST /api/v1/claims/analyze', C.teal],
  ];

  const cw = 3.831, y0 = 2.52, ch = 3.5;
  modes.forEach(([head, tag, flow, desc, ep, color], i) => {
    const x = M + i * (cw + 0.3);
    card(s, { x, y: y0, w: cw, h: ch });
    ell(s, { x: x + 0.3, y: y0 + 0.3, w: 0.34, h: 0.34, fill: { color } });
    tb(s, String(i + 1), { x: x + 0.3, y: y0 + 0.37, w: 0.34, h: 0.22, align: 'center', fontFace: F.head, fontSize: 11, bold: true, color: C.paper });
    tb(s, head, { x: x + 0.76, y: y0 + 0.34, w: cw - 1.1, h: 0.26, fontFace: F.head, fontSize: 13.5, bold: true, color: C.ink });
    tb(s, tag, { x: x + 0.76, y: y0 + 0.6, w: cw - 1.1, h: 0.22, fontSize: 10.5, italic: true, color: C.soft });

    rrect(s, { x: x + 0.3, y: y0 + 1.0, w: cw - 0.6, h: 0.74, rectRadius: 0.08, fill: { color: C.ice } });
    tb(s, flow, { x: x + 0.44, y: y0 + 1.12, w: cw - 0.88, h: 0.56, fontFace: F.mono, fontSize: 9.5, color: C.navy, lineSpacingMultiple: 1.12 });

    tb(s, desc, { x: x + 0.3, y: y0 + 1.92, w: cw - 0.6, h: 1.1, fontSize: 12, color: C.muted, lineSpacingMultiple: 1.06 });
    tb(s, ep, { x: x + 0.3, y: y0 + 3.02, w: cw - 0.6, h: 0.3, fontFace: F.mono, fontSize: 9.5, color: color });
  });

  band(s, 'Los modos explícitos se saltan el router por completo: nadie queda a merced de una clasificación que no pidió.', { tone: 'navy', y: 6.26 });

  notes(s, [
    'LOS TRES RECORRIDOS (45 s).',
    '',
    '· El modo automático es el que se ve en la demo primero. Lo importante: el clasificador',
    '  devuelve una etiqueta de un conjunto cerrado (question, claim, clarification_required),',
    '  no una respuesta. No reescribe el texto del usuario ni lo enriquece.',
    '· La interfaz enseña siempre qué recorrido se ha seguido, así que el enrutado nunca es una',
    '  caja negra: si se equivoca, se ve, y hay dos botones para forzarlo.',
    '· El tercero es donde está el trabajo de dominio. Se ve en las dos láminas siguientes.',
  ].join('\n'));
}

/* --------------------------------------------------------------- interfaz */

const SHOT = (name) => new URL(`./assets/${name}.png`, import.meta.url).pathname;

function interfaz(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Producto' });
  title(s, 'La interfaz enseña el razonamiento, no sólo la respuesta.');
  deck(s, 'Captura real resolviendo un cambio de carril: los hechos extraídos, las catorce reglas evaluadas y la decisión que resulta.');

  // Marco del pantallazo, para que se lea como producto y no como adorno.
  const ih = 4.42, iw = ih * 0.843, ix = RIGHT - iw, iy = 2.36;
  rrect(s, { x: ix - 0.06, y: iy - 0.06, w: iw + 0.12, h: ih + 0.12, rectRadius: 0.08, fill: { color: C.navy } });
  s.addImage({ path: SHOT('ui-reasoning'), x: ix, y: iy, w: iw, h: ih });

  const items = [
    ['Los hechos, con su procedencia', 'vehicle_count, direct_collision, lane_change_vehicle… y cada uno dice de dónde sale: «según relato», «según ambos conductores». No hay un hecho sin origen.'],
    ['Las catorce reglas, también las que no casan', 'Once dicen «no comprobable con los datos aportados». Esa ausencia es información: enseña exactamente qué haría falta para ir más lejos.'],
    ['La decisión y la norma que la sostiene', 'ASCIDE · el Convenio es aplicable · resuelto, con el texto literal de la b.10. Nada de esa conclusión la ha redactado el modelo.'],
  ];
  const lw = ix - M - 0.42;
  items.forEach(([h, d], i) => {
    const y = iy + i * 1.52;
    card(s, { x: M, y, w: lw, h: 1.38, fill: C.ice });
    chip(s, i + 1, { x: M + 0.28, y: y + 0.26, d: 0.4, fill: C.navy, size: 12 });
    tb(s, h, { x: M + 0.84, y: y + 0.3, w: lw - 1.14, h: 0.3, fontSize: 14, bold: true, color: C.ink });
    tb(s, d, { x: M + 0.84, y: y + 0.66, w: lw - 1.14, h: 0.62, fontSize: 12, color: C.muted, lineSpacingMultiple: 1.06 });
  });

  notes(s, [
    'LA INTERFAZ (50 s). Es una captura real, tomada del sistema corriendo hoy.',
    'SALTABLE si la demo va bien: la demo 2 enseña esto mismo en vivo. Esta lámina es la red',
    'de seguridad para contarlo sin sistema delante.',
    '',
    '· Merece la pena detenerse en la columna de reglas que NO casan. Casi todas las demos',
    '  esconden eso. Aquí es deliberado: si el sistema no puede aplicar la tabla de culpabilidad',
    '  porque el relato no trae las casillas, se ve escrito, con el nombre de la regla.',
    '· La consecuencia práctica: un tramitador que discrepe de la conclusión puede señalar el paso',
    '  exacto donde discrepa — el hecho extraído, la regla aplicada o la redacción final.',
    '',
    'Si preguntan por qué se enseñan identificadores técnicos como lane_change_acknowledged_by_both:',
    'porque son los mismos nombres que aparecen en el artefacto de reglas firmado. Enseñar un',
    'sinónimo bonito rompería la trazabilidad entre lo que se ve y lo que se evalúa.',
  ].join('\n'));
}

/* ---------------------------------------------------------------- ingesta */

function ingesta(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Evidencia' });
  title(s, 'La ingesta no «sube un PDF»: publica una versión inmutable del conocimiento.');
  deck(s, 'Cinco pasos, y ninguno se puede saltar. Si el hash no coincide, la ingesta se rechaza antes de leer una sola página.');

  const steps = [
    ['VERIFICAR', 'Se comprueba el SHA-256 del documento. Sólo se acepta el manual verificado; cualquier otro se rechaza.'],
    ['EXTRAER', 'Página a página con el parser elegido. Las 111 páginas, incluidas las que están en blanco: la numeración no puede desplazarse.'],
    ['EVIDENCIAR', 'Una evidencia por página con hash del documento, página física, etiqueta impresa y —con Docling— regiones verificadas.'],
    ['PUBLICAR', 'Manifiesto, diagnósticos y versión de extracción. La publicación es atómica: o está entera o no está.'],
    ['INDEXAR', 'Qdrant, con una firma de índice de 13 campos. El alias sólo se mueve si la firma es compatible, y el rollback está probado.'],
  ];

  const cw = 2.30, gap = 0.12, y0 = 2.52, ch = 3.06;
  steps.forEach(([head, desc], i) => {
    const x = M + i * (cw + gap);
    card(s, { x, y: y0, w: cw, h: ch, fill: C.paper });
    chip(s, i + 1, { x: x + 0.24, y: y0 + 0.26, d: 0.4, fill: C.navy, size: 12 });
    tb(s, head, { x: x + 0.24, y: y0 + 0.82, w: cw - 0.48, h: 0.3, fontFace: F.head, fontSize: 14, bold: true, color: C.ink });
    tb(s, desc, { x: x + 0.24, y: y0 + 1.2, w: cw - 0.48, h: 1.7, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.06 });
    if (i < 4) tb(s, '›', { x: x + cw, y: y0 + 1.36, w: gap, h: 0.3, align: 'center', fontFace: F.head, fontSize: 15, bold: true, color: C.blue });
  });

  rrect(s, { x: M, y: 5.76, w: CW, h: 0.46, rectRadius: 0.1, fill: { color: C.band } });
  tb(s, 'sha256:b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344   ·   111 páginas   ·   publicación atómica', {
    x: M, y: 5.87, w: CW, h: 0.28, align: 'center', fontFace: F.mono, fontSize: 10, color: C.navy,
  });

  band(s, 'El identificador de una evidencia es sha256:<documento>:page:<n>. Apunta al manual original, no al fragmento del índice: la cita sobrevive a cambiar de parser o de chunking.', { tone: 'navy' });

  notes(s, [
    'INGESTA (60 s).',
    '',
    '· Paso 1: el sistema no ingiere cualquier PDF. Comprueba el hash contra el manual verificado.',
    '  En una prueba técnica parece exagerado; en un entorno real es la diferencia entre citar el',
    '  manual y citar «un» manual.',
    '· Paso 2: las páginas en blanco se conservan. Si se descartan, la página 57 del PDF deja de',
    '  ser la 57 y todas las citas anteriores se corrompen en silencio.',
    '· Paso 5: la firma de índice tiene 13 campos (parser, chunker, modelo de embeddings,',
    '  dimensión, métrica de distancia…). Mover el alias a un índice con firma incompatible falla',
    '  en vez de degradar los resultados sin avisar. Hay un comando de rollback y está probado.',
    '',
    'La banda de abajo es el detalle que más se agradece a los seis meses: los IDs de evidencia',
    'no dependen del parser, así que reindexar no invalida ni una cita del golden set.',
  ].join('\n'));
}

/* ------------------------------------------------------- evidencia abrible */

function evidenciaAbrible(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Evidencia' });
  title(s, 'Una cita no es una nota al pie: abre el manual por la página que la sostiene.');
  deck(s, 'Captura real: la respuesta sobre alcoholemia cita la página 9 y, al pulsarla, aparece el párrafo exacto del manual original sin salir de la conversación.');

  const iw = 6.2, ih = iw / 1.609, ix = M, iy = 2.44;
  rrect(s, { x: ix - 0.06, y: iy - 0.06, w: iw + 0.12, h: ih + 0.12, rectRadius: 0.08, fill: { color: C.navy } });
  s.addImage({ path: SHOT('ui-pdf'), x: ix, y: iy, w: iw, h: ih });

  const items = [
    ['El identificador es del documento, no del fragmento', 'sha256:…:page:9. Sobrevive a reindexar con otro parser o con otro tamaño de chunk: la cita del golden set sigue siendo válida.'],
    ['Página física y etiqueta impresa, separadas', 'La 9 de 111 del PDF. La numeración que el manual imprime se guarda aparte cuando se conoce, porque no siempre coinciden.'],
    ['Sin coordenadas verificadas no se finge un resaltado', 'Con el perfil activo se abre la página entera. El perfil estructurado sí tiene las regiones para resaltar la frase — otra razón para compararlos.'],
  ];
  const rx = ix + iw + 0.42, rw = RIGHT - rx;
  items.forEach(([h, d], i) => {
    const y = iy + i * 1.30;
    dot(s, { x: rx, y: y + 0.08, d: 0.13, color: C.blue });
    tb(s, h, { x: rx + 0.28, y: y, w: rw - 0.28, h: 0.46, fontSize: 13, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    tb(s, d, { x: rx + 0.28, y: y + 0.48, w: rw - 0.3, h: 0.7, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.06 });
  });

  band(s, 'Quien revisa no tiene que fiarse de la respuesta: tiene el manual delante en dos clics, y puede leer el párrafo entero, no el trozo que el sistema eligió enseñar.', { tone: 'navy' });

  notes(s, [
    'EVIDENCIA ABRIBLE (45 s). Segunda captura real.',
    'SALTABLE si la demo va bien: la demo 1 abre esta misma cita en vivo.',
    '',
    '· El detalle que suele pasar desapercibido y que más importa a los seis meses: el',
    '  identificador de evidencia apunta al documento y a la página física, no al fragmento del',
    '  índice. Reindexar con otro parser no invalida ni una cita.',
    '· Página física vs. etiqueta impresa: en este manual no siempre coinciden, y confundirlas',
    '  produce citas que parecen correctas y no lo son. Se guardan por separado.',
    '· Y la honestidad del visor: sin coordenadas verificadas se abre la página completa en vez',
    '  de pintar un resaltado inventado.',
  ].join('\n'));
}

/* ---------------------------------------------------------------- parsers */

function parsers(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Evidencia' });
  title(s, 'Dos métodos de ingesta conviven publicados; sólo la evaluación decide cuál se activa.');
  deck(s, 'Poder demostrar dos caminos de extracción sobre el mismo documento era un requisito propio: es la forma de que la elección deje de ser una opinión.');

  const cw = 5.866, y0 = 2.5, ch = 3.16;

  const cards = [
    [M, 'pypdf 6.16.2', 'BASELINE · ACTIVO EN DEMO', C.teal, C.tealSoft,
      'Texto plano por página y chunking de tamaño fijo con solapamiento.',
      ['118 fragmentos en el índice activo', 'Reproducible y barato de reindexar', 'Sin dependencias pesadas ni modelos de layout']],
    [M + cw + 0.36, 'Docling 2.124.0', 'ESTRUCTURADO · PUBLICADO, NO ACTIVO', C.blue, C.band,
      'Layout, Markdown y JSON originales, con chunking por secciones.',
      ['109 fragmentos, regiones verificadas en las 111 páginas', 'Diagnóstico por página: tablas sin verificar, OCR ausente', 'Coordenadas que permitirían resaltar la cita, no sólo abrir la página']],
  ];

  cards.forEach(([x, name, tag, color, tagbg, lead, bullets]) => {
    card(s, { x, y: y0, w: cw, h: ch });
    tb(s, name, { x: x + 0.34, y: y0 + 0.3, w: cw - 0.68, h: 0.36, fontFace: F.head, fontSize: 20, bold: true, color: C.ink });
    rrect(s, { x: x + 0.34, y: y0 + 0.76, w: 3.9, h: 0.3, rectRadius: 0.15, fill: { color: tagbg } });
    tb(s, tag, { x: x + 0.34, y: y0 + 0.81, w: 3.9, h: 0.22, align: 'center', fontSize: 9.5, bold: true, color });
    tb(s, lead, { x: x + 0.34, y: y0 + 1.2, w: cw - 0.68, h: 0.5, fontSize: 13, color: C.ink, lineSpacingMultiple: 1.04 });
    bullets.forEach((b, i) => {
      const y = y0 + 1.78 + i * 0.44;
      dot(s, { x: x + 0.36, y: y + 0.08, d: 0.11, color });
      tb(s, b, { x: x + 0.64, y, w: cw - 1.0, h: 0.4, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.02 });
    });
  });

  band(s, 'Decisión consciente: que una técnica esté disponible no demuestra que mejore el resultado. El índice estructurado espera a la comparación de evaluación; el comando compare-parsers existe justo para eso.', { tone: 'amber' });

  notes(s, [
    'DOS PARSERS (55 s). Ésta suele generar pregunta.',
    '',
    '· Docling es objetivamente más capaz: da layout, regiones y bounding boxes por página, que',
    '  es lo que haría falta para resaltar la frase exacta dentro del PDF en vez de abrir la',
    '  página entera.',
    '· Y aun así el índice activo en la demo es el de pypdf. El motivo está en la banda inferior:',
    '  no tengo todavía la comparación de evaluación que demuestre que mejora las respuestas.',
    '  Activarlo porque es más sofisticado sería exactamente el vicio que este proyecto intenta',
    '  evitar.',
    '',
    'Si preguntan cuándo se activaría: en cuanto la campaña de evaluación dé métricas de',
    'recuperación y de fidelidad de citas para los dos perfiles sobre los mismos 110 casos.',
    'Es el punto 2 del roadmap.',
  ].join('\n'));
}

/* -------------------------------------------------------------- retrieval */

function retrieval(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Recuperación' });
  title(s, 'Recuperación híbrida: la semántica encuentra el concepto, BM25 encuentra «b.10».');
  deck(s, 'Este manual mezcla lenguaje jurídico con referencias literales. Una búsqueda sólo vectorial falla justo donde el documento es más útil.');

  const nodes = [
    ['CONSULTA', 'El texto del usuario, sin reescribir', C.ice, C.ink, C.blue],
    ['DENSO', 'Embeddings: intención, sinónimos y contexto', C.band, C.navy, C.navy],
    ['BM25 ESPAÑOL', 'Términos literales: «art. 35», «b.10», «ASCIDE»', C.band, C.navy, C.navy],
    ['FUSIÓN RRF', 'Rango recíproco nativo de Qdrant, determinista', C.navy, C.paper, C.paper],
    ['EVIDENCIA', 'Fragmentos con página y hash, listos para citar', C.teal, C.paper, C.paper],
  ];

  const cw = 2.24, gap = 0.20, y0 = 2.66, ch = 1.72;
  nodes.forEach(([head, desc, bg, fg, accent], i) => {
    const x = M + i * (cw + gap);
    rrect(s, { x, y: y0, w: cw, h: ch, rectRadius: 0.1, fill: { color: bg }, line: { color: i < 3 ? C.line : bg, width: 1 } });
    tb(s, head, { x: x + 0.2, y: y0 + 0.28, w: cw - 0.4, h: 0.28, align: 'center', fontFace: F.head, fontSize: 12.5, bold: true, color: fg });
    tb(s, desc, { x: x + 0.2, y: y0 + 0.68, w: cw - 0.4, h: 0.86, align: 'center', fontSize: 11, color: i < 3 ? C.muted : C.pale, lineSpacingMultiple: 1.06 });
    if (i < 4) tb(s, i === 2 ? '›' : '›', { x: x + cw, y: y0 + 0.7, w: gap, h: 0.3, align: 'center', fontFace: F.head, fontSize: 16, bold: true, color: C.blue });
  });
  // Las dos señales son paralelas: se marca la bifurcación bajo los nodos 2 y 3.
  tb(s, 'dos señales sobre el mismo corpus, fusionadas sin reordenar a mano', {
    x: M + 2.44, y: y0 + ch + 0.14, w: 4.68, h: 0.26, align: 'center', fontSize: 10.5, italic: true, color: C.soft,
  });

  const gov = [
    ['Firma de índice de 13 campos', 'parser, chunker, modelo, dimensión, distancia, versión del documento…'],
    ['El alias sólo se mueve si la firma encaja', 'promover un índice incompatible falla en vez de degradar en silencio'],
    ['Rollback probado por comando', 'allianz index-rollback --collection … devuelve el alias al índice anterior'],
  ];
  const gw = 3.831;
  gov.forEach(([h, d], i) => {
    const x = M + i * (gw + 0.3);
    card(s, { x, y: 5.02, w: gw, h: 1.12, fill: C.ice });
    tb(s, h, { x: x + 0.26, y: 5.2, w: gw - 0.52, h: 0.44, fontSize: 12, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    tb(s, d, { x: x + 0.26, y: 5.62, w: gw - 0.52, h: 0.44, fontSize: 10.5, color: C.muted, lineSpacingMultiple: 1.02 });
  });

  band(s, 'Gobierno del índice: un índice no se activa porque exista, se activa porque su firma es compatible y su evaluación lo respalda.', { tone: 'navy' });

  notes(s, [
    'RECUPERACIÓN (55 s).',
    '',
    '· El ejemplo concreto que convence: si alguien pregunta «¿qué dice la b.10?», un índice',
    '  puramente vectorial devuelve normas parecidas; BM25 devuelve la b.10. Y al revés: si',
    '  preguntan «¿quién responde cuando uno sale de un garaje?», el léxico no encuentra nada',
    '  y los embeddings sí.',
    '· La fusión es RRF nativo de Qdrant: determinista y en el motor, no un reordenamiento',
    '  hecho a mano en Python que nadie podría reproducir.',
    '· La fila de abajo es gobierno del índice y es lo que hace que esto sea operable: la firma',
    '  de 13 campos evita el fallo clásico de reindexar con otro modelo de embeddings y que las',
    '  respuestas empeoren sin que nadie sepa por qué.',
  ].join('\n'));
}

/* -------------------------------------------------------- grafo documental */

function grafoDocumental(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Workflows', dark: true });
  title(s, 'El grafo documental es corto, tipado, y no entrega nada sin validarlo antes.', { dark: true, size: 29 });
  deck(s, 'Tres nodos. La respuesta pasa por una comprobación contra el contexto recuperado antes de salir, y el estado que resulta viaja hasta la interfaz.', { dark: true, y: 2.02 });

  const nodes = [
    ['retrieve', 'Top-k híbrido y deduplicado, con un límite duro de 8 fragmentos. El modelo no ve el manual entero.'],
    ['generate', 'El modelo sólo recibe el contexto recuperado. Cada bloque de respuesta nace con su cita asociada.'],
    ['validate', 'Cada cita se contrasta contra la evidencia recuperada y el resultado fija el estado de la respuesta.'],
  ];
  const cw = 3.4, y0 = 2.6, ch = 1.86;
  nodes.forEach(([name, desc], i) => {
    const x = M + i * (cw + 0.55);
    card(s, { x, y: y0, w: cw, h: ch, dark: true, fill: i === 2 ? C.teal : C.darkCard });
    tb(s, `0${i + 1}`, { x: x + 0.3, y: y0 + 0.26, w: 0.6, h: 0.24, fontFace: F.head, fontSize: 10.5, bold: true, color: i === 2 ? C.tealSoft : C.sky });
    tb(s, name, { x: x + 0.3, y: y0 + 0.54, w: cw - 0.6, h: 0.36, fontFace: F.mono, fontSize: 19, bold: true, color: C.paper });
    tb(s, desc, { x: x + 0.3, y: y0 + 1.0, w: cw - 0.6, h: 0.76, fontSize: 11.5, color: i === 2 ? 'DFF2F1' : C.pale, lineSpacingMultiple: 1.06 });
    if (i < 2) tb(s, '›', { x: x + cw, y: y0 + 0.72, w: 0.55, h: 0.36, align: 'center', fontFace: F.head, fontSize: 22, bold: true, color: C.sky });
  });

  tb(s, 'ESTADOS QUE LA INTERFAZ MUESTRA, SIN MAQUILLAR', {
    x: M, y: 4.78, w: 8, h: 0.24, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.2, color: C.sky,
  });
  const states = [
    ['answered', 'la evidencia sostiene la respuesta completa', C.teal],
    ['partial', 'sostiene una parte; se dice cuál falta', C.sky],
    ['insufficient_evidence', 'el manual no lo cubre con lo recuperado', C.amber],
    ['out_of_scope', 'la pregunta no es del manual', C.rust],
  ];
  const sw = 2.828;
  states.forEach(([code, desc, color], i) => {
    const x = M + i * (sw + 0.26);
    rrect(s, { x, y: 5.14, w: sw, h: 0.92, rectRadius: 0.09, fill: { color: C.deep } });
    tb(s, code, { x: x + 0.2, y: 5.28, w: sw - 0.4, h: 0.26, fontFace: F.mono, fontSize: 11, bold: true, color });
    tb(s, desc, { x: x + 0.2, y: 5.56, w: sw - 0.4, h: 0.44, fontSize: 10.5, color: C.pale, lineSpacingMultiple: 1.02 });
  });

  band(s, 'Estado interno tipado, tiempo máximo acotado y traza en Langfuse bajo el session_id del hilo: la misma ejecución se puede auditar después.', { tone: 'dark', y: 6.34 });

  notes(s, [
    'GRAFO DOCUMENTAL (45 s).',
    '',
    '· Tres nodos y ya está. La complejidad de un RAG no está en el grafo, está en lo que rodea',
    '  al grafo: la evidencia por debajo y la validación por arriba.',
    '· El límite de 8 fragmentos es deliberado: más contexto no mejora la respuesta y sí empeora',
    '  la trazabilidad, porque diluye qué fragmento sostiene qué afirmación.',
    '· Los cuatro estados de abajo son la parte que la mayoría de demos esconde. insufficient_',
    '  evidence y out_of_scope son respuestas correctas, y la interfaz las enseña tal cual.',
  ].join('\n'));
}

/* -------------------------------------------------------- grafo siniestros */

function grafoSiniestros(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Workflows' });
  title(s, 'El grafo de siniestros se interrumpe y pregunta antes que inventar.');
  deck(s, 'Cinco nodos y una salida lateral: cuando falta un hecho que cambia la decisión, el grafo se detiene, pide ese dato concreto y reanuda el mismo hilo.');

  const nodes = [
    ['extract_facts', 'Hechos con nombre, atribución y texto literal del relato'],
    ['retrieve_criteria', 'Evidencia del manual para el contexto del caso'],
    ['apply_rules', 'Puerta de aplicabilidad, ruleset firmado y tabla de culpabilidad'],
    ['explain', 'Redacta la decisión que las reglas ya han tomado'],
    ['validate', 'Comprueba citas y coherencia antes de entregar'],
  ];
  const cw = 2.24, gap = 0.20, y0 = 2.5, ch = 1.5;
  nodes.forEach(([name, desc], i) => {
    const x = M + i * (cw + gap);
    const hot = i === 2;
    rrect(s, { x, y: y0, w: cw, h: ch, rectRadius: 0.1, fill: { color: hot ? C.navy : C.paper }, line: { color: hot ? C.navy : C.line, width: 1 } });
    tb(s, name, { x: x + 0.14, y: y0 + 0.26, w: cw - 0.28, h: 0.28, align: 'center', fontFace: F.mono, fontSize: 11, bold: true, color: hot ? C.paper : C.navy });
    tb(s, desc, { x: x + 0.16, y: y0 + 0.62, w: cw - 0.32, h: 0.72, align: 'center', fontSize: 10.5, color: hot ? C.pale : C.muted, lineSpacingMultiple: 1.04 });
    if (i < 4) tb(s, '›', { x: x + cw, y: y0 + 0.58, w: gap, h: 0.3, align: 'center', fontFace: F.head, fontSize: 16, bold: true, color: C.blue });
  });

  // Salida lateral: la interrupción.
  const xi = M + 2 * (cw + gap);
  s.addShape('line', { x: xi + cw / 2, y: y0 + ch, w: 0, h: 0.40, line: { color: C.amber, width: 1.5, dashType: 'dash' } });
  rrect(s, { x: M + 1.9, y: 4.40, w: 6.2, h: 1.56, rectRadius: 0.1, fill: { color: C.amberSoft } });
  tb(s, 'needs_information   ·   interrupt()', {
    x: M + 2.14, y: 4.62, w: 5.7, h: 0.28, fontFace: F.mono, fontSize: 12, bold: true, color: C.amber,
  });
  tb(s, 'El grafo guarda su estado en un checkpoint y devuelve la pregunta exacta que falta. La respuesta del usuario lo reanuda con Command(resume=…) en el mismo punto: no se reejecuta la conversación ni se vuelve a llamar al modelo desde cero.', {
    x: M + 2.14, y: 4.98, w: 5.72, h: 0.86, fontSize: 11.5, color: C.amber, lineSpacingMultiple: 1.06,
  });

  card(s, { x: 8.42, y: 4.40, w: CW - 7.8 - 0.06, h: 1.56, fill: C.ice });
  tb(s, 'EJEMPLO REAL DE LA DEMO', { x: 8.64, y: 4.62, w: 3.6, h: 0.22, fontFace: F.head, fontSize: 9, bold: true, charSpacing: 1.1, color: C.soft });
  tb(s, '«A2 + B4 ⇒ culpable B, salvo que el conductor de A abra la puerta.» Sin ese hecho, el sistema no elige: pide exactamente ese dato, con el texto literal de la observación del manual.', {
    x: 8.64, y: 4.94, w: 3.66, h: 0.92, fontSize: 11, color: C.ink, lineSpacingMultiple: 1.06,
  });

  band(s, 'Preguntar por el dato que falta es una decisión del sistema, no un fallo: es la diferencia entre un asistente que colabora y uno que rellena huecos.', { tone: 'navy' });

  notes(s, [
    'GRAFO DE SINIESTROS (75 s). Es la lámina técnica que más diferencia esta prueba.',
    '',
    '· apply_rules (el nodo oscuro) es donde ocurre todo lo determinista: puerta de aplicabilidad,',
    '  reglas subsidiarias y tabla de culpabilidad. El LLM ya ha terminado su trabajo antes.',
    '· La salida lateral es human-in-the-loop de verdad, con interrupt() de LangGraph y un',
    '  checkpoint. No es «te devuelvo un error y vuelve a escribirlo todo»: el hilo se reanuda',
    '  en el mismo punto con Command(resume=…).',
    '· El ejemplo de la derecha es literal del manual (pág. 101): una de las cuatro observaciones',
    '  impresas bajo la tabla de culpabilidad. Se ve en la demo 3.',
    '',
    'Si preguntan por el coste de la interrupción: el estado vive en el checkpointer del grafo,',
    'asociado al hilo. En esta prueba es memoria del proceso; en producción sería una base',
    'persistente, y es un cambio de adaptador, no de diseño.',
  ].join('\n'));
}

/* ----------------------------------------------------- relato → decisión */

function relatoADecision(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Motor de reglas' });
  title(s, 'Del lenguaje natural a una decisión auditable, sin ningún salto mágico.');
  deck(s, 'El modelo rellena un vocabulario cerrado de hechos. El motor evalúa predicados sobre esos hechos. Nadie más participa en la decisión.');

  const steps = [
    ['RELATO', '«Cambiaba de carril y rocé al otro…»', C.ice, C.ink],
    ['HECHOS TIPADOS', 'lane_change_acknowledged_by_both\n    = true\ncontradictory_versions = true\nlane_change_vehicle = A', C.band, C.navy],
    ['RULESET FIRMADO', 'applies_when: all / any\neq · ne · is_true · is_false\nevidencia + firma del revisor', C.navy, C.paper],
    ['EVALUACIÓN', 'matched\nnot_matched\ninsufficient_data', C.band, C.navy],
    ['DECISIÓN', 'resuelta\ncondicionada\nindeterminada', C.teal, C.paper],
  ];

  const widths = [1.80, 2.95, 2.60, 2.10, 1.95];
  const gap = 0.15;
  let x = M;
  const y0 = 2.6, ch = 2.0;
  steps.forEach(([head, body, bg, fg], i) => {
    const w = widths[i];
    rrect(s, { x, y: y0, w, h: ch, rectRadius: 0.1, fill: { color: bg }, line: { color: bg === C.ice || bg === C.band ? C.line : bg, width: 1 } });
    tb(s, head, { x: x + 0.16, y: y0 + 0.24, w: w - 0.32, h: 0.26, align: 'center', fontFace: F.head, fontSize: 11.5, bold: true, color: fg });
    tb(s, body, {
      x: x + 0.18, y: y0 + 0.66, w: w - 0.36, h: 1.2,
      align: i === 0 ? 'center' : 'left',
      fontFace: i === 0 ? F.body : F.mono, fontSize: i === 0 ? 12 : 9,
      italic: i === 0, color: fg, lineSpacingMultiple: 1.16,
    });
    if (i < 4) tb(s, '›', { x: x + w, y: y0 + 0.84, w: gap, h: 0.3, align: 'center', fontFace: F.head, fontSize: 15, bold: true, color: C.blue });
    x += w + gap;
  });

  const guards = [
    ['El extractor sólo conoce los hechos que el ruleset consulta', 'Los nombres estables se derivan del artefacto firmado: una regla no puede depender de un hecho que nadie pidió extraer.'],
    ['Un hecho ausente produce insufficient_data', 'Nunca un culpable por defecto. La interfaz enseña también las reglas que no casan, y por qué.'],
    ['Una invariante del dominio bloquea la incoherencia', 'Un convenio no aplicable no puede llevar decisión, y una decisión resuelta no puede existir sin las reglas que la sostienen.'],
  ];
  const gw = 3.831;
  guards.forEach(([h, d], i) => {
    const gx = M + i * (gw + 0.3);
    card(s, { x: gx, y: 4.88, w: gw, h: 1.28, fill: C.ice });
    tb(s, h, { x: gx + 0.26, y: 5.06, w: gw - 0.52, h: 0.44, fontSize: 11.5, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    tb(s, d, { x: gx + 0.26, y: 5.5, w: gw - 0.52, h: 0.58, fontSize: 10.5, color: C.muted, lineSpacingMultiple: 1.04 });
  });

  band(s, 'El generador redacta la decisión; no la toma. No hay ningún camino en el código por el que una generación convierta un resultado indeterminado en definitivo.', { tone: 'navy' });

  notes(s, [
    'DEL RELATO A LA DECISIÓN (60 s).',
    '',
    '· Recorrer la cadena de izquierda a derecha una vez, despacio. Es el corazón del sistema.',
    '· La caja azul oscuro del centro es un fichero JSON firmado, no código: cada regla lleva su',
    '  identificador, su evidencia en el manual, su descripción, su consecuencia y el identificador',
    '  de quien la revisó.',
    '· La primera garantía de abajo es sutil pero importante: la lista de nombres de hecho que el',
    '  prompt de extracción pide se deriva del ruleset. Si mañana se añade una regla que consulta',
    '  un hecho nuevo, el extractor empieza a pedirlo. No hay dos listas que se desincronicen.',
    '· La tercera garantía es una excepción de dominio de verdad: si el código intentara publicar',
    '  una decisión resuelta sin reglas que la sostengan, lanza. Me saltó a mí durante el',
    '  desarrollo y por eso está.',
  ].join('\n'));
}

/* ----------------------------------------------------------------- matriz */

function matriz(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Motor de reglas' });
  title(s, 'La tabla de culpabilidad se transcribió dos veces a mano — por eso se puede confiar en ella.');
  deck(s, '324 celdas leídas de un PDF de 2004 en las que cada error es un error de atribución de responsabilidad. Ninguna se autotranscribió.');

  // Retícula 18×18 estilizada.
  const gx = M + 0.92, gy = 2.92, cell = 0.13, gap = 0.016, step = cell + gap;
  tb(s, 'VEHÍCULO B  ·  B0 – B17', {
    x: gx, y: gy - 0.32, w: 18 * step, h: 0.22, align: 'center', fontFace: F.head, fontSize: 8.5, bold: true, charSpacing: 0.8, color: C.soft,
  });
  tb(s, 'VEHÍCULO A\nA0 – A17', {
    x: M, y: gy + 0.98, w: 0.84, h: 0.5, align: 'center', fontFace: F.head, fontSize: 8, bold: true, charSpacing: 0.4, color: C.soft, lineSpacingMultiple: 1.05,
  });
  for (let r = 0; r < 18; r++) {
    for (let c = 0; c < 18; c++) {
      // Patrón estable y reproducible: sólo ilustra densidad, no reproduce el manual.
      const v = (r * 7 + c * 13 + ((r * c) % 5)) % 10;
      let color = C.band;
      if (v < 3) color = C.navy;
      else if (v < 6) color = C.sky;
      const isNote = (r === 2 && c === 4);
      rect(s, {
        x: gx + c * step, y: gy + r * step, w: cell, h: cell,
        fill: { color: isNote ? C.amber : color },
      });
    }
  }
  // Señalización de la celda con observación.
  rrect(s, {
    x: gx + 4 * step - 0.03, y: gy + 2 * step - 0.03, w: cell + 0.06, h: cell + 0.06,
    rectRadius: 0.02, fill: { type: 'none' }, line: { color: C.amber, width: 1.75 },
  });
  tb(s, 'A2 + B4 — celda con observación impresa', {
    x: gx - 0.5, y: gy + 18 * step + 0.14, w: 18 * step + 1.0, h: 0.24, align: 'center', fontSize: 10, italic: true, color: C.amber,
  });
  tb(s, 'Retícula ilustrativa; la transcripción real está firmada\nen el artefacto y se puede abrir.', {
    x: gx - 0.5, y: gy + 18 * step + 0.42, w: 18 * step + 1.0, h: 0.42, align: 'center', fontSize: 9, color: C.soft, lineSpacingMultiple: 1.05,
  });

  const xr = M + 3.78;
  const facts = [
    ['324 celdas · 18 casillas A × 18 casillas B',
      'La tabla que el manual imprime en la página 101 para repartir responsabilidad a partir del apartado 12 de la declaración amistosa.'],
    ['Doble transcripción independiente y adjudicación firmada',
      'Dos pasadas separadas, comparadas por comando (allianz rules compare-transcriptions) y atestadas. Una celda no conciliada no decide.'],
    ['Las cuatro observaciones viven en el artefacto, no en el código',
      'Se declaran con campos propios —a qué celdas aplican, qué hecho las activa, sobre qué conductor y qué consecuencia tienen—. Una celda con asterisco sin observación anotada simplemente no decide.'],
    ['Cuatro resultados que la interfaz no puede confundir',
      'Atribuye · no atribuye («-») · falta el hecho de la excepción · la excepción se cumple y retira la atribución.'],
  ];
  let y = 2.54;
  facts.forEach(([h, d]) => {
    dot(s, { x: xr, y: y + 0.08, d: 0.13, color: C.blue });
    tb(s, h, { x: xr + 0.28, y, w: RIGHT - xr - 0.28, h: 0.28, fontSize: 12.5, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    tb(s, d, { x: xr + 0.28, y: y + 0.3, w: RIGHT - xr - 0.3, h: 0.66, fontSize: 11, color: C.muted, lineSpacingMultiple: 1.04 });
    y += 0.94;
  });

  band(s, 'Nunca se traduce una maniobra narrada a un código de casilla. Si el relato no declara «marcamos A2 y B4», la tabla no entra: inferirlo sería inventar el dato más determinante del expediente.', { tone: 'navy' });

  notes(s, [
    'LA TABLA 18×18 (70 s). Es la parte de la que más orgulloso estoy y la que más incomoda',
    'contar, porque el trabajo fue manual a propósito.',
    '',
    '· 324 celdas. Un OCR o un extractor de tablas habría dado un resultado plausible y nadie',
    '  habría podido saber si era correcto. Aquí un error de transcripción cambia quién paga.',
    '· Por eso: dos transcripciones independientes, un comando que las compara, y una firma.',
    '· Las cuatro observaciones impresas bajo la tabla («A2+B4 = culpable B, salvo que el A abra',
    '  la puerta») están declaradas de forma estructurada en el artefacto. No hay un if en el',
    '  código que sepa de puertas.',
    '· La banda de abajo es el límite que más se defiende solo: si el parte no trae las casillas',
    '  marcadas, no las deducimos de la narración. Ese dato lo firman los conductores.',
    '',
    'Aviso honesto si preguntan: la retícula de colores de la izquierda es ilustrativa, para que',
    'se vea la densidad. La transcripción real está en el artefacto firmado y se puede abrir.',
  ].join('\n'));
}

/* ---------------------------------------------------------- estado reglas */

function estadoReglas(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '03 · Motor de reglas' });
  title(s, '13 de las 14 reglas firmadas ya deciden; la que falta se declara, no se disimula.');
  deck(s, 'Estado real del ruleset a día de hoy, comprobado sobre el artefacto: qué regla tiene condición verificable y cuál sigue siendo sólo documentación.');

  const groups = [
    ['PUERTA DE APLICABILIDAD Y EXCEPCIONES', 2.96, [
      ['cide-requires-two-vehicles', 'ok', 'Dos vehículos intervinientes · p. 56'],
      ['cide-requires-direct-collision', 'ok', 'Colisión directa entre ellos · p. 56'],
      ['third-vehicle-identified-…', 'ok', 'Un tercero identificado lo excluye'],
      ['chain-collision-excludes-…', 'ok', 'Colisión en cadena excluida · p. 57'],
      ['alcohol-does-not-exclude-…', 'ok', 'El alcohol no excluye · p. 9'],
      ['convention-scope', 'na', 'Ámbito: no es regla de decisión'],
    ]],
    ['NORMAS SUBSIDIARIAS Y TABLA DE CULPABILIDAD', 3.72, [
      ['ascide-b5-parked-vehicle', 'ok', 'Contra vehículo aparcado'],
      ['ascide-b6-exit-from-parking', 'ok', 'Salida de estacionamiento o garaje'],
      ['ascide-b9-reverse-vs-rear-impact', 'ok', 'Marcha atrás vs. alcance trasero'],
      ['ascide-b10-lane-change', 'ok', 'Cambio de carril · p. 75'],
      ['ascide-traffic-light-amber', 'ok', 'Paso en ámbar admitido'],
      ['cide-door-opening', 'ok', 'Apertura de puertas sin precisar'],
      ['cide-matrix-lookup', 'ok', '324 celdas de la tabla · p. 101'],
      ['ascide-b11-roundabout', 'no', 'Rotondas · pendiente'],
    ]],
  ];

  const cw = 5.866, y0 = 2.5;
  groups.forEach(([head, ch, rules], gi) => {
    const x = M + gi * (cw + 0.36);
    card(s, { x, y: y0, w: cw, h: ch, fill: C.paper });
    tb(s, head, { x: x + 0.3, y: y0 + 0.24, w: cw - 0.6, h: 0.24, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft });
    rules.forEach(([id, state, desc], i) => {
      const y = y0 + 0.62 + i * 0.38;
      const color = state === 'ok' ? C.teal : state === 'no' ? C.rust : C.soft;
      dot(s, { x: x + 0.3, y: y + 0.08, d: 0.12, color });
      tb(s, id, { x: x + 0.54, y: y, w: 2.6, h: 0.24, fontFace: F.mono, fontSize: 9.5, color: state === 'no' ? C.rust : C.ink });
      tb(s, desc, { x: x + 3.22, y: y + 0.01, w: cw - 3.5, h: 0.24, fontSize: 9.5, color: C.muted });
    });
  });

  // Leyenda horizontal bajo la columna izquierda.
  const legend = [['Decide hoy', C.teal], ['Sin condición verificable', C.rust], ['No es regla de decisión', C.soft]];
  let lx = M + 0.04;
  legend.forEach(([t, color]) => {
    dot(s, { x: lx, y: 5.66, d: 0.12, color });
    tb(s, t, { x: lx + 0.22, y: 5.6, w: 2.1, h: 0.24, fontSize: 10.5, color: C.muted });
    lx += t.length > 14 ? 2.0 : 1.3;
  });

  band(s, 'Falta b.11 (rotondas): su excepción no retira la atribución, la sustituye por otra — exige una segunda regla mutuamente excluyente, no rellenar un predicado. Mientras tanto devuelve insufficient_data de forma explícita, nunca como si hubiera casado.', { tone: 'navy' });

  notes(s, [
    'ESTADO DE LAS REGLAS (50 s). Lámina de honestidad dentro del bloque técnico.',
    '',
    '· La puerta de aplicabilidad está completa desde el día 4: es lo que permite decir «fuera',
    '  del Convenio» con fundamento en los casos 2 y 3 del enunciado.',
    '· De las normas subsidiarias, seis están conectadas más la tabla de culpabilidad.',
    '· Falta una: b.11, rotondas. Y la explico porque el motivo es interesante: su excepción no',
    '  retira la atribución, la sustituye («culpable quien accede, salvo que ambos tengan daños',
    '  laterales no angulares, en cuyo caso responde el del lateral derecho»). Eso no es rellenar',
    '  un predicado: es una segunda regla con su propia condición mutuamente excluyente.',
    '· Mientras no esté, devuelve insufficient_data. No finge.',
  ].join('\n'));
}
