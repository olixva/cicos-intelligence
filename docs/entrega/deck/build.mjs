// Genera docs/entrega/presentacion.pptx.
//
//   NODE_PATH=<ruta a node_modules con pptxgenjs> node docs/entrega/deck/build.mjs
//
// El deck se construye entero por código: cada cifra que aparece en una lámina
// sale de una comprobación ejecutada sobre este repositorio, no de memoria.
import PptxGenJS from 'pptxgenjs';
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
console.log(`Escritas ${ctx.n} láminas en ${OUT}`);
