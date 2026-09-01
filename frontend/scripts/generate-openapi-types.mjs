#!/usr/bin/env node
// generate-openapi-types.mjs
//
// Genera `src/types/api.gen.ts` desde `docs/api/openapi.json` usando
// openapi-typescript. Node puro (.mjs) para evitar el bootstrap de TS en
// el script.
//
// Variables de entorno:
//   OPENAPI_JSON_PATH  Ruta al openapi.json (absoluta o relativa a este
//                      directorio). Default: `../../docs/api/openapi.json`.
//   OPENAPI_TS_PATH    Ruta destino del .ts. Default: `src/types/api.gen.ts`.
//
// Flags CLI:
//   --check            Si el archivo destino existe y no está vacío, lo
//                      regenera y compara. Sale con código 1 si hay diff.
//                      Pensado para CI / pre-commit.

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import openapiTS, { astToString } from 'openapi-typescript';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const FRONTEND_ROOT = resolve(__dirname, '..');
const REPO_ROOT = resolve(FRONTEND_ROOT, '..');

const args = new Set(process.argv.slice(2));
const CHECK_MODE = args.has('--check');

const OPENAPI_JSON_PATH = resolve(
  REPO_ROOT,
  process.env.OPENAPI_JSON_PATH ?? 'docs/api/openapi.json',
);
const OPENAPI_TS_PATH = resolve(
  FRONTEND_ROOT,
  process.env.OPENAPI_TS_PATH ?? 'src/types/api.gen.ts',
);

function log(level, msg) {
  const stamp = new Date().toISOString();
  console[level](`[openapi:gen ${stamp}] ${msg}`);
}

function readOpenAPI() {
  if (!existsSync(OPENAPI_JSON_PATH)) {
    log('error', `openapi.json no encontrado en ${OPENAPI_JSON_PATH}`);
    process.exit(2);
  }
  const raw = readFileSync(OPENAPI_JSON_PATH, 'utf8');
  try {
    return JSON.parse(raw);
  } catch (err) {
    log('error', `openapi.json no es JSON válido: ${err.message}`);
    process.exit(2);
  }
}

async function generate() {
  const schema = readOpenAPI();
  log('info', `leyendo openapi.json desde ${OPENAPI_JSON_PATH}`);

  const ast = await openapiTS(schema, {
    // Genera tipos readonly inmutables (más estricto, mejor para runtime).
    immutableTypes: true,
    // Genera `additionalProperties: false` como `{}` exacto.
    emptyObjectsUnknown: false,
    // Encadenamiento de comments JSDoc para mejor DX.
    additionalProperties: false,
  });

  const generated = astToString(ast);

  // Cabecera informativa — git blame te dirá cuándo se regeneró por última vez.
  const header = `// ⚠️  AUTO-GENERATED FILE — DO NOT EDIT.
// Regenerado por scripts/generate-openapi-types.mjs desde ${relative(
    FRONTEND_ROOT,
    OPENAPI_JSON_PATH,
  )}.
// Para regenerar: pnpm openapi:gen   ·   Para verificar en CI: pnpm openapi:check

`;

  return header + generated + '\n';
}

async function run() {
  const previous = existsSync(OPENAPI_TS_PATH)
    ? readFileSync(OPENAPI_TS_PATH, 'utf8')
    : null;

  const next = await generate();

  if (CHECK_MODE) {
    if (previous === null) {
      log('error', `destino inexistente: ${OPENAPI_TS_PATH}. Ejecuta primero pnpm openapi:gen.`);
      process.exit(1);
    }
    if (previous === next) {
      log('info', `openapi:check OK — sin drift (${OPENAPI_TS_PATH})`);
      process.exit(0);
    }
    log('error', `openapi:check FAIL — drift detectado. Regenera con pnpm openapi:gen.`);
    // Imprime la primera línea distinta para facilitar la diagnosis.
    const aLines = previous.split('\n');
    const bLines = next.split('\n');
    for (let i = 0; i < Math.min(aLines.length, bLines.length); i++) {
      if (aLines[i] !== bLines[i]) {
        log(
          'error',
          `primera diferencia en línea ${i + 1}: "${aLines[i].slice(0, 80)}" → "${bLines[i].slice(0, 80)}"`,
        );
        break;
      }
    }
    process.exit(1);
  }

  writeFileSync(OPENAPI_TS_PATH, next, 'utf8');
  log('info', `escrito ${OPENAPI_TS_PATH} (${next.length} bytes)`);
}

run().catch((err) => {
  log('error', `generación abortada: ${err?.stack ?? err}`);
  process.exit(2);
});
