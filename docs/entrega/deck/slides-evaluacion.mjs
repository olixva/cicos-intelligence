import {
  W, H, M, CW, RIGHT, C, F, tb, rect, rrect, ell, card, pill, chip, dot, arrow,
  title, deck, band, notes, page, divider, hline, LOG,
} from './lib.mjs';

/* ═══════════════════════════════════ 04 · Demo ══════════════════════════════ */

export function chapterFour(pres, ctx) {
  divider(pres, ctx, {
    num: '04',
    name: 'Demo en vivo',
    promise: 'Cuatro recorridos sobre el sistema real, en local.\nLo que hay que creerse no son las láminas.',
    shot: new URL('./assets/ui-empty.png', import.meta.url).pathname,
  });
  demo(pres, ctx, {
    n: '1', head: 'Enrutado y consulta documental',
    input: '«¿Qué establece el manual sobre la alcoholemia?»',
    watch: [
      ['El modo se detecta solo', 'La interfaz declara «Consulta del manual» antes de responder. El usuario ve por qué recorrido va, siempre.'],
      ['La respuesta llega por bloques', 'Y cada bloque trae su cita. No hay un párrafo con una bibliografía al final.'],
      ['La cita abre el manual', 'Se pulsa y aparece el PDF original por la página 9, junto a la respuesta, sin salir de la conversación.'],
    ],
    close: 'Es el recorrido más sencillo y ya enseña las tres garantías: recorrido explícito, cita por afirmación y evidencia abrible.',
    speak: [
      'Escribir la pregunta en modo Automático (sin elegir modo).',
      'Señalar la etiqueta de modo detectado ANTES de leer la respuesta.',
      'Pulsar la cita y dejar que se vea el PDF abrirse por la página 9.',
      'Si alguien pregunta por el resaltado: con el índice activo (pypdf) no hay coordenadas',
      'verificadas, así que se abre la página completa en vez de fingir un resaltado. Con el',
      'perfil Docling sí las habría. Es la decisión de la lámina de parsers.',
    ],
  });
  demo(pres, ctx, {
    n: '2', head: 'El siniestro que sí se resuelve',
    input: 'Caso de demo accident-04-lane-change-es · cambio de carril con versiones opuestas',
    watch: [
      ['Hechos extraídos, con atribución', 'lane_change_acknowledged_by_both, contradictory_versions, lane_change_vehicle — cada uno con el texto literal del relato que lo sostiene.'],
      ['La tarjeta «Reglas evaluadas»', 'Enseña las que casan y también las que no casan, con el motivo. La ausencia de una regla es información.'],
      ['Decisión: resuelto', 'Convenio aplicable · ASCIDE · responde el vehículo A, citando la norma subsidiaria b.10 en la página 75.'],
    ],
    close: 'Éste es el único de los cinco casos del enunciado que se resuelve con lo que el propio relato aporta. Y se ve por qué.',
    speak: [
      'Usar el ejemplo de demo, no escribir el relato a mano (ahorra 40 segundos).',
      'Expandir «Reglas evaluadas» y recorrer los hechos: insistir en que llevan el texto literal.',
      'Leer la conclusión en voz alta y abrir la cita de la página 75.',
      'Rematar: «El modelo no ha decidido esto. Ha rellenado tres hechos y el motor ha aplicado',
      'una norma firmada que cualquiera puede leer en el artefacto.»',
    ],
  });
  demo(pres, ctx, {
    n: '3', head: 'Abstenerse con criterio, y pedir el dato exacto',
    input: 'accident-02-pile-up-es · la tabla de culpabilidad con A2 + B4 · una pregunta fuera de alcance',
    watch: [
      ['Fuera del Convenio, con fundamento', 'La colisión múltiple se declara no aplicable citando las páginas 56 y 57. No hay conclusión inventada ni un «depende».'],
      ['La interrupción en directo', 'Con A2 y B4 declaradas, el sistema se detiene y pide el hecho de la observación impresa, con su texto literal.'],
      ['Las dos ramas de la excepción', 'Si abre la puerta el conductor de B, responde B. Si la abre el de A, la excepción retira la atribución y queda indeterminado — sin inventar quién paga.'],
    ],
    close: 'Y la pregunta fuera de alcance: el sistema se abstiene sin dar cifras, en vez de improvisar un baremo que el manual no contiene.',
    speak: [
      'Empezar por la colisión múltiple: es el caso que más sorprende (cinco coches, y se cae del',
      'Convenio por la puerta de entrada).',
      'Después la matriz: declarar las casillas en el relato, provocar la interrupción, responder',
      'primero «abrió la puerta el de B» y luego repetir con «el de A» para enseñar las dos ramas.',
      'Cerrar con la pregunta fuera de alcance (baremo de lesiones): comprobar que NO da cifras.',
      '',
      'Es la demo más importante de las cuatro. Si hay que recortar tiempo, recortar la 1, no ésta.',
    ],
  });
  demo(pres, ctx, {
    n: '4', head: 'Trazabilidad y operación',
    input: 'Langfuse local · modo administrador de ingesta',
    watch: [
      ['La traza de la ejecución que acaban de ver', 'Cada respuesta enlaza a su traza real. Nodos del grafo, llamadas al modelo, coste y latencia por etapa.'],
      ['Un hilo, una sesión', 'El session_id agrupa todos los pasos de la misma conversación, incluida la interrupción y su reanudación.'],
      ['Modo administrador', 'Hash verificado, 111 páginas, extracciones publicadas y previsualización paginada de lo que realmente se indexó.'],
    ],
    close: 'La misma traza que mira quien opera el sistema es la que alimenta la evaluación. No hay una instrumentación para la demo y otra para producción.',
    speak: [
      'Abrir la traza del caso de la demo 2 desde el enlace «Ver en Langfuse» de la propia respuesta.',
      'Enseñar el desglose por etapa: es donde se ve que el coste real por consulta es pequeño.',
      'Pasar al modo administrador y enseñar la previsualización de la extracción.',
      'Rematar con la frase de la banda: producto, modelo y evaluación miran la misma traza.',
    ],
  });
}

function demo(pres, ctx, { n, head, input, watch, close, speak }) {
  const s = page(pres, ctx, { eyebrow: '04 · Demo en vivo', dark: true });
  LOG[LOG.length - 1].title = `Demo ${n} — ${head}`;

  rrect(s, { x: M, y: 1.0, w: 1.72, h: 0.46, rectRadius: 0.1, fill: { color: C.teal } });
  tb(s, `DEMO ${n}`, { x: M, y: 1.11, w: 1.72, h: 0.26, align: 'center', fontFace: F.head, fontSize: 13, bold: true, color: C.paper });
  tb(s, head, { x: M + 2.0, y: 0.98, w: 9.1, h: 0.56, fontFace: F.head, fontSize: 29, bold: true, color: C.paper });

  rrect(s, { x: M, y: 1.86, w: CW, h: 0.5, rectRadius: 0.1, fill: { color: C.deep } });
  tb(s, input, { x: M + 0.3, y: 1.98, w: CW - 0.6, h: 0.28, fontFace: F.mono, fontSize: 11.5, color: C.sky });

  tb(s, 'QUÉ HAY QUE MIRAR', {
    x: M, y: 2.62, w: 6, h: 0.24, fontFace: F.head, fontSize: 10, bold: true, charSpacing: 1.3, color: C.sky,
  });

  const cw = 3.831, y0 = 2.94, ch = 3.02;
  watch.forEach(([h, d], i) => {
    const x = M + i * (cw + 0.3);
    card(s, { x, y: y0, w: cw, h: ch, dark: true });
    chip(s, i + 1, { x: x + 0.3, y: y0 + 0.32, d: 0.4, fill: C.sky, color: C.navy, size: 12 });
    tb(s, h, { x: x + 0.3, y: y0 + 0.9, w: cw - 0.6, h: 0.6, fontFace: F.head, fontSize: 14.5, bold: true, color: C.paper, lineSpacingMultiple: 1.0 });
    tb(s, d, { x: x + 0.3, y: y0 + 1.58, w: cw - 0.6, h: 1.28, fontSize: 12, color: C.pale, lineSpacingMultiple: 1.08 });
  });

  band(s, close, { tone: 'dark' });

  notes(s, [
    `DEMO ${n} — ${head}`,
    '',
    'Guion en pantalla:',
    ...speak.map((l) => (l ? `· ${l}` : '')),
    '',
    'Antes de empezar la demo: make local-services-up, make serve-backend, make serve-frontend,',
    'y comprobar GET /health/ready → {"status":"ready"}. Tener Langfuse ya abierto en otra pestaña.',
  ].join('\n'));
}

/* ═════════════════════ 05 · Evaluación, límites y futuro ════════════════════ */

export function chapterFive(pres, ctx) {
  divider(pres, ctx, {
    num: '05',
    name: 'Evaluación y límites',
    promise: '110 casos de referencia, un protocolo de medida\ny una lista explícita de lo que este sistema no hace.',
  });
  goldenSet(pres, ctx);
  anatomia(pres, ctx);
  protocolo(pres, ctx);
  observabilidad(pres, ctx);
  gates(pres, ctx);
  limites(pres, ctx);
  roadmap(pres, ctx);
  cierre(pres, ctx);
}

function goldenSet(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '05 · Evaluación' });
  title(s, '110 casos de referencia construidos contra el manual, no contra el sistema.');
  deck(s, 'El enunciado pedía «una evaluación básica de la calidad de las respuestas». La parte difícil no es medir: es tener una referencia en la que se pueda confiar.');

  const stats = [
    ['110', 'casos admitidos', C.navy],
    ['57 / 53', 'siniestros / consultas', C.blue],
    ['105', 'en castellano', C.teal],
    ['111', 'páginas en el pool de evidencia', C.amber],
  ];
  stats.forEach(([v, l, color], i) => {
    const x = M + i * 3.05;
    tb(s, v, { x, y: 2.46, w: 2.8, h: 0.66, fontFace: F.head, fontSize: 38, bold: true, color });
    tb(s, l, { x, y: 3.12, w: 2.8, h: 0.4, fontSize: 11.5, color: C.muted });
  });

  const comp = [
    ['5 accidentes del enunciado', 'Los que adjunta la prueba, resueltos a mano contra el manual. Son el criterio de aceptación, y están en el conjunto desde el primer día.'],
    ['5 variantes en castellano', 'El siniestro que se resuelve, el que se excluye, dos consultas documentales y una pregunta que el sistema no debe responder.'],
    ['100 casos sintéticos derivados del manual', 'Mitad consulta y mitad siniestro, cada uno anclado a páginas reales. Generados y después revisados de forma adversarial, no aceptados tal cual.'],
  ];
  const cw = 3.831, y0 = 3.76, ch = 1.9;
  comp.forEach(([h, d], i) => {
    const x = M + i * (cw + 0.3);
    card(s, { x, y: y0, w: cw, h: ch, fill: C.ice });
    tb(s, h, { x: x + 0.28, y: y0 + 0.26, w: cw - 0.56, h: 0.56, fontSize: 13, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    tb(s, d, { x: x + 0.28, y: y0 + 0.88, w: cw - 0.56, h: 0.92, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.04 });
  });

  rrect(s, { x: M, y: 5.78, w: CW, h: 0.46, rectRadius: 0.1, fill: { color: C.band } });
  tb(s, 'release synthetic-expansion-110-2026-09-03   ·   allianz golden validate → errors: [], item_count: 110', {
    x: M, y: 5.89, w: CW, h: 0.28, align: 'center', fontFace: F.mono, fontSize: 9.5, color: C.navy,
  });

  band(s, 'Cada caso se congela con firma: no se puede «mejorar» el golden después de ver los resultados sin que quede constancia de que se hizo.', { tone: 'navy' });

  notes(s, [
    'GOLDEN SET (60 s).',
    '',
    '· El punto no es el número. Es que hay una referencia escrita ANTES de mirar lo que el',
    '  sistema contesta, y que está anclada a páginas concretas del manual.',
    '· Los cinco del enunciado son el criterio de aceptación. Los resolví a mano el primer día:',
    '  es la tabla del bloque 01.',
    '· Los 100 sintéticos se generaron a partir del manual y se revisaron de forma adversarial.',
    '  No se aceptaron tal cual: hay una pasada que corrigió paquetes de evidencia demasiado',
    '  estrictos y requisitos sin cita que los sostuviera.',
    '· La release se congela con hash de contenido y de esquema. Eso es lo que impide el vicio',
    '  clásico de retocar el golden cuando los resultados no gustan.',
  ].join('\n'));
}

function anatomia(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '05 · Evaluación' });
  title(s, 'Un caso golden no guarda una respuesta: guarda qué debe cumplirse y qué está prohibido.');
  deck(s, 'Comparar cadenas de texto no mide nada en un dominio donde dos redacciones distintas pueden ser igual de correctas. Por eso la referencia es una especificación, no un texto modelo.');

  const fields = [
    ['reference', 'La resolución razonada del caso, con las citas del manual que la sostienen paso a paso.', C.navy],
    ['decisions', 'Aplicabilidad, convenio y decisión esperada: los tres ejes que un siniestro tiene que fijar.', C.blue],
    ['requirements', 'Afirmaciones que la respuesta debe contener para considerarse correcta.', C.teal],
    ['acceptable_alternatives', 'Redacciones distintas que también son correctas: evita penalizar la forma en lugar del fondo.', C.teal],
    ['forbidden_facts', 'Lo que la respuesta no puede decir. Por ejemplo, presumir la culpa de quien alcanza por detrás.', C.rust],
    ['evidence_requirements', 'Paquetes de evidencia AND/OR: qué páginas hay que citar, y cuáles son intercambiables entre sí.', C.amber],
  ];

  const cw = 5.866, y0 = 2.5, rh = 0.62;
  fields.forEach(([name, desc, color], i) => {
    const x = M + (i % 2) * (cw + 0.36);
    const y = y0 + Math.floor(i / 2) * (rh + 0.14);
    rrect(s, { x, y, w: cw, h: rh, rectRadius: 0.09, fill: { color: C.ice } });
    tb(s, name, { x: x + 0.24, y: y + 0.09, w: 2.2, h: 0.24, fontFace: F.mono, fontSize: 10.5, bold: true, color });
    tb(s, desc, { x: x + 2.5, y: y + 0.08, w: cw - 2.74, h: 0.48, fontSize: 10.5, color: C.muted, lineSpacingMultiple: 1.02 });
  });

  card(s, { x: M, y: 4.9, w: CW, h: 1.3, fill: C.paper });
  tb(s, 'CÓMO SE REVISÓ — Y QUÉ NO SE PUEDE AFIRMAR DE ESA REVISIÓN', {
    x: M + 0.32, y: 5.06, w: 8, h: 0.24, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft,
  });
  const steps = [
    ['1 · Resolución ciega', 'Cada caso se resuelve contra el manual sin ver la respuesta del sistema.'],
    ['2 · Revisión adversarial', 'Una segunda pasada independiente intenta tumbar la resolución y sus citas.'],
    ['3 · Adjudicación', 'Se concilian ambas y se anota el desacuerdo en los metadatos del caso.'],
  ];
  steps.forEach(([h, d], i) => {
    const x = M + 0.32 + i * 3.9;
    tb(s, h, { x, y: 5.36, w: 3.6, h: 0.24, fontSize: 12, bold: true, color: C.navy });
    tb(s, d, { x, y: 5.6, w: 3.6, h: 0.48, fontSize: 10.5, color: C.muted, lineSpacingMultiple: 1.02 });
  });

  band(s, 'Limitación declarada, no escondida: los tres pasos los hizo una IA. Ningún caso tiene todavía revisión de un experto humano del dominio, y eso consta en los metadatos de cada uno.', { tone: 'amber' });

  notes(s, [
    'ANATOMÍA DE UN CASO (55 s).',
    '',
    '· La idea clave: comparar texto con texto no sirve. «El Convenio no es de aplicación» y',
    '  «este siniestro queda fuera del Convenio» son la misma respuesta. Por eso la referencia',
    '  es una especificación con requisitos, alternativas aceptables y prohibiciones.',
    '· forbidden_facts es mi campo favorito: recoge los errores plausibles. En el alcance por',
    '  detrás, presumir la culpa del que alcanza es exactamente lo que un modelo haría por',
    '  sentido común, y el manual no lo sostiene.',
    '· La banda ámbar es deliberada. Es la limitación más seria del trabajo de evaluación y',
    '  prefiero decirla yo antes de que la pregunten: la revisión es de IA, en tres pasos y',
    '  documentada, pero no es un perito humano.',
  ].join('\n'));
}

function protocolo(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '05 · Evaluación' });
  title(s, 'La evaluación está diseñada como un experimento, no como una captura de pantalla.');
  deck(s, 'Lo que hace creíble a una métrica es el protocolo que la rodea: qué se mide, contra qué versión exacta, y qué está prohibido tocar.');

  const blocks = [
    ['QUÉ SE MIDE', C.navy, [
      'Corrección factual frente a la referencia',
      'Fidelidad de las citas: si la página sostiene la afirmación',
      'Acierto del enrutado entre consulta y siniestro',
      'Abstención correcta — la métrica que más importa aquí',
    ]],
    ['CÓMO SE MIDE', C.blue, [
      'La release congelada se publica como dataset',
      'Un experimento por release, no ejecuciones sueltas',
      'Evaluadores deterministas antes que jueces LLM',
      'Cada ejecución identifica commit, hashes, perfil y modelos',
    ]],
    ['QUÉ ESTÁ PROHIBIDO', C.rust, [
      'Ajustar el sistema mirando la reserva de holdout',
      'Retocar el golden después de ver los resultados',
      'Publicar una métrica sin la configuración que la produjo',
      'Activar un índice porque exista y no porque mida mejor',
    ]],
  ];

  const cw = 3.831, y0 = 2.5, ch = 2.66;
  blocks.forEach(([head, color, items], i) => {
    const x = M + i * (cw + 0.3);
    card(s, { x, y: y0, w: cw, h: ch });
    tb(s, head, { x: x + 0.3, y: y0 + 0.28, w: cw - 0.6, h: 0.26, fontFace: F.head, fontSize: 11.5, bold: true, charSpacing: 1.2, color });
    items.forEach((t, j) => {
      const y = y0 + 0.7 + j * 0.48;
      dot(s, { x: x + 0.3, y: y + 0.08, d: 0.11, color });
      tb(s, t, { x: x + 0.56, y, w: cw - 0.86, h: 0.44, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.02 });
    });
  });

  card(s, { x: M, y: 5.30, w: CW, h: 1.02, fill: C.amberSoft });
  tb(s, 'ESTADO REAL A DÍA DE HOY — sin adornos', {
    x: M + 0.32, y: 5.44, w: 6, h: 0.24, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.amber,
  });
  tb(s, 'Construido y comprobable ahora mismo: el golden de 110 casos (allianz golden validate → errors: [], item_count: 110), la release congelada con sus hashes y el ejecutor de experimentos sobre el recorrido documental.   ·   En curso: la campaña completa sobre los 110 casos, los evaluadores de siniestro y de enrutado, y publicar esta release como dataset en el proyecto de Langfuse en uso.   ·   Pendiente por decisión: congelar la reserva de holdout, que se abre una sola vez y todavía no toca.', {
    x: M + 0.32, y: 5.70, w: CW - 0.64, h: 0.54, fontSize: 10.5, color: C.amber, lineSpacingMultiple: 1.06,
  });

  band(s, 'Prefiero presentar el protocolo terminado y las métricas en curso, antes que un número redondo cuya procedencia no pueda defender delante de vosotros.', { tone: 'navy' });

  notes(s, [
    'PROTOCOLO DE EVALUACIÓN (60 s). Lámina delicada: hay que ser exacto.',
    'COMPROBADO el 2026-09-03: allianz golden validate devuelve errors: [] e item_count: 110,',
    'y el proyecto de Langfuse en uso todavía no tiene el dataset publicado (la API de datasets',
    'devuelve 0). Por eso la caja ámbar lo pone en "en curso" y no en "construido".',
    '',
    '· Contar primero el protocolo. Es lo que se está evaluando en esta prueba: si sé montar una',
    '  evaluación creíble, no si tengo un número bonito.',
    '· «Abstención correcta» como métrica principal es la consecuencia directa del bloque 01:',
    '  en cuatro de los cinco casos del enunciado, acertar es abstenerse.',
    '· La caja ámbar es el estado real. Decirla tal cual, sin apurarse:',
    '  hecho = golden + release congelada + dataset + runner documental;',
    '  en curso = campaña completa y evaluadores de siniestro y router;',
    '  pendiente = holdout, que se abre una sola vez y por eso no se ha abierto.',
    '',
    'SI PARA ENTONCES HAY NÚMEROS: sustituir la caja ámbar por las métricas reales',
    '(precisión de enrutado, fidelidad de citas, abstención correcta) e indicar sobre qué',
    'release y qué commit se midieron. No añadir ninguna métrica que no venga de una ejecución.',
  ].join('\n'));
}

function observabilidad(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '05 · Operación' });
  title(s, 'Cada ejecución deja huella: producto, modelo y evaluación miran la misma traza.');
  deck(s, 'La observabilidad no se añadió para la demo. Es la misma instrumentación que alimenta los experimentos y la que permitiría investigar una queja real.');

  const left = [
    ['Los tres workflows, nodo a nodo', 'Documental, siniestros y enrutado automático, con su estado de entrada y salida.'],
    ['Todas las llamadas al modelo', 'Generación, extracción de hechos, clasificación y embeddings, con coste y latencia por etapa.'],
    ['Un hilo, una sesión', 'El session_id agrupa la conversación completa, incluida la interrupción y su reanudación.'],
    ['Datasets y experimentos, junto a las trazas', 'El mismo despliegue aloja los datasets de evaluación y sus ejecuciones: la medida no acaba en una hoja de cálculo aparte.'],
  ];
  card(s, { x: M, y: 2.5, w: 7.2, h: 3.3 });
  tb(s, 'QUÉ SE TRAZA', { x: M + 0.32, y: 2.68, w: 5, h: 0.24, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.soft });
  left.forEach(([h, d], i) => {
    const y = 3.04 + i * 0.68;
    dot(s, { x: M + 0.32, y: y + 0.08, d: 0.13, color: C.blue });
    tb(s, h, { x: M + 0.6, y, w: 6.3, h: 0.26, fontSize: 12.5, bold: true, color: C.ink });
    tb(s, d, { x: M + 0.6, y: y + 0.28, w: 6.3, h: 0.36, fontSize: 11, color: C.muted, lineSpacingMultiple: 1.02 });
  });

  card(s, { x: M + 7.56, y: 2.5, w: CW - 7.56, h: 3.3, fill: C.navy });
  tb(s, 'POR QUÉ AUTOALOJADO', { x: M + 7.86, y: 2.68, w: 3.8, h: 0.24, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.1, color: C.sky });
  tb(s, 'Langfuse corre en local, con su propia base de datos, su almacén de objetos y su motor analítico.\n\nNi un relato de accidente ni una traza salen de la máquina. En un dominio donde el material de entrada son declaraciones de siniestro, esa propiedad no es un detalle de despliegue: es un requisito.\n\nY el mismo despliegue sirve para trazas, datasets y experimentos.', {
    x: M + 7.86, y: 3.04, w: CW - 8.16, h: 2.6, fontSize: 12, color: C.pale, lineSpacingMultiple: 1.08,
  });

  band(s, 'El enlace «Ver en Langfuse» de cada respuesta abre la traza real de esa ejecución concreta: «¿por qué contestó esto?» se responde con una traza, no con una conjetura.', { tone: 'navy' });

  notes(s, [
    'OBSERVABILIDAD (45 s).',
    '',
    '· Insistir en lo de autoalojado: el material de entrada de este sistema son relatos de',
    '  siniestro. Mandarlos a un SaaS de observabilidad para una prueba técnica habría sido',
    '  cómodo y equivocado.',
    '· El argumento de producto: el enlace de cada respuesta lleva a SU traza. Cuando alguien',
    '  discuta una conclusión, se abre la ejecución exacta con los hechos extraídos, las reglas',
    '  evaluadas y las llamadas al modelo.',
    '· Y el argumento de ingeniería: datasets y experimentos viven en el mismo sitio, así que la',
    '  evaluación no es un cuaderno aparte que se desincroniza.',
  ].join('\n'));
}

function gates(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '05 · Ingeniería' });
  title(s, 'Nada entra sin pasar cinco puertas, y las cinco están verdes hoy.');
  deck(s, 'Ejecutadas sobre este repositorio antes de preparar esta presentación. Un solo comando las reproduce en local.');

  const stats = [
    ['500', 'pruebas de backend', 'pytest · 1 omitida', C.navy],
    ['97', 'pruebas de frontend', 'vitest · 17 ficheros', C.blue],
    ['0', 'errores de tipado', 'pyright estricto + TS estricto', C.teal],
    ['0', 'deriva de contrato', 'los tipos del cliente salen del OpenAPI', C.teal],
    ['0', 'avisos de linter', 'ruff + eslint', C.teal],
  ];
  const cw = 2.30, gap = 0.12, y0 = 2.5, ch = 2.1;
  stats.forEach(([v, l, d, color], i) => {
    const x = M + i * (cw + gap);
    card(s, { x, y: y0, w: cw, h: ch });
    tb(s, v, { x: x + 0.24, y: y0 + 0.26, w: cw - 0.48, h: 0.72, fontFace: F.head, fontSize: 42, bold: true, color });
    tb(s, l, { x: x + 0.24, y: y0 + 1.06, w: cw - 0.48, h: 0.46, fontSize: 12.5, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    tb(s, d, { x: x + 0.24, y: y0 + 1.54, w: cw - 0.48, h: 0.44, fontSize: 10.5, color: C.muted, lineSpacingMultiple: 1.02 });
  });

  const extra = [
    ['11.848 líneas en 111 módulos de backend', 'Módulos pequeños y con una responsabilidad: es lo que hace que un cambio de dominio no arrastre media aplicación.'],
    ['51 módulos de frontend, tipos generados', 'React 19 con TypeScript estricto. Los DTO no se escriben dos veces: se generan del contrato que publica el backend.'],
    ['El dominio se prueba sin red ni contenedores', 'Las reglas, la tabla de culpabilidad y las invariantes son funciones puras: sus pruebas corren en milisegundos.'],
  ];
  const ew = 3.831;
  extra.forEach(([h, d], i) => {
    const x = M + i * (ew + 0.3);
    card(s, { x, y: 4.86, w: ew, h: 1.36, fill: C.ice });
    tb(s, h, { x: x + 0.28, y: 5.04, w: ew - 0.56, h: 0.46, fontSize: 12, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    tb(s, d, { x: x + 0.28, y: 5.5, w: ew - 0.56, h: 0.66, fontSize: 10.5, color: C.muted, lineSpacingMultiple: 1.04 });
  });

  band(s, 'make check reproduce las cinco puertas. Si una se cae, el trabajo no está terminado — da igual lo bien que se vea en pantalla.', { tone: 'navy' });

  notes(s, [
    'GATES (40 s). Ir rápido, es una lámina de confianza, no de contenido.',
    '',
    '· Las cifras están medidas hoy sobre este repositorio, no son de memoria.',
    '· El punto que merece detenerse: la deriva de contrato. El frontend no tiene una segunda',
    '  definición manual de los tipos de la API; se generan del OpenAPI que publica FastAPI, y',
    '  hay una comprobación que falla si el contrato y el código se separan.',
    '· El tercer bloque de abajo es consecuencia directa de la arquitectura hexagonal: el dominio',
    '  se prueba sin levantar Qdrant ni llamar a ningún modelo.',
  ].join('\n'));
}

function limites(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '05 · Límites' });
  title(s, 'Lo que este sistema no hace — dicho aquí, y no en la letra pequeña.');
  deck(s, 'La misma disciplina que hace que el sistema se abstenga en un siniestro se aplica a cómo se presenta el sistema.');

  const items = [
    ['No es derecho vigente', 'El manual es la edición de noviembre de 2004. El sistema responde lo que ese documento dice, no lo que hoy sea aplicable.'],
    ['No cubre lesiones ni vía penal', 'El Convenio regula daños materiales entre aseguradoras. Ante un baremo de lesiones el sistema se abstiene, sin dar cifras.'],
    ['No infiere las casillas de la declaración', 'Si el relato no declara qué marcaron los conductores en el apartado 12, la tabla de culpabilidad no entra. Deducirlo sería inventar el dato decisivo.'],
    ['No hay revisión de un experto humano', 'El golden set es una referencia sintética auditada contra el manual con revisión de IA en tres pasos. No es un baremo pericial.'],
    ['No hay todavía reserva de holdout', 'Los 110 casos están en desarrollo. La reserva se congela y se abre una sola vez, después de congelar código, prompts y reglas.'],
    ['Una de las catorce reglas sigue pendiente', 'b.11, rotondas. Devuelve insufficient_data de forma explícita, y el motivo técnico está documentado.'],
  ];

  const cw = 5.866, y0 = 2.5, rh = 1.0;
  items.forEach(([h, d], i) => {
    const x = M + (i % 2) * (cw + 0.36);
    const y = y0 + Math.floor(i / 2) * (rh + 0.2);
    rrect(s, { x, y, w: cw, h: rh, rectRadius: 0.09, fill: { color: C.ice } });
    tb(s, '—', { x: x + 0.28, y: y + 0.2, w: 0.3, h: 0.26, fontFace: F.head, fontSize: 13, bold: true, color: C.rust });
    tb(s, h, { x: x + 0.6, y: y + 0.2, w: cw - 0.9, h: 0.26, fontSize: 13.5, bold: true, color: C.ink });
    tb(s, d, { x: x + 0.6, y: y + 0.5, w: cw - 0.92, h: 0.44, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.04 });
  });

  band(s, 'Ninguno de estos seis límites es una sorpresa de última hora: los seis están escritos en la documentación de entrega y, los que afectan al golden, en los metadatos de cada caso.', { tone: 'navy' });

  notes(s, [
    'LÍMITES (50 s). Contarla entera y sin prisa. Es la lámina que más credibilidad da.',
    '',
    'Frase de entrada: «Esta es la lámina que normalmente no está en una presentación de',
    'entrega. Va aquí porque es exactamente el mismo criterio que hace que el sistema se',
    'abstenga en un siniestro.»',
    '',
    '· El límite 3 es el más importante del dominio: no deducimos las casillas del apartado 12.',
    '· El límite 4 es el más importante de la evaluación: revisión de IA, no de perito.',
    '· El límite 5 es el que un evaluador técnico agradecerá: los 110 casos están en desarrollo.',
    '  Medir sobre ellos y llamarlo generalización sería trampa, y por eso el holdout se abre',
    '  una sola vez.',
  ].join('\n'));
}

function roadmap(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: '05 · Siguiente iteración', dark: true });
  title(s, 'La siguiente iteración avanza por evidencia, no por disponibilidad.', { dark: true, size: 30 });
  deck(s, 'Cuatro movimientos, en este orden. Ninguno exige tocar el dominio: es exactamente lo que la arquitectura tenía que comprar.', { dark: true, y: 2.02 });

  const items = [
    ['Cerrar la campaña de evaluación', 'Publicar métricas por recorrido sobre los 110 casos, con su commit y su configuración. Después, congelar la reserva de holdout.'],
    ['Decidir el perfil de índice con datos', 'Comparar baseline y estructurado sobre el mismo golden. Si Docling gana, se promueve; si no, se queda publicado y sin activar.'],
    ['Revisión humana experta del golden', 'Empezando por los cinco casos del enunciado. Es la limitación declarada más seria y la más barata de cerrar.'],
    ['Completar b.11 y exponer el CLI de índices', 'La regla de rotondas como segunda regla mutuamente excluyente, y la gestión de índices desde el modo administrador.'],
  ];

  const y0 = 2.56, rh = 0.80;
  items.forEach(([h, d], i) => {
    const y = y0 + i * (rh + 0.14);
    rrect(s, { x: M, y, w: CW, h: rh, rectRadius: 0.09, fill: { color: C.darkCard } });
    chip(s, i + 1, { x: M + 0.28, y: y + 0.22, d: 0.42, fill: C.sky, color: C.navy, size: 13 });
    tb(s, h, { x: M + 0.9, y: y + 0.15, w: 4.4, h: 0.56, fontFace: F.head, fontSize: 15, bold: true, color: C.paper, lineSpacingMultiple: 1.0 });
    tb(s, d, { x: M + 5.5, y: y + 0.18, w: CW - 5.8, h: 0.54, fontSize: 12, color: C.pale, lineSpacingMultiple: 1.04 });
  });

  band(s, 'El orden importa: primero medir, después promover. Invertirlo es cómo un sistema demostrable se convierte en uno que sólo parece bueno.', { tone: 'dark', y: 6.42, h: 0.5 });

  notes(s, [
    'ROADMAP (40 s).',
    '',
    '· El orden es el mensaje. Los cuatro puntos podrían hacerse en cualquier orden y he elegido',
    '  éste porque los dos primeros son mediciones y los dos últimos son consecuencias.',
    '· Punto 3: reconocer que es la limitación más seria y también la más barata de cerrar.',
    '  Una tarde de una persona del negocio revisando cinco casos vale más que cien sintéticos.',
    '· Cerrar señalando que ninguno de los cuatro toca el dominio: es la factura que paga la',
    '  arquitectura del bloque 03.',
  ].join('\n'));
}

function cierre(pres, ctx) {
  const s = page(pres, ctx, {
    eyebrow: 'Cierre', dark: true,
    decor: (sl) => {
      ell(sl, { x: 10.2, y: -1.6, w: 5.0, h: 5.0, fill: { color: C.deep } });
      ell(sl, { x: 11.4, y: 3.9, w: 3.0, h: 3.0, fill: { color: '063E82' } });
    },
  });

  LOG[LOG.length - 1].title = 'No es un chatbot sobre un PDF.';

  tb(s, 'No es un chatbot sobre un PDF.', {
    x: M, y: 1.5, w: 9.6, h: 0.8, fontFace: F.head, fontSize: 40, bold: true, color: C.paper,
  });
  tb(s, 'Es una plataforma RAG componible donde la evidencia, la orquestación y la decisión son capas independientes, observables e intercambiables — y donde abstenerse con criterio es una función del producto, no un fallo.', {
    x: M, y: 2.5, w: 9.0, h: 1.0, fontSize: 16, color: C.pale, lineSpacingMultiple: 1.14,
  });

  const pillars = [
    ['INGESTA', 'versionada y verificable'],
    ['RECUPERACIÓN', 'híbrida y reversible'],
    ['DECISIÓN', 'determinista y firmada'],
    ['OPERACIÓN', 'trazable extremo a extremo'],
  ];
  const cw = 2.828, y0 = 3.86;
  pillars.forEach(([h, d], i) => {
    const x = M + i * (cw + 0.26);
    rrect(s, { x, y: y0, w: cw, h: 1.06, rectRadius: 0.1, fill: { color: C.darkCard } });
    tb(s, h, { x: x + 0.2, y: y0 + 0.22, w: cw - 0.4, h: 0.26, align: 'center', fontFace: F.head, fontSize: 12, bold: true, color: C.sky });
    tb(s, d, { x: x + 0.2, y: y0 + 0.54, w: cw - 0.4, h: 0.4, align: 'center', fontSize: 11.5, color: C.paper, lineSpacingMultiple: 1.02 });
  });

  tb(s, 'Gracias.', { x: M, y: 5.5, w: 4, h: 0.6, fontFace: F.head, fontSize: 32, bold: true, color: C.paper });
  tb(s, '¿Preguntas?', { x: M, y: 6.14, w: 5, h: 0.4, fontSize: 17, color: C.sky });

  rrect(s, { x: 7.4, y: 5.52, w: CW - 6.78, h: 1.06, rectRadius: 0.1, fill: { color: C.deep } });
  tb(s, 'A mano para las preguntas:  docs/ESTADO.md (estado verificado)  ·  el ruleset y la matriz firmados  ·  la traza en Langfuse del caso resuelto  ·  el golden set congelado', {
    x: 7.64, y: 5.68, w: CW - 7.26, h: 0.76, fontSize: 11, color: C.pale, lineSpacingMultiple: 1.08,
  });

  notes(s, [
    'CIERRE (30 s) y paso a preguntas.',
    '',
    'Frase de cierre sugerida:',
    '«Si me tuviera que quedar con una sola idea de todo esto: el sistema se abstiene cuando el',
    'manual no da para más, y esa abstención está tan trabajada como las respuestas. En un dominio',
    'donde la salida es quién paga un siniestro, un asistente que siempre responde no es más útil:',
    'es más peligroso.»',
    '',
    'Tener abierto en otra ventana: docs/ESTADO.md, data/rules/ruleset.v1.json, la traza de',
    'Langfuse del caso 4 y el golden congelado. Las láminas del apéndice cubren stack, API,',
    'glosario y comandos.',
  ].join('\n'));
}

/* ═══════════════════════════════════ Apéndice ═══════════════════════════════ */

export function appendix(pres, ctx) {
  divider(pres, ctx, {
    num: 'A',
    name: 'Apéndice',
    promise: 'Material de apoyo para las preguntas: stack, API,\nglosario del dominio y comandos reproducibles.',
  });
  preguntasDificiles(pres, ctx);
  stack(pres, ctx);
  api(pres, ctx);
  glosario(pres, ctx);
  comandos(pres, ctx);
}

function preguntasDificiles(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: 'Apéndice · Preguntas' });
  title(s, 'Las preguntas incómodas, con la respuesta corta y dónde está la larga.');

  const rows = [
    ['«¿Esto no lo está inventando el modelo?»',
      'No: la decisión la emite un evaluador determinista sobre reglas firmadas, y una invariante del dominio impide publicar un culpable sin las reglas que lo sostienen.', 'Láminas 17 y 24'],
    ['«¿Por qué no resuelve los cinco accidentes?»',
      'Porque el manual no da para más con los datos de cada relato. En cuanto el parte aporta las casillas del apartado 12, la tabla entra y resuelve.', 'Lámina 05 y demo 3'],
    ['«¿Qué métricas tenéis?»',
      'El protocolo está terminado y la campaña completa está en curso. Prefiero enseñar la caja de estado real antes que un número que no pueda defender.', 'Lámina 35'],
    ['«¿Por qué no usáis Docling, si es mejor?»',
      'Porque disponible no es lo mismo que mejor. Está publicado y esperando la comparación de evaluación que lo justifique; el comando para compararlos existe.', 'Lámina 20'],
    ['«¿Y si cambiáis de proveedor de modelo?»',
      'Son cuatro puertos distintos: generar, extraer, clasificar e incrustar. El único que no se puede cambiar sin reindexar es el embedding, y la firma del índice lo impide.', 'Láminas 14 y 15'],
    ['«¿Esto no es sobreingeniería para cinco días?»',
      'Costó tiempo el día 1 y lo devolvió el día 4, cuando hubo que meter la tabla de 324 celdas en el flujo sin romper nada de lo anterior.', 'Láminas 11 y 13'],
    ['«¿Quién ha validado el golden set?»',
      'Una IA en tres pasos, documentados caso a caso. No un experto humano del dominio: es la limitación declarada más seria y la primera del roadmap.', 'Láminas 34 y 38'],
  ];

  const y0 = 1.92, rh = 0.63;
  const wQ = 3.9, xA = M + 4.16, wA = 6.1, xW = M + 10.5, wW = CW - 10.5;
  rows.forEach(([q, a, where], i) => {
    const y = y0 + i * rh;
    if (i % 2 === 0) rrect(s, { x: M, y, w: CW, h: rh - 0.05, fill: { color: C.ice } });
    tb(s, q, { x: M + 0.14, y: y + 0.1, w: wQ, h: 0.44, fontSize: 11.5, bold: true, color: C.ink, lineSpacingMultiple: 1.0 });
    tb(s, a, { x: xA, y: y + 0.09, w: wA, h: 0.46, fontSize: 10.5, color: C.muted, lineSpacingMultiple: 1.02 });
    tb(s, where, { x: xW, y: y + 0.17, w: wW, h: 0.26, align: 'right', fontSize: 10, bold: true, color: C.blue });
  });

  band(s, 'La regla para el turno de preguntas: si no lo puedo enseñar o citar, lo digo como pendiente. Nadie penaliza un límite declarado; todo el mundo penaliza uno descubierto.', { tone: 'navy' });

  notes(s, [
    'Apéndice. NO se pasa en la presentación: está para tenerla a mano en el turno de preguntas',
    'y para repasarla cinco minutos antes de entrar.',
    '',
    'La columna de la derecha dice a qué lámina saltar si conviene enseñarla al responder.',
  ].join('\n'));
}

function stack(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: 'Apéndice · Stack' });
  title(s, 'Stack completo, y el puerto por el que cada pieza es sustituible.');

  const rows = [
    ['Lenguaje y ejecución', 'Python 3.14 · uv', 'Entorno reproducible y resolución de dependencias rápida'],
    ['API', 'FastAPI · Pydantic 2 · SSE', 'Contrato tipado y publicación del OpenAPI que consume el cliente'],
    ['Orquestación', 'LangGraph · MemorySaver', 'Grafos tipados con checkpoint e interrupción humana'],
    ['Modelos', 'OpenAI (generación, extracción, embeddings, enrutado)', 'Cuatro usos distintos tras cuatro puertos separados'],
    ['Índice', 'Qdrant · denso + BM25 español (fastembed) · RRF nativo', 'Fusión determinista dentro del motor'],
    ['Extracción de PDF', 'pypdf 6.16.2 · Docling 2.124.0', 'Dos perfiles publicados para el mismo documento verificado'],
    ['Observabilidad y evaluación', 'Langfuse autoalojado · Ragas', 'Trazas, datasets, releases y experimentos en local'],
    ['Cliente', 'React 19 · Vite · TypeScript estricto · pdfjs-dist', 'Tipos generados del OpenAPI; visor que rasteriza sólo la página visible'],
    ['Calidad', 'pytest · vitest · pyright · ruff · eslint', 'Cinco puertas reproducibles con un comando'],
  ];

  const y0 = 1.86, rh = 0.5;
  rows.forEach(([a, b, c], i) => {
    const y = y0 + i * rh;
    if (i % 2 === 0) rrect(s, { x: M, y, w: CW, h: rh - 0.04, fill: { color: C.ice } });
    tb(s, a, { x: M + 0.16, y: y + 0.14, w: 2.9, h: 0.3, fontSize: 11.5, bold: true, color: C.ink });
    tb(s, b, { x: M + 3.2, y: y + 0.15, w: 4.4, h: 0.3, fontFace: F.mono, fontSize: 9.5, color: C.navy });
    tb(s, c, { x: M + 7.8, y: y + 0.15, w: CW - 7.96, h: 0.3, fontSize: 10.5, color: C.muted });
  });

  notes(s, 'Apéndice. Sólo si preguntan por el stack. La columna de la derecha explica el porqué de cada elección, que suele ser la pregunta real.');
}

function api(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: 'Apéndice · API' });
  title(s, 'Superficie de API: un sobre común tipado para los tres recorridos.');

  const groups = [
    ['CONVERSACIÓN', C.navy, [
      ['POST /api/v1/queries/resolve', 'Modo automático: clasifica y delega en el recorrido correcto'],
      ['POST /api/v1/questions/answer', 'Consulta documental con citas; admite respuesta por SSE'],
      ['POST /api/v1/claims/analyze', 'Análisis de siniestro; puede devolver una petición de datos'],
    ]],
    ['EVIDENCIA Y DEMO', C.blue, [
      ['GET /api/v1/evidence/{id}', 'Devuelve la evidencia por su identificador estable'],
      ['GET /api/v1/demo/cases', 'Casos de demo, leídos del golden real sin exponer la respuesta esperada'],
      ['GET /api/v1/manual/…', 'Inspección del manual publicado: páginas, extracciones y diagnósticos'],
    ]],
    ['ADMINISTRACIÓN Y SALUD', C.teal, [
      ['POST /api/v1/admin/ingest', 'Ingesta por API; sólo acepta el manual verificado por hash'],
      ['GET /health/ready', 'Preparación real de dependencias, sin llamadas pagadas al modelo'],
      ['GET /openapi.json', 'Contrato del que se generan los tipos del cliente'],
    ]],
  ];

  const cw = 3.831;
  groups.forEach(([head, color, rows], gi) => {
    const x = M + gi * (cw + 0.3);
    tb(s, head, { x, y: 2.2, w: cw, h: 0.24, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.2, color });
    rows.forEach(([ep, d], i) => {
      const y = 2.56 + i * 0.94;
      rrect(s, { x, y, w: cw, h: 0.84, rectRadius: 0.09, fill: { color: C.ice } });
      tb(s, ep, { x: x + 0.24, y: y + 0.14, w: cw - 0.48, h: 0.24, fontFace: F.mono, fontSize: 9.5, color });
      tb(s, d, { x: x + 0.24, y: y + 0.4, w: cw - 0.48, h: 0.36, fontSize: 10.5, color: C.muted, lineSpacingMultiple: 1.02 });
    });
  });

  card(s, { x: M, y: 5.62, w: CW, h: 0.6, fill: C.paper });
  tb(s, 'El sobre de respuesta es común a los tres recorridos: identifica el modo seguido, las etapas ejecutadas, las citas y el estado — por eso la interfaz enseña el razonamiento sin duplicar lógica.', {
    x: M + 0.3, y: 5.79, w: CW - 0.6, h: 0.28, align: 'center', fontSize: 11.5, color: C.ink,
  });

  band(s, 'Un solo contrato publicado en OpenAPI; los tipos del cliente se generan de él, y una comprobación falla si se separan.', { tone: 'navy' });

  notes(s, 'Apéndice. El sobre de respuesta es común a los tres recorridos: identifica el modo seguido, las etapas ejecutadas, las citas y el estado. Es lo que permite que la interfaz enseñe el razonamiento sin lógica duplicada.');
}

function glosario(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: 'Apéndice · Dominio' });
  title(s, 'Glosario mínimo del dominio, para que nadie asienta sin seguirlo.');

  const terms = [
    ['CIDE', 'Convenio de Indemnización Directa Española. Reparto de responsabilidad entre aseguradoras a partir de la declaración amistosa firmada por ambos conductores.'],
    ['ASCIDE', 'Acuerdo Suplementario al CIDE. Aporta la vía informatizada y las normas subsidiarias que resuelven supuestos concretos cuando las versiones no coinciden.'],
    ['CICOS', 'Centro Informático de Compensación de Siniestros: la infraestructura común que liquida entre entidades adheridas.'],
    ['D.A.A.', 'Declaración Amistosa de Accidente, el parte europeo. Su apartado 12 son las casillas que cada conductor marca describiendo su maniobra.'],
    ['Casillas A0–A17 / B0–B17', 'Las dieciocho maniobras del apartado 12 para cada vehículo. Cruzarlas en la tabla de culpabilidad da 324 combinaciones.'],
    ['Norma subsidiaria', 'Regla del ASCIDE que resuelve un supuesto típico —cambio de carril, marcha atrás, rotonda— cuando las declaraciones discrepan.'],
  ];

  const cw = 5.866, y0 = 2.04, rh = 1.10;
  terms.forEach(([t, d], i) => {
    const x = M + (i % 2) * (cw + 0.36);
    const y = y0 + Math.floor(i / 2) * (rh + 0.2);
    card(s, { x, y, w: cw, h: rh, fill: C.ice });
    tb(s, t, { x: x + 0.28, y: y + 0.2, w: cw - 0.56, h: 0.28, fontFace: F.head, fontSize: 14, bold: true, color: C.navy });
    tb(s, d, { x: x + 0.28, y: y + 0.52, w: cw - 0.56, h: 0.54, fontSize: 11, color: C.muted, lineSpacingMultiple: 1.04 });
  });

  band(s, 'El manual es de noviembre de 2004 y estos convenios han evolucionado. El sistema responde lo que este documento dice, y lo declara.', { tone: 'navy' });

  notes(s, 'Apéndice. Útil si en la sala hay perfiles no aseguradores. Los cinco primeros términos aparecen en la demo.');
}

function comandos(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: 'Apéndice · Reproducibilidad' });
  title(s, 'Todo lo que se ha enseñado se reproduce con estos comandos.');

  const groups = [
    ['ARRANQUE', [
      ['make local-services-up', 'Qdrant, Langfuse, PostgreSQL, ClickHouse, Redis y MinIO'],
      ['make serve-backend  ·  make serve-frontend', 'API en :8000 y cliente en :5173'],
      ['curl localhost:8000/health/ready', 'Comprobación de preparación antes de la demo'],
    ]],
    ['EVIDENCIA Y REGLAS', [
      ['allianz compare-parsers', 'Compara la extracción de pypdf y de Docling sobre el mismo documento'],
      ['allianz index-rollback --collection …', 'Devuelve el alias activo al índice anterior, verificando la firma'],
      ['allianz rules validate  ·  compare-transcriptions', 'Valida el ruleset y concilia las dos transcripciones'],
    ]],
    ['CALIDAD', [
      ['make check', 'Las cinco puertas: pruebas, tipado, linter y contrato'],
      ['make check-openapi', 'Verifica que el contrato y el cliente no se han separado'],
    ]],
    ['EVALUACIÓN', [
      ['allianz golden validate', 'errors: [], item_count: 110'],
      ['allianz golden freeze  ·  publish', 'Congela la release con sus hashes y la publica como dataset en Langfuse'],
    ]],
  ];

  const cw = 5.866;
  groups.forEach(([head, rows], gi) => {
    const x = M + (gi % 2) * (cw + 0.36);
    let y = 2.0 + (gi < 2 ? 0 : 2.74);
    tb(s, head, { x, y, w: cw, h: 0.22, fontFace: F.head, fontSize: 9.5, bold: true, charSpacing: 1.2, color: C.blue });
    y += 0.3;
    rows.forEach(([cmd, d]) => {
      rrect(s, { x, y, w: cw, h: 0.66, rectRadius: 0.09, fill: { color: C.ice } });
      tb(s, cmd, { x: x + 0.24, y: y + 0.11, w: cw - 0.48, h: 0.24, fontFace: F.mono, fontSize: 10, color: C.navy });
      tb(s, d, { x: x + 0.24, y: y + 0.37, w: cw - 0.48, h: 0.24, fontSize: 10.5, color: C.muted });
      y += 0.74;
    });
  });

  notes(s, 'Apéndice. Si alguien quiere verificar algo en el momento, está aquí. Todos se ejecutan en local y ninguno necesita credenciales externas salvo la clave del modelo.');
}
