import { test, expect } from '@playwright/test';

/**
 * Smoke e2e — verifica que la app carga, que el ModeSelector aparece y que
 * el textarea acepta texto. No asume backend arriba: el envío generará un
 * error de red visible en el EnvelopeRenderer (lo aceptamos dentro del
 * timeout de 60s).
 */

test.describe('Allianz CICOS — smoke', () => {
  test('carga, muestra ModeSelector y permite escribir en el textarea', async ({ page }) => {
    await page.goto('/');

    // El título de la app debe estar visible.
    await expect(page.getByRole('heading', { name: /Claims Intelligence/i })).toBeVisible();

    // El ModeSelector renderiza los 3 radios con label accesible.
    await expect(page.getByLabel('Automático')).toBeVisible();
    await expect(page.getByLabel('Pregunta')).toBeVisible();
    await expect(page.getByLabel('Siniestro')).toBeVisible();

    // El textarea con el label oculto está presente.
    const textarea = page.getByLabel(/texto de la consulta/i);
    await textarea.fill('¿Qué dice el manual sobre el convenio CIDE?');

    // El botón Enviar debe estar habilitado.
    await expect(page.getByRole('button', { name: /enviar consulta/i })).toBeEnabled();
  });
});
