import { chromium } from '@playwright/test';

const url = process.env.SCREEN_URL ?? 'http://127.0.0.1:5173/';
const outDir = process.env.SCREEN_DIR ?? '/tmp/allianz-screens';

async function main() {
  const browser = await chromium.launch({ channel: 'chrome' });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  // 1) Empty state.
  console.log('Navigating to', url);
  await page.goto(url, { waitUntil: 'networkidle', timeout: 30_000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${outDir}/01-empty-state.png`, fullPage: false });
  console.log('Saved 01-empty-state.png');

  // 2) Type into composer and capture thread with user message + tool call cards.
  const textarea = page.getByLabel(/texto de la consulta/i);
  await textarea.fill(
    'Vehículo A gira a la izquierda en un cruce con semáforo en ámbar y es embestido por el vehículo B que circulaba en sentido contrario. ¿Convenio aplicable?',
  );
  await page.waitForTimeout(400);

  // Click "Siniestro" mode to test the claim flow tool calls.
  await page.locator('label[for="composer-mode-claim"]').click();
  await page.waitForTimeout(400);

  // Click Enviar.
  await page.getByRole('button', { name: /enviar consulta/i }).click();

  // Wait for tool call cards to appear.
  await page.waitForSelector('[role="article"][data-role="assistant"]', { timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${outDir}/02-tool-calls-pending.png`, fullPage: false });
  console.log('Saved 02-tool-calls-pending.png');

  // Wait for the failure/error state since backend is not running.
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${outDir}/03-thread-final.png`, fullPage: false });
  console.log('Saved 03-thread-final.png');

  // 4) Sidebar expanded.
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(800);
  // Expand sidebar via the chevron button.
  const expandBtn = page.getByRole('button', { name: /expandir sidebar/i }).first();
  if (await expandBtn.count()) {
    await expandBtn.click();
    await page.waitForTimeout(800);
  }
  await page.screenshot({ path: `${outDir}/04-sidebar-expanded.png`, fullPage: false });
  console.log('Saved 04-sidebar-expanded.png');

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
