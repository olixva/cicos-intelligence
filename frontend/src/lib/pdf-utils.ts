/**
 * pdf-utils — utilidades puras para proyección regions → viewport.
 *
 * Decisión D4: cuando `evidence.regions` está vacío, devolvemos un único
 * rectángulo que cubre toda la página. El componente `pdf-overlay` aplica
 * la overlay `#00378133` sobre el canvas en ese caso y emite
 * `console.warn('[pdf-overlay] evidence sin regiones, resaltando página completa', ...)`.
 *
 * Las regiones que llegan del backend están en coordenadas **viewport**
 * (origen arriba-izquierda, unidades en píxeles del PDF renderizado a la
 * escala nativa — `viewport.width`/`viewport.height`). pdfjs-dist nos da
 * el viewport directamente, así que no hay conversión adicional: las
 * coordenadas de la región coinciden con coordenadas CSS en pixeles
 * absolutos dentro del contenedor del canvas.
 *
 * Si en el futuro el backend pasa coords en otro sistema (fracciones 0..1,
 * coords del MediaBox sin escalar), se añade aquí la conversión y los
 * tests cubren ambos paths.
 */

export interface PdfRegion {
  /** 0-indexed page number — pdfjs uses 1-indexed for getPage(n), cuidado. */
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface NormalizedRegion {
  pageIndex: number; // 0-indexed
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Heurística: ¿parece que la región ya está en coords de viewport? */
function looksLikeViewportCoords(
  regions: ReadonlyArray<{ x: number; y: number; width: number; height: number }>,
  pageWidth: number,
  pageHeight: number,
): boolean {
  if (regions.length === 0) return true;
  return regions.every(
    (r) =>
      r.x >= 0 &&
      r.y >= 0 &&
      r.x + r.width <= pageWidth + 1 &&
      r.y + r.height <= pageHeight + 1,
  );
}

/** Normaliza regiones: convierte page 1-indexed → 0-indexed y valida coords. */
export function normalizeRegions(
  regions: ReadonlyArray<PdfRegion>,
  pageWidth: number,
  pageHeight: number,
): NormalizedRegion[] {
  if (!regions || regions.length === 0) return [];
  const valid = looksLikeViewportCoords(regions, pageWidth, pageHeight);
  return regions
    .map((r) => ({
      pageIndex: Math.max(0, r.page - 1),
      x: r.x,
      y: r.y,
      width: r.width,
      height: r.height,
    }))
    .filter(
      (r) =>
        valid &&
        r.x >= 0 &&
        r.y >= 0 &&
        r.x + r.width <= pageWidth + 1 &&
        r.y + r.height <= pageHeight + 1,
    );
}

/** Resalta la página completa: rectángulo que cubre el viewport entero. */
export function fullPageFallback(pageWidth: number, pageHeight: number): NormalizedRegion {
  return { pageIndex: 0, x: 0, y: 0, width: pageWidth, height: pageHeight };
}
