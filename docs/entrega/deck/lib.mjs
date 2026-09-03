// Sistema de diseño del deck de entrega — Allianz CICOS Claims Intelligence.
// Nada aquí conoce el contenido: sólo la retícula, la paleta y los componentes.

export const W = 13.333;
export const H = 7.5;
export const M = 0.62;              // margen lateral
export const CW = W - 2 * M;        // ancho útil: 12.093
export const RIGHT = W - M;

export const C = {
  navy: '003781',   // azul Allianz, color dominante
  deep: '002A5E',
  blue: '0079C1',
  sky: '5AB6E8',
  pale: 'C9DEF2',
  ice: 'F1F6FC',
  band: 'E6F0F9',
  paper: 'FFFFFF',
  ink: '0B1F3A',
  muted: '5D7189',
  soft: '8296AC',
  line: 'D9E4F0',
  darkCard: '0A3E7A',
  darkLine: '2D639F',
  teal: '00807E',
  tealSoft: 'E2F3F2',
  amber: 'A9711A',
  amberSoft: 'FBF1DF',
  rust: 'A63F38',
  rustSoft: 'FAEDEC',
};

export const F = { head: 'Arial', body: 'Calibri', mono: 'Courier New' };

const LOGO = new URL('./assets/allianz-logo.png', import.meta.url).pathname;

export function softShadow() {
  // pptxgenjs muta los objetos de opciones: hay que devolver uno nuevo en cada uso.
  return { type: 'outer', color: '99AEC6', blur: 7, offset: 1.5, angle: 90, opacity: 0.28 };
}

/* ---------------------------------------------------------------- primitivas */

export function tb(s, text, o) {
  s.addText(text, {
    isTextBox: true, margin: 0, fontFace: F.body, fontSize: 13.5,
    color: C.ink, valign: 'top', ...o,
  });
}

// pptxgenjs escribe un borde gris por defecto si se le pasa `line` con width 0:
// la única forma de no tener borde es no pasar `line` en absoluto.
export function rect(s, o) { s.addShape('rect', { ...o }); }

export function rrect(s, o) { s.addShape('roundRect', { rectRadius: 0.09, ...o }); }

export function ell(s, o) { s.addShape('ellipse', { ...o }); }

export function hline(s, x, y, w, color = C.line, width = 1) {
  s.addShape('line', { x, y, w, h: 0, line: { color, width } });
}

/* --------------------------------------------------------------- componentes */

// Tarjeta: fondo propio y sombra suave. Sin franjas de color en los bordes.
export function card(s, { x, y, w, h, dark = false, fill, radius = 0.1 }) {
  rrect(s, {
    x, y, w, h, rectRadius: radius,
    fill: { color: fill || (dark ? C.darkCard : C.paper) },
    line: { color: dark ? C.darkLine : C.line, width: 1 },
    ...(dark ? {} : { shadow: softShadow() }),
  });
}

// Píldora de evidencia: el motivo que se repite en todo el deck.
export function pill(s, text, { x, y, w, h = 0.3, fill = C.band, color = C.navy, size = 10.5, mono = true, align = 'center' }) {
  rrect(s, { x, y, w, h, rectRadius: h / 2, fill: { color: fill } });
  tb(s, text, {
    x, y: y + (h - 0.2) / 2 - 0.02, w, h: 0.24, align,
    fontFace: mono ? F.mono : F.body, fontSize: size, color, bold: !mono,
  });
}

// Chip numerado: el segundo elemento del motivo.
export function chip(s, n, { x, y, d = 0.42, fill = C.navy, color = C.paper, size = 13 }) {
  ell(s, { x, y, w: d, h: d, fill: { color: fill } });
  tb(s, String(n), {
    x, y: y + d / 2 - 0.13, w: d, h: 0.26, align: 'center',
    fontFace: F.head, fontSize: size, bold: true, color,
  });
}

export function dot(s, { x, y, d = 0.13, color }) {
  ell(s, { x, y, w: d, h: d, fill: { color } });
}

export function arrow(s, { x, y, w = 0.3, color = C.blue, size = 16 }) {
  tb(s, '›', { x, y, w, h: 0.3, align: 'center', fontFace: F.head, fontSize: size, bold: true, color });
}

/* ------------------------------------------------------------------- chrome */

export function chrome(s, { eyebrow, num, dark = false, logo = true }) {
  if (eyebrow) {
    tb(s, eyebrow.toUpperCase(), {
      x: M, y: 0.38, w: 8, h: 0.24,
      fontFace: F.head, fontSize: 10.5, bold: true, charSpacing: 1.6,
      color: dark ? C.sky : C.blue,
    });
  }
  if (logo) {
    if (dark) {
      rrect(s, { x: RIGHT - 1.52, y: 0.28, w: 1.52, h: 0.42, rectRadius: 0.08, fill: { color: C.paper } });
      s.addImage({ path: LOGO, x: RIGHT - 1.40, y: 0.36, w: 1.28, h: 0.26, sizing: { type: 'contain', w: 1.28, h: 0.26 } });
    } else {
      s.addImage({ path: LOGO, x: RIGHT - 1.35, y: 0.36, w: 1.35, h: 0.27, sizing: { type: 'contain', w: 1.35, h: 0.27 } });
    }
  }
  if (num != null) {
    tb(s, String(num).padStart(2, '0'), {
      x: RIGHT - 0.6, y: 7.02, w: 0.6, h: 0.24, align: 'right',
      fontFace: F.head, fontSize: 9.5, bold: true, color: dark ? C.darkLine : C.soft,
    });
  }
}

// Título de acción: una frase completa que dice la conclusión, no el tema.
export function title(s, text, { dark = false, y = 0.88, size = 26, w = 11.1 } = {}) {
  tb(s, text, {
    x: M, y, w, h: 0.9, fontFace: F.head, fontSize: size, bold: true,
    color: dark ? C.paper : C.ink, lineSpacingMultiple: 1.02,
  });
}

export function deck(s, text, { dark = false, y = 1.90, w = 11.5, size = 13.5 } = {}) {
  tb(s, text, {
    x: M, y, w, h: 0.52, fontSize: size,
    color: dark ? C.pale : C.muted, lineSpacingMultiple: 1.08,
  });
}

// Banda inferior: el "so what" de la lámina. Nunca decorativa.
export function band(s, text, { y = 6.40, tone = 'navy', h = 0.54 } = {}) {
  const tones = {
    navy: [C.navy, C.paper], ice: [C.band, C.navy], amber: [C.amberSoft, C.amber],
    teal: [C.tealSoft, C.teal], rust: [C.rustSoft, C.rust], dark: [C.darkCard, C.pale],
  };
  const [bg, fg] = tones[tone];
  rrect(s, { x: M, y, w: CW, h, fill: { color: bg } });
  tb(s, text, {
    x: M + 0.3, y: y + (h - 0.34) / 2, w: CW - 0.6, h: 0.36, align: 'center',
    fontSize: 12.5, bold: true, color: fg, lineSpacingMultiple: 0.95,
  });
}

export function notes(s, text) { s.addNotes(text); }

// Crea la lámina, pinta el fondo y el chrome, y devuelve el objeto slide.
// `decor` pinta el fondo decorativo ANTES del chrome, para que nunca tape el logo.
export function page(pres, ctx, { eyebrow, dark = false, logo = true, bg, decor } = {}) {
  const s = pres.addSlide();
  s.background = { color: bg || (dark ? C.navy : C.paper) };
  if (decor) decor(s);
  chrome(s, { eyebrow, num: ++ctx.n, dark, logo });
  return s;
}

// Los cinco bloques de la narración, para el raíl de progreso de los separadores.
export const CHAPTERS = [
  ['01', 'El problema'], ['02', 'Plan y riesgos'], ['03', 'Arquitectura'],
  ['04', 'Demo en vivo'], ['05', 'Evaluación y límites'],
];

// Lámina de capítulo: pausa deliberada entre bloques, con el mapa de dónde estamos.
export function divider(pres, ctx, { num, name, promise, shot }) {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  if (shot) {
    // Un adelanto real del producto pesa más que la geometría decorativa.
    const iw = 5.5, ih = iw / 1.609, ix = RIGHT - iw, iy = 1.6;
    rrect(s, { x: ix - 0.06, y: iy - 0.06, w: iw + 0.12, h: ih + 0.12, rectRadius: 0.08, fill: { color: C.darkLine } });
    s.addImage({ path: shot, x: ix, y: iy, w: iw, h: ih });
  } else {
    ell(s, { x: 10.4, y: -1.5, w: 5.2, h: 5.2, fill: { color: C.deep } });
    ell(s, { x: 11.6, y: 3.6, w: 3.4, h: 3.4, fill: { color: '063E82' } });
  }
  chrome(s, { num: ++ctx.n, dark: true });

  const tw = shot ? 4.8 : 8.6;
  tb(s, num, {
    x: M, y: 2.32, w: 2.4, h: 1.5, fontFace: F.head, fontSize: 92, bold: true, color: C.darkLine,
  });
  tb(s, name, {
    x: M + 1.9, y: 2.58, w: tw, h: 0.8, fontFace: F.head, fontSize: 36, bold: true, color: C.paper,
  });
  tb(s, promise, {
    x: M + 1.9, y: 3.54, w: shot ? 4.6 : 8.2, h: 1.4, fontSize: 15, color: C.pale, lineSpacingMultiple: 1.12,
  });

  // Raíl de progreso: dónde estamos dentro de los cinco bloques.
  const w = CW / CHAPTERS.length;
  CHAPTERS.forEach(([n, label], i) => {
    const here = n === num;
    const x = M + i * w;
    rrect(s, {
      x, y: 5.94, w: w - 0.16, h: 0.62, rectRadius: 0.09,
      fill: { color: here ? C.darkCard : C.deep },
    });
    tb(s, n, {
      x: x + 0.24, y: 6.06, w: 0.5, h: 0.24,
      fontFace: F.head, fontSize: 11, bold: true, color: here ? C.sky : C.darkLine,
    });
    tb(s, label, {
      x: x + 0.74, y: 6.06, w: w - 1.0, h: 0.36,
      fontSize: 11.5, bold: here, color: here ? C.paper : C.darkLine, lineSpacingMultiple: 0.98,
    });
  });
  return s;
}
