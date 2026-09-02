/**
 * Abrir una cita no puede rasterizar el manual entero.
 *
 * Regresión real: el visor recorría `doc.numPages` (111 en el manual)
 * rasterizando cada página a un canvas ANTES de pintar la primera. El usuario
 * pulsaba una cita y se quedaba mirando un skeleton, con 111 canvas vivos en
 * memoria. Debe abrirse el documento, leer el número de páginas y rasterizar
 * únicamente la que se está mirando.
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import type { EvidenceItem } from '@/api/queries';

const NUM_PAGES = 111;
const renderedPages: number[] = [];

vi.mock('pdfjs-dist', () => {
  const makePage = (pageNumber: number) => ({
    getViewport: () => ({ width: 600, height: 800 }),
    render: () => {
      renderedPages.push(pageNumber);
      return { promise: Promise.resolve() };
    },
  });
  return {
    GlobalWorkerOptions: { workerSrc: '' },
    getDocument: () => ({
      promise: Promise.resolve({
        numPages: NUM_PAGES,
        getPage: (pageNumber: number) => Promise.resolve(makePage(pageNumber)),
      }),
    }),
  };
});

vi.mock('pdfjs-dist/build/pdf.worker.min.mjs?url', () => ({ default: 'worker.mjs' }));

import { PdfOverlay } from '@/components/pdf-overlay/pdf-overlay';

const evidence: EvidenceItem = {
  evidence_id: 'sha256:abc:page:9',
  document_hash: 'abc',
  pdf_page: 9,
  delivery: 'text',
};

describe('PdfOverlay', () => {
  it('rasteriza sólo la página citada, no las 111 del manual', async () => {
    renderedPages.length = 0;
    // jsdom no implementa canvas 2D; sin este stub el visor aborta antes de
    // llegar a pdfjs y el test mediría el fallo equivocado.
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
      {} as unknown as CanvasRenderingContext2D,
    );

    render(
      <PdfOverlay
        open
        onOpenChange={() => {}}
        src="/api/v1/manual/pdf?version=abc"
        evidence={evidence}
        snippet="cita"
      />,
    );

    // El contador de páginas sale del documento, sin rasterizar nada más.
    await waitFor(() => expect(screen.getByText(`9 / ${NUM_PAGES}`)).toBeInTheDocument());

    await waitFor(() => expect(renderedPages.length).toBeGreaterThan(0));
    expect(renderedPages).toEqual([9]);
  });
});
