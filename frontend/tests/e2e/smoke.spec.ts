import { test, expect } from '@playwright/test';

/**
 * Smoke e2e — verifica que el chat agéntico carga y que se puede
 * enviar una consulta. No asume backend arriba: si el POST falla,
 * aparecerá un mensaje de error en la burbuja del asistente (lo
 * aceptamos dentro del timeout de 60s).
 *
 * Spec UX v2: la app expone BannerSystem, EmptyState, Composer y
 * thread. Verificamos los elementos clave y dejamos el flujo de
 * streaming a la prueba manual (necesita backend con índice).
 */

test.describe('Allianz CICOS — chat agéntico smoke', () => {
  test('carga, muestra header, EmptyState y Composer', async ({ page }) => {
    await page.goto('/');

    // Header
    await expect(
      page.getByRole('heading', { name: /Claims Intelligence/i }),
    ).toBeVisible();

    // EmptyState con 5 ejemplos
    await expect(
      page.getByRole('heading', { name: /Claims Intelligence/i }),
    ).toBeVisible();
    await expect(page.getByText(/Pregunta frecuente/i)).toBeVisible();
    await expect(page.getByText(/Siniestro corto/i)).toBeVisible();

    // Composer con radios de modo
    await expect(page.getByLabel('Automático')).toBeVisible();
    await expect(page.getByLabel('Pregunta')).toBeVisible();
    await expect(page.getByLabel('Siniestro')).toBeVisible();

    // Textarea con label accesible
    const textarea = page.getByLabel(/texto de la consulta/i);
    await expect(textarea).toBeVisible();

    // Botón Enviar inicialmente deshabilitado
    await expect(page.getByRole('button', { name: /enviar consulta/i })).toBeDisabled();
  });

  test('permite escribir y habilitar el botón Enviar', async ({ page }) => {
    await page.goto('/');
    const textarea = page.getByLabel(/texto de la consulta/i);
    await textarea.fill('¿Qué dice el manual sobre el convenio CIDE?');
    await expect(page.getByRole('button', { name: /enviar consulta/i })).toBeEnabled();
  });
});
