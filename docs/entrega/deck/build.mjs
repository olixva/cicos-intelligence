// Genera docs/entrega/presentacion.pptx.
//
//   NODE_PATH=<ruta a node_modules con pptxgenjs> node docs/entrega/deck/build.mjs
//
// El deck se construye entero por código: cada cifra que aparece en una lámina
// sale de una comprobación ejecutada sobre este repositorio, no de memoria.
import fs from 'node:fs/promises';
import PptxGenJS from 'pptxgenjs';
import { LOG } from './lib.mjs';
import { chapterOne, chapterTwo } from './slides-problema.mjs';
import { chapterThree } from './slides-arquitectura.mjs';
import { chapterFour, chapterFive, appendix } from './slides-evaluacion.mjs';
import { cover, agenda } from './slides-apertura.mjs';

const OUT = new URL('../presentacion.pptx', import.meta.url).pathname;

const pres = new PptxGenJS();
pres.layout = 'LAYOUT_WIDE';           // 13.333 x 7.5 in — fijar antes de añadir láminas
pres.author = 'Antonio Oliva Carceles';
pres.company = 'Prueba técnica GenAI';
pres.title = 'CICOS Claims Intelligence';
pres.subject = 'RAG con evidencia verificable y decisión auditable sobre el manual CIDE/ASCIDE/CICOS';

// Contador de láminas compartido: el chrome lo pinta abajo a la derecha.
const ctx = { n: 0 };

cover(pres, ctx);
agenda(pres, ctx);
chapterOne(pres, ctx);
chapterTwo(pres, ctx);
chapterThree(pres, ctx);
chapterFour(pres, ctx);
chapterFive(pres, ctx);
appendix(pres, ctx);

await pres.writeFile({ fileName: OUT });

// El guion de orador se genera del mismo sitio que las láminas: no puede
// desincronizarse con lo que se proyecta.
const SCRIPT = new URL('../guion-orador.md', import.meta.url).pathname;
const md = [
  '# Guion de orador — Allianz CICOS Claims Intelligence',
  '',
  `Generado por \`docs/entrega/deck/build.mjs\` a partir de las notas de las ${ctx.n} láminas de`,
  '`docs/entrega/presentacion.pptx`. No se edita a mano: se regenera con `npm run build` dentro',
  'de `docs/entrega/deck/`. Los mismos textos están en las notas de orador del `.pptx`.',
  '',
  '**Reparto de los 45 minutos**: 4 min problema · 4 min plan y riesgos · 10 min arquitectura ·',
  '14 min demo en vivo · 5 min evaluación y límites · 8 min preguntas.',
  '',
  '---',
  '',
  ...LOG.flatMap((slide) => [
    `## ${String(slide.n).padStart(2, '0')} · ${slide.title || '(sin título)'}`,
    '',
    slide.eyebrow && slide.eyebrow !== 'Separador' ? `*${slide.eyebrow}*` : '',
    '',
    ...(slide.notes ? slide.notes.split('\n').map((l) => (l.trim() ? l : '')) : ['_Sin notas._']),
    '',
  ]),
].join('\n').replace(/\n{3,}/g, '\n\n');
await fs.writeFile(SCRIPT, `${md}\n`, 'utf8');

console.log(`Escritas ${ctx.n} láminas en ${OUT}`);
console.log(`Guion de orador en ${SCRIPT}`);
