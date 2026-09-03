import { test, expect } from '@playwright/test';

/**
 * Smoke e2e — verifica que el chat carga con sus elementos clave y que el
 * composer se habilita al escribir.
 *
 * Requiere el backend en marcha: las tarjetas de sugerencia salen de
 * `GET /api/v1/demo/cases`. El flujo de streaming completo queda fuera de
 * este smoke.
 *
 * Las aserciones sobre las sugerencias van contra el contrato de la
 * interfaz (hay tarjetas y son clickables), no contra los identificadores
 * concretos de los casos: la selección curada es contenido y cambia.
 */

test.describe('Allianz CICOS — chat agéntico smoke', () => {
  test('carga, muestra header, EmptyState y Composer', async ({ page }) => {
    await page.goto('/');

    // Header — scoped al banner para evitar la ambigüedad con el
    // heading del EmptyState que reusa el mismo texto accesible.
    const banner = page.getByRole('banner');
    await expect(
      banner.getByRole('heading', { name: /Claims Intelligence/i }),
    ).toBeVisible();

    // EmptyState con sugerencias: heading propio + ejemplos
    await expect(
      page.getByLabel('Sugerencias').getByRole('heading', {
        name: /Claims Intelligence/i,
      }),
    ).toBeVisible();
    const suggestions = page.getByLabel('Sugerencias').getByRole('button', {
      name: /Probar ejemplo:/i,
    });
    await expect(suggestions.first()).toBeVisible();
    expect(await suggestions.count()).toBeGreaterThan(0);

    // Composer con radios de modo — el fieldset expone su nombre
    // accesible, evitamos así ambigüedad con textos repetidos.
    const modeFieldset = page.getByRole('group', { name: 'Modo de consulta' });
    await expect(
      modeFieldset.getByRole('radio', { name: /Automático/i }),
    ).toBeVisible();
    await expect(
      modeFieldset.getByRole('radio', { name: /Pregunta/i }),
    ).toBeVisible();
    await expect(
      modeFieldset.getByRole('radio', { name: /Siniestro/i }),
    ).toBeVisible();

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
