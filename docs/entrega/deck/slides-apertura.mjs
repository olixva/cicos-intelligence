import {
  W, H, M, CW, RIGHT, C, F, tb, rect, rrect, ell, card, pill, chip, dot, arrow,
  chrome, title, deck, band, notes, page, hline,
} from './lib.mjs';

const LOGO = new URL('./assets/allianz-logo.png', import.meta.url).pathname;

export function cover(pres, ctx) {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  ctx.n += 1;

  // Motivo de portada: dos círculos concéntricos desplazados fuera del lienzo.
  ell(s, { x: 8.9, y: -1.9, w: 6.6, h: 6.6, fill: { color: C.deep } });
  ell(s, { x: 10.2, y: 0.4, w: 4.3, h: 4.3, fill: { color: '0A4E92' } });
  ell(s, { x: 11.1, y: 2.0, w: 2.4, h: 2.4, fill: { color: C.blue } });

  rrect(s, { x: M, y: 0.62, w: 2.28, h: 0.66, rectRadius: 0.1, fill: { color: C.paper } });
  s.addImage({ path: LOGO, x: M + 0.24, y: 0.83, w: 1.8, h: 0.24, sizing: { type: 'contain', w: 1.8, h: 0.24 } });

  tb(s, 'CICOS Claims\nIntelligence', {
    x: M, y: 2.05, w: 8.4, h: 1.9, fontFace: F.head, fontSize: 47, bold: true,
    color: C.paper, lineSpacingMultiple: 1.0,
  });
  tb(s, 'RAG con evidencia verificable y decisión auditable\nsobre el manual CIDE · ASCIDE · CICOS', {
    x: M, y: 4.06, w: 7.6, h: 0.86, fontSize: 16.5, color: C.pale, lineSpacingMultiple: 1.16,
  });

  const stats = [
    ['111', 'páginas indexadas'],
    ['110', 'casos golden'],
    ['14', 'reglas firmadas'],
    ['597', 'pruebas verdes'],
  ];
  stats.forEach(([v, l], i) => {
    const x = M + i * 2.06;
    tb(s, v, { x, y: 5.28, w: 1.9, h: 0.6, fontFace: F.head, fontSize: 33, bold: true, color: C.sky });
    tb(s, l, { x, y: 5.88, w: 1.9, h: 0.4, fontSize: 11.5, color: C.pale });
  });

  tb(s, 'Antonio Oliva Carceles   ·   Prueba técnica GenAI   ·   Septiembre 2026', {
    x: M, y: 6.72, w: 9, h: 0.3, fontSize: 12, color: '8FB8DC',
  });

  notes(s, [
    'APERTURA (30 s). No leer la portada.',
    '',
    'Frase de entrada sugerida:',
    '«El enunciado pedía un RAG sobre el manual del Convenio. Lo que me encontré al leer los cinco',
    'accidentes de ejemplo es que cuatro de ellos no tienen una respuesta determinista — y que un',
    'sistema que los resolviera los cinco estaría inventando cuatro. Todo lo que voy a enseñar sale',
    'de esa observación.»',
    '',
    'Las cuatro cifras están verificadas hoy contra el repositorio: 111 páginas del manual publicadas,',
    '110 casos en el golden de desarrollo, 14 reglas en el ruleset firmado, 500 pruebas de backend',
    '+ 97 de frontend = 597.',
  ].join('\n'));
}

export function agenda(pres, ctx) {
  const s = page(pres, ctx, { eyebrow: 'Recorrido' });
  title(s, 'Cuarenta y cinco minutos: veinte de diseño, quince de demo en vivo, diez de preguntas.');
  deck(s, 'La narración va de por qué este problema es más difícil de lo que parece, a cómo se demuestra que el sistema no improvisa.');

  const rows = [
    ['01', 'El problema', 'Qué pide el enunciado y por qué cuatro de sus cinco accidentes no tienen respuesta determinista.', '4 min'],
    ['02', 'Plan, supuestos y riesgos', 'Cinco días con hitos comprobables, seis supuestos declarados y las decisiones técnicas con su porqué.', '4 min'],
    ['03', 'Arquitectura', 'Hexagonal, ingesta con cadena de custodia, recuperación híbrida, workflows y motor de reglas.', '9 min'],
    ['04', 'Demo en vivo', 'Cuatro recorridos sobre el sistema real: enrutado, caso resuelto, abstención y trazabilidad.', '15 min'],
    ['05', 'Evaluación y límites', 'Golden set de 110 casos, protocolo de medida, lo que el sistema no hace y la siguiente iteración.', '5 min'],
    ['06', 'Preguntas', 'Con el código, el manual, las trazas y el estado verificado delante.', '8 min'],
  ];

  let y = 2.46;
  rows.forEach(([n, name, desc, time], i) => {
    const h = 0.62;
    if (i % 2 === 0) rrect(s, { x: M, y: y - 0.04, w: CW, h: h + 0.08, fill: { color: C.ice } });
    chip(s, n, { x: M + 0.22, y: y + 0.04, d: 0.42, fill: i === 3 ? C.teal : C.navy, size: 12 });
    tb(s, name, { x: M + 0.84, y: y + 0.04, w: 2.7, h: 0.3, fontFace: F.head, fontSize: 14.5, bold: true, color: C.ink });
    tb(s, desc, { x: M + 3.6, y: y + 0.05, w: 7.0, h: 0.5, fontSize: 12, color: C.muted, lineSpacingMultiple: 1.0 });
    pill(s, time, { x: RIGHT - 1.02, y: y + 0.09, w: 0.92, h: 0.3, fill: i === 3 ? C.tealSoft : C.band, color: i === 3 ? C.teal : C.navy, size: 10.5 });
    y += 0.69;
  });

  band(s, 'La demo ocupa un tercio del tiempo a propósito: lo que hay que creerse no son las láminas, es el sistema corriendo.', { tone: 'navy' });

  notes(s, [
    'AGENDA (40 s).',
    '',
    'Marcar dos cosas y pasar:',
    '1) El bloque más largo es la demo. Es deliberado.',
    '2) El bloque 05 incluye una lámina de límites: lo que el sistema NO hace se cuenta aquí,',
    '   no en la letra pequeña ni cuando alguien lo pregunte.',
    '',
    'Si el tiempo aprieta: los bloques 01 y 02 se pueden comprimir a 5 min entre los dos;',
    'nunca recortar la demo ni la lámina de límites.',
  ].join('\n'));
}
