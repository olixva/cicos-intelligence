import {
  W, H, M, CW, RIGHT, C, F, tb, rect, rrect, ell, card, pill, chip, dot, arrow,
  title, deck, band, notes, page, divider, hline,
} from './lib.mjs';

/* ═══════════════════════════════════ 01 · El problema ═══════════════════════ */

export function chapterOne(pres, ctx) {
  divider(pres, ctx, {
    num: '01',
    name: 'El problema',
    promise: 'El enunciado parece pedir un buscador sobre un PDF.\nLos cinco accidentes que adjunta piden otra cosa.',
  });
  elEncargo(pres, ctx);
  losVeredictos(pres, ctx);
  laTesis(pres, ctx);
}

function elEncargo(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '01 · El problema' });
  title(s, 'El enunciado pide un RAG sobre el manual; los cinco accidentes que adjunta piden criterio.');
  deck(s, 'Los dos encargos son reales, pero sólo el primero se resuelve con recuperación. El segundo exige aplicar un Convenio con reglas propias.');

  const cw = 5.866, y0 = 2.5, ch = 3.66;

  // Izquierda — lo que pide el enunciado
  card(s, { x: M, y: y0, w: cw, h: ch });
  tb(s, 'LO QUE PIDE EL ENUNCIADO', {
    x: M + 0.34, y: y0 + 0.3, w: cw - 0.68, h: 0.26,
    fontFace: F.head, fontSize: 11, bold: true, charSpacing: 1.2, color: C.blue,
  });
  const asks = [
    ['Un sistema RAG con un LLM', 'sobre el manual de las comisiones CIDE, ASCIDE y CICOS.'],
    ['Responder preguntas del manual', 'y analizar relatos de accidentes: partes implicadas, responsabilidad y circunstancias de la colisión.'],
    ['Una evaluación de la calidad', 'de las respuestas, no una demostración anecdótica.'],
    ['Plan, arquitectura y código', 'con hitos, supuestos, riesgos y el porqué de cada decisión técnica.'],
  ];
  let y = y0 + 0.72;
  asks.forEach(([h, d]) => {
    dot(s, { x: M + 0.36, y: y + 0.09, d: 0.12, color: C.blue });
    tb(s, h, { x: M + 0.66, y, w: cw - 1.0, h: 0.26, fontSize: 13, bold: true, color: C.ink });
    tb(s, d, { x: M + 0.66, y: y + 0.26, w: cw - 1.02, h: 0.42, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.02 });
    y += 0.76;
  });

  // Derecha — los cinco accidentes
  const x2 = M + cw + 0.36;
  card(s, { x: x2, y: y0, w: cw, h: ch, fill: C.ice });
  tb(s, 'LOS CINCO ACCIDENTES DE MUESTRA', {
    x: x2 + 0.34, y: y0 + 0.3, w: cw - 0.68, h: 0.26,
    fontFace: F.head, fontSize: 11, bold: true, charSpacing: 1.2, color: C.navy,
  });
  const cases = [
    'Alcance en semáforo; ambos conductores dicen ir atentos.',
    'Colisión múltiple con lluvia, cinco vehículos y heridos.',
    'Vehículo aparcado, daños y fuga sin identificar al causante.',
    'Cambio de carril con roce lateral y versiones opuestas.',
    'Conductor bajo los efectos del alcohol y lesiones graves.',
  ];
  y = y0 + 0.76;
  cases.forEach((t, i) => {
    chip(s, i + 1, { x: x2 + 0.34, y: y - 0.02, d: 0.34, fill: C.navy, size: 11 });
    tb(s, t, { x: x2 + 0.84, y: y + 0.02, w: cw - 1.2, h: 0.52, fontSize: 12.5, color: C.ink, lineSpacingMultiple: 1.04 });
    y += 0.6;
  });

  band(s, 'Ninguno de los cinco se responde con una búsqueda semántica. Los cinco exigen decidir si el Convenio aplica, y sólo entonces quién responde.', { tone: 'navy' });

  notes(s, [
    'EL ENCARGO (60 s).',
    '',
    'Puntos a decir:',
    '· El enunciado tiene dos mitades y sólo la primera es un problema de RAG clásico.',
    '· La segunda mitad —«identificar partes, responsabilidad y circunstancias»— es un problema',
    '  de aplicación de un convenio con condiciones cerradas. Si eso se resuelve generando texto,',
    '  el sistema queda convincente y no demostrable.',
    '· Los cinco accidentes de la derecha son los que vienen en el enunciado, literalmente.',
    '  Los usé como criterio de aceptación desde el primer día y están en el golden set',
    '  (case_id accident-01 … accident-05).',
    '',
    'Enlace a la siguiente lámina: «Los resolví a mano contra el manual antes de escribir código.',
    'Este fue el resultado.»',
  ].join('\n'));
}

function losVeredictos(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '01 · El problema' });
  title(s, 'En cuatro de los cinco casos, la respuesta correcta del manual es no concluir.');
  deck(s, 'Resueltos a mano contra el manual y verificados después contra el sistema en ejecución.');

  const rows = [
    ['1', 'Alcance en semáforo', 'Aplicable · culpa indeterminada', C.amber, C.amberSoft,
      'Faltan las casillas del apartado 12 de la D.A.A. que activan la tabla de culpabilidad · pág. 101'],
    ['2', 'Colisión múltiple (5 vehículos)', 'Fuera del Convenio', C.rust, C.rustSoft,
      'El Convenio exige dos vehículos en colisión directa · pág. 56 — y excluye la colisión en cadena · págs. 57-58'],
    ['3', 'Aparcado con daños y fuga', 'Indeterminado', C.amber, C.amberSoft,
      'El segundo vehículo no está identificado: no hay dos partes entre las que repartir · pág. 56'],
    ['4', 'Cambio de carril', 'Resuelto · ASCIDE b.10 · culpable A', C.teal, C.tealSoft,
      'Norma subsidiaria: si ambos reconocen el cambio de carril, responde quien lo efectúa · pág. 75'],
    ['5', 'Alcohol y lesiones graves', 'Aplicable · culpa indeterminada', C.amber, C.amberSoft,
      'El alcohol no excluye el Convenio · pág. 9 — pero lesiones y vía penal quedan fuera de su alcance · págs. 27 y 62'],
  ];

  const y0 = 2.68, rh = 0.73;
  const xCase = M + 0.5, wCase = 2.85;
  const xVer = M + 3.5, wVer = 3.0;
  const xWhy = M + 6.68, wWhy = CW - 6.68 - 0.1;

  tb(s, 'CASO DEL ENUNCIADO', { x: xCase, y: y0 - 0.32, w: wCase, h: 0.24, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft });
  tb(s, 'VEREDICTO DEL SISTEMA', { x: xVer, y: y0 - 0.32, w: wVer, h: 0.24, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft });
  tb(s, 'FUNDAMENTO EN EL MANUAL', { x: xWhy, y: y0 - 0.32, w: wWhy, h: 0.24, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft });

  rows.forEach(([n, name, verdict, fg, bg, why], i) => {
    const y = y0 + i * rh;
    if (i % 2 === 0) rrect(s, { x: M, y, w: CW, h: rh - 0.06, fill: { color: C.ice } });
    chip(s, n, { x: M + 0.1, y: y + 0.17, d: 0.32, fill: C.navy, size: 10.5 });
    tb(s, name, { x: xCase, y: y + 0.2, w: wCase, h: 0.3, fontSize: 13, bold: true, color: C.ink });
    rrect(s, { x: xVer, y: y + 0.16, w: wVer, h: 0.34, rectRadius: 0.17, fill: { color: bg } });
    tb(s, verdict, { x: xVer, y: y + 0.22, w: wVer, h: 0.24, align: 'center', fontSize: 11, bold: true, color: fg });
    tb(s, why, { x: xWhy, y: y + 0.11, w: wWhy, h: 0.5, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.0 });
  });

  band(s, 'Un asistente que resolviera los cinco estaría inventando cuatro. Esto no es una limitación del sistema: es lo que el manual sostiene, y el sistema llega ahí solo y con la cita delante.', { tone: 'navy' });

  notes(s, [
    'LOS CINCO VEREDICTOS (90 s). Ésta es la lámina más importante del primer bloque.',
    '',
    'Cómo contarla:',
    '· «Antes de escribir una línea de código resolví los cinco casos a mano contra el manual.»',
    '· Recorrer la columna de veredictos de arriba abajo y detenerse en el 4: es el único que se',
    '  resuelve de forma determinista con lo que el propio relato aporta.',
    '· El 2 es el más contraintuitivo: cinco vehículos parece el caso más grave y es el que se cae',
    '  del Convenio por la puerta de entrada (dos vehículos, colisión directa).',
    '· El 5 es el que más se presta a error: mucha gente asume que la alcoholemia excluye el',
    '  Convenio. El manual dice lo contrario en la página 9. Lo que queda fuera son las lesiones',
    '  y lo penal.',
    '',
    'Si preguntan «¿entonces vuestro sistema no resuelve casi nada?»:',
    '«Resuelve exactamente lo que el manual permite resolver con los datos del relato. En cuanto',
    'el parte aporta las casillas del apartado 12, la tabla de culpabilidad de 324 celdas entra y',
    'resuelve. Lo veréis en la demo.»',
  ].join('\n'));
}

function laTesis(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '01 · El problema', dark: true });
  title(s, 'Todo el sistema descansa sobre una sola regla:\nnada se afirma sin poder demostrarlo.', { dark: true, size: 30 });
  deck(s, 'De ahí salen las tres garantías que atraviesan la arquitectura entera, y también las que la hacen más incómoda de construir.', { dark: true, y: 2.06 });

  const items = [
    ['EVIDENCIA', 'Cada afirmación arrastra su cita: documento, hash, página física del PDF y versión de extracción. Al pulsarla se abre el manual original por esa página.'],
    ['DECISIÓN', 'El LLM interpreta el relato y rellena un vocabulario cerrado de hechos. Quien decide es un motor determinista sobre reglas firmadas. Nunca al revés.'],
    ['ABSTENCIÓN', 'Si falta un hecho, el sistema dice cuál falta y por qué importa. La incertidumbre no se convierte en una responsabilidad atribuida.'],
  ];
  const cw = 3.831, y0 = 2.92, ch = 2.9;
  items.forEach(([h, d], i) => {
    const x = M + i * (cw + 0.3);
    card(s, { x, y: y0, w: cw, h: ch, dark: true });
    chip(s, i + 1, { x: x + 0.36, y: y0 + 0.36, d: 0.44, fill: C.sky, color: C.navy, size: 13 });
    tb(s, h, { x: x + 0.36, y: y0 + 1.02, w: cw - 0.72, h: 0.34, fontFace: F.head, fontSize: 18, bold: true, color: C.paper });
    tb(s, d, { x: x + 0.36, y: y0 + 1.48, w: cw - 0.72, h: 1.2, fontSize: 12.5, color: C.pale, lineSpacingMultiple: 1.08 });
  });

  band(s, 'Es lo único que separa un asistente demostrable de uno meramente convincente. Cuesta más construirlo; es la diferencia entre un piloto y un producto.', { tone: 'dark', y: 6.24 });

  notes(s, [
    'LA TESIS (50 s). Lámina de transición: aquí se fija el criterio con el que hay que juzgar',
    'todo lo que viene después.',
    '',
    '· EVIDENCIA: el identificador de evidencia apunta al documento y la página física del PDF,',
    '  no al fragmento del índice. Así una cita sigue siendo válida aunque se cambie el parser',
    '  o el tamaño de chunk.',
    '· DECISIÓN: es la inversión de control importante. El modelo no redacta la conclusión;',
    '  rellena hechos con nombre y el motor de reglas decide.',
    '· ABSTENCIÓN: el sistema tiene un estado explícito para «me falta este dato», y el grafo',
    '  se interrumpe para pedirlo. No es un mensaje de error: es parte del flujo.',
  ].join('\n'));
}

/* ══════════════════════ 02 · Plan, supuestos y riesgos ══════════════════════ */

export function chapterTwo(pres, ctx) {
  divider(pres, ctx, {
    num: '02',
    name: 'Plan, supuestos y riesgos',
    promise: 'Cinco días, cinco hitos comprobables.\nNingún atajo que no esté escrito.',
  });
  elPlan(pres, ctx);
  losSupuestos(pres, ctx);
  losRiesgos(pres, ctx);
  lasDecisiones(pres, ctx);
}

function elPlan(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '02 · Plan' });
  title(s, 'Cinco días construidos de abajo arriba: primero la evidencia, después la inteligencia.');
  deck(s, 'Cada día cierra con un hito comprobable por un comando, no con una demostración. Si un día no cerraba, el siguiente no empezaba.');

  const days = [
    ['DÍA 1', 'Cimientos', 'Arquitectura hexagonal, contratos de API, servicios locales y puertas de calidad en marcha.', 'make check en verde'],
    ['DÍA 2', 'Ingesta y evidencia', 'Manual verificado por hash, extracción página a página, publicación atómica e IDs de evidencia.', '111 páginas publicadas'],
    ['DÍA 3', 'Recuperación y respuesta', 'Índice híbrido en Qdrant y grafo documental recuperar → generar → validar con citas ancladas.', 'cita que abre el PDF'],
    ['DÍA 4', 'Reglas y siniestros', 'Ruleset y tabla de culpabilidad transcritos y firmados; grafo de siniestros con interrupción humana.', 'b.10 y matriz resolviendo'],
    ['DÍA 5', 'Evaluación y entrega', 'Golden set, congelación de release, trazas en Langfuse, documentación y guion de demo.', 'release congelada'],
  ];

  const cw = 2.30, gap = 0.12, y0 = 2.52, ch = 3.4;
  days.forEach(([d, name, desc, hito], i) => {
    const x = M + i * (cw + gap);
    card(s, { x, y: y0, w: cw, h: ch, fill: i === 4 ? C.ice : C.paper });
    rrect(s, { x: x + 0.24, y: y0 + 0.26, w: 0.86, h: 0.28, rectRadius: 0.14, fill: { color: C.navy } });
    tb(s, d, { x: x + 0.24, y: y0 + 0.31, w: 0.86, h: 0.22, align: 'center', fontFace: F.head, fontSize: 9.5, bold: true, color: C.paper });
    tb(s, name, { x: x + 0.24, y: y0 + 0.72, w: cw - 0.48, h: 0.56, fontFace: F.head, fontSize: 14.5, bold: true, color: C.ink, lineSpacingMultiple: 0.98 });
    tb(s, desc, { x: x + 0.24, y: y0 + 1.36, w: cw - 0.48, h: 1.3, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.04 });
    tb(s, 'HITO', { x: x + 0.24, y: y0 + 2.68, w: cw - 0.48, h: 0.2, fontFace: F.head, fontSize: 8.5, bold: true, charSpacing: 1, color: C.soft });
    tb(s, hito, { x: x + 0.24, y: y0 + 2.9, w: cw - 0.48, h: 0.4, fontSize: 11, bold: true, color: C.teal, lineSpacingMultiple: 1.0 });
    if (i < 4) tb(s, '›', { x: x + cw, y: y0 + 1.5, w: gap, h: 0.3, align: 'center', fontFace: F.head, fontSize: 15, bold: true, color: C.blue });
  });

  band(s, 'El mayor riesgo se mitigó el día uno: si el dominio hubiera resultado irreducible a reglas verificables, el sistema seguiría siendo útil como RAG documental con citas.', { tone: 'navy' });

  notes(s, [
    'EL PLAN (60 s).',
    '',
    '· El orden no es casual: evidencia antes que inteligencia. El día 2 no genera ni una palabra',
    '  con un LLM; sólo publica el manual de forma verificable. Sin eso, cualquier cita posterior',
    '  sería una promesa.',
    '· Cada hito es un comando, no una captura: make check, el recuento de páginas publicadas,',
    '  una cita que abre el PDF, dos reglas resolviendo extremo a extremo, y la release congelada.',
    '· La banda inferior es la gestión de riesgo de proyecto: el plan tenía una salida digna',
    '  si la parte de reglas no salía. No hizo falta usarla.',
    '',
    'Si preguntan por desviaciones: el día 4 se alargó. La transcripción de la tabla 18×18 se hizo',
    'dos veces a propósito y eso consumió más de lo previsto; se recortó ampliar el golden a mano,',
    'que se resolvió después con generación asistida y revisión adversarial.',
  ].join('\n'));
}

function losSupuestos(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '02 · Supuestos' });
  title(s, 'Seis supuestos declarados por escrito; ninguno escondido dentro del código.');
  deck(s, 'Un supuesto que no se escribe acaba siendo una sorpresa en producción. Éstos están además en la documentación de entrega y en los metadatos del golden set.');

  const items = [
    ['El manual es la única fuente de verdad', 'No se completa con derecho vigente ni con lo que el modelo crea recordar. Es la edición de noviembre de 2004.'],
    ['Las casillas A0–A17 son externas al manual', 'El apartado 12 de la declaración amistosa no está definido en el documento: vive en un catálogo aparte, versionado y validado.'],
    ['El ámbito administrativo se da por bueno', 'Matriculación española o del EEE y aseguradora adherida se asumen salvo que el relato diga lo contrario (art. 4, pág. 10).'],
    ['Un solo usuario, entorno local', 'Sin autenticación multiusuario ni alta disponibilidad: no es lo que la prueba evalúa, y fingirlo habría restado tiempo a lo que sí.'],
    ['Ningún dato real de siniestros', 'Todo el material es el manual público, los cinco casos del enunciado y casos sintéticos derivados del propio manual.'],
    ['Lesiones y vía penal, fuera de alcance', 'El Convenio regula daños materiales entre aseguradoras. El sistema lo declara en lugar de opinar (págs. 27 y 62).'],
  ];

  const cw = 3.831, ch = 1.78, y0 = 2.52;
  items.forEach(([h, d], i) => {
    const x = M + (i % 3) * (cw + 0.3);
    const y = y0 + Math.floor(i / 3) * (ch + 0.26);
    card(s, { x, y, w: cw, h: ch, fill: C.ice });
    dot(s, { x: x + 0.3, y: y + 0.36, d: 0.14, color: C.blue });
    tb(s, h, { x: x + 0.56, y: y + 0.28, w: cw - 0.86, h: 0.56, fontSize: 13, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    tb(s, d, { x: x + 0.3, y: y + 0.92, w: cw - 0.6, h: 0.76, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.04 });
  });

  band(s, 'Los seis se pueden discutir. Ése es el objetivo: un supuesto explícito es negociable, uno implícito es una avería esperando.', { tone: 'navy' });

  notes(s, [
    'SUPUESTOS (45 s). Ir rápido: leer sólo los titulares en negrita y detenerse en dos.',
    '',
    '· «Casillas A0–A17 externas al manual»: es el supuesto más importante y el que más se nota',
    '  en el producto. El manual usa la tabla de culpabilidad pero no define qué maniobra es cada',
    '  casilla — eso está en el impreso de la declaración amistosa. Lo resolví con un catálogo',
    '  aparte, versionado y validado explícitamente, en vez de que el modelo lo adivine.',
    '· «Ámbito administrativo dado por bueno»: si no lo asumiera, todos los casos acabarían',
    '  pidiendo la matrícula y la aseguradora antes de decir nada. Está declarado en el golden.',
  ].join('\n'));
}

function losRiesgos(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '02 · Riesgos' });
  title(s, 'Los cinco riesgos que podían hundir esta prueba, y qué se hizo con cada uno.');
  deck(s, 'Ninguno se cerró con «tener cuidado»: los cinco tienen una contramedida en el código o en el proceso, y se puede señalar dónde está.');

  const rows = [
    ['El modelo alucina una responsabilidad', 'Crítico',
      'La decisión no la emite el LLM. La emite un evaluador determinista sobre reglas firmadas, y una invariante del dominio impide publicar un culpable sin las reglas que lo sostienen.', C.rust],
    ['La tabla 18×18 se transcribe mal', 'Crítico',
      '324 celdas transcritas dos veces de forma independiente, comparadas por un comando y atestadas con firma. Una celda no conciliada no decide.', C.rust],
    ['La cita no sostiene la afirmación', 'Alto',
      'Los identificadores de evidencia apuntan al documento y a la página física, no al fragmento del índice. El visor abre el PDF original por esa página y el revisor juzga.', C.amber],
    ['El golden set se ajusta al sistema', 'Alto',
      'La referencia se construyó contra el manual, con revisión adversarial independiente y prohibiciones explícitas. El holdout se abre una sola vez, tras congelar código y prompts.', C.amber],
    ['Cinco días para catorce reglas', 'Medio',
      'Se priorizó la puerta de aplicabilidad completa y el patrón de una norma subsidiaria, luego replicado a seis más y a la tabla. La que falta se declara, no se disimula.', C.amber],
  ];

  const y0 = 2.68, rh = 0.73;
  const wRisk = 3.3, wImp = 1.0;
  const xImp = M + 3.5, xMit = M + 4.78, wMit = CW - 4.78 - 0.06;

  tb(s, 'RIESGO', { x: M + 0.1, y: y0 - 0.32, w: wRisk, h: 0.22, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft });
  tb(s, 'IMPACTO', { x: xImp, y: y0 - 0.32, w: wImp, h: 0.22, align: 'center', fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft });
  tb(s, 'MITIGACIÓN APLICADA', { x: xMit, y: y0 - 0.32, w: wMit, h: 0.22, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft });

  rows.forEach(([risk, imp, mit, color], i) => {
    const y = y0 + i * rh;
    if (i % 2 === 0) rrect(s, { x: M, y, w: CW, h: rh - 0.06, fill: { color: C.ice } });
    tb(s, risk, { x: M + 0.1, y: y + 0.2, w: wRisk, h: 0.44, fontSize: 13, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    rrect(s, { x: xImp, y: y + 0.19, w: wImp, h: 0.3, rectRadius: 0.15, fill: { color: color === C.rust ? C.rustSoft : C.amberSoft } });
    tb(s, imp, { x: xImp, y: y + 0.24, w: wImp, h: 0.22, align: 'center', fontSize: 10, bold: true, color });
    tb(s, mit, { x: xMit, y: y + 0.12, w: wMit, h: 0.58, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.02 });
  });

  band(s, 'El patrón se repite: cada riesgo de generación se responde con una frontera de código, y cada riesgo de transcripción con una firma humana.', { tone: 'navy' });

  notes(s, [
    'RIESGOS (60 s). No leer la columna de mitigaciones entera; contar dos y ofrecer el resto.',
    '',
    '· Riesgo 1: es EL riesgo de un sistema así. La respuesta no es un prompt mejor: es que el',
    '  modelo no tenga la última palabra. Hay una invariante en el dominio que lanza excepción',
    '  si alguien intenta construir una decisión «resuelta» sin las reglas que la sostienen.',
    '· Riesgo 2: la tabla de culpabilidad son 324 celdas leídas de un PDF de 2004. Un error de',
    '  transcripción es un error de atribución de responsabilidad. Por eso se transcribió dos veces',
    '  y hay un comando que compara ambas transcripciones.',
    '',
    'Si preguntan por el riesgo 4 (golden ajustado al sistema): reconocer que es el más difícil',
    'de cerrar del todo, y que la contramedida completa —abrir el holdout una sola vez tras',
    'congelar— está definida y todavía no ejecutada.',
  ].join('\n'));
}

function lasDecisiones(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '02 · Decisiones' });
  title(s, 'Seis decisiones técnicas, con el motivo y el precio que se pagó por cada una.');
  deck(s, 'Una decisión sin coste declarado no es una decisión: es una preferencia. Éstas son las seis que más condicionan el resto del sistema.');

  const rows = [
    ['Arquitectura hexagonal', 'El núcleo no puede depender de un SDK que cambia cada trimestre.', 'Más módulos y más ceremonia en el arranque.'],
    ['LangGraph como adaptador, no como marco', 'La orquestación es un detalle: los casos de uso hablan con un puerto, no con el framework.', 'Renunciar a los atajos del framework dentro del dominio.'],
    ['Reglas en un artefacto firmado, no en el código', 'Una regla debe poder revisarla una persona de negocio, versionarse y llevar firma.', 'Un lenguaje de predicados cerrado y deliberadamente corto.'],
    ['Salida estructurada para extraer hechos', 'El modelo rellena un vocabulario cerrado; no redacta la conclusión.', 'Un prompt de extracción largo y muy acotado que hay que mantener.'],
    ['Recuperación híbrida con fusión nativa', 'El manual mezcla lenguaje jurídico con referencias literales como «b.10» o «art. 35».', 'Dos representaciones del texto que mantener sincronizadas.'],
    ['Langfuse autoalojado en vez de SaaS', 'Trazas, datasets y experimentos sin que salga un solo dato de la máquina.', 'Siete contenedores que operar en local.'],
  ];

  const y0 = 2.68, rh = 0.61;
  const wDec = 3.5, xWhy = M + 3.72, wWhy = 4.6, xCost = M + 8.5, wCost = CW - 8.5 - 0.06;

  tb(s, 'DECISIÓN', { x: M + 0.1, y: y0 - 0.32, w: wDec, h: 0.22, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft });
  tb(s, 'POR QUÉ', { x: xWhy, y: y0 - 0.32, w: wWhy, h: 0.22, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft });
  tb(s, 'COSTE ACEPTADO', { x: xCost, y: y0 - 0.32, w: wCost, h: 0.22, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft });

  rows.forEach(([dec, why, cost], i) => {
    const y = y0 + i * rh;
    if (i % 2 === 0) rrect(s, { x: M, y, w: CW, h: rh - 0.06, fill: { color: C.ice } });
    tb(s, dec, { x: M + 0.1, y: y + 0.1, w: wDec, h: 0.42, fontSize: 12, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    tb(s, why, { x: xWhy, y: y + 0.1, w: wWhy, h: 0.42, fontSize: 11, color: C.muted, lineSpacingMultiple: 1.02 });
    tb(s, cost, { x: xCost, y: y + 0.1, w: wCost, h: 0.42, fontSize: 11, color: C.amber, lineSpacingMultiple: 1.02 });
  });

  band(s, 'Las seis comparten una intención: que dentro de seis meses se pueda cambiar el modelo, el índice o el orquestador sin volver a discutir quién responde en un alcance por detrás.', { tone: 'navy' });

  notes(s, [
    'DECISIONES (60 s). Es la lámina que el enunciado pide explícitamente («rationale behind the',
    'main technical decisions»). Contar dos y dejar el resto para preguntas.',
    '',
    '· Decisión 3 (reglas en artefacto firmado) es la que más se nota: el fichero de reglas lleva',
    '  para cada regla su evidencia en el manual, su descripción, su consecuencia y el identificador',
    '  de quien la revisó. Cambiar una regla no es cambiar código.',
    '· Decisión 5 (híbrida): la búsqueda puramente semántica falla justo donde este manual es más',
    '  útil — cuando alguien pregunta por «la b.10» o por «el artículo 35». BM25 en español',
    '  recupera eso; los embeddings recuperan la intención. La fusión es determinista.',
    '',
    'La banda inferior es el argumento de cierre del bloque: la arquitectura compra opcionalidad.',
  ].join('\n'));
}
