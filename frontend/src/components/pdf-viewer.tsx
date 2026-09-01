import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, X, FileWarning } from 'lucide-react';
// pdfjs-dist — el worker se importa con `?url` para que Vite lo empaquete
// correctamente en build y lo sirva como asset. La asignación a
// GlobalWorkerOptions.workerSrc debe ocurrir ANTES de cualquier `getDocument`.
import * as pdfjsLib from 'pdfjs-dist';
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useEvidence } from '@/features/evidence/evidence-context';
import {
  fullPageFallback,
  normalizeRegions,
  type PdfRegion,
} from '@/features/pdf-viewer/pdf-utils';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;

interface RenderedPage {
  pageIndex: number;
  width: number;
  height: number;
  canvas: HTMLCanvasElement;
}

type RegionWithFallback = PdfRegion;

/**
 * PdfViewer — visor de evidencia abierta.
 *
 * Decisión D4: si `evidence.regions` está vacío, emitimos console.warn y
 * renderizamos un overlay tenue sobre toda la página (full-page fallback).
 * En este scaffold MVP no recibimos regiones del backend en el envelope;
 * el chip abre la página y, cuando lleguen, se proyectarán aquí.
 */
export interface PdfViewerProps {
  /** URL del PDF. En dev podría ser `/api/v1/manual/pdf` con auth via proxy. */
  src: string;
}

export function PdfViewer({ src }: PdfViewerProps) {
  const { open, closeEvidence } = useEvidence();
  const [pages, setPages] = useState<RenderedPage[]>([]);
  const [activePage, setActivePage] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Carga del PDF al cambiar src o al abrir evidencia por primera vez.
  useEffect(() => {
    let cancelled = false;
    const task = pdfjsLib.getDocument(src);

    setLoading(true);
    setError(null);

    task.promise
      .then(async (doc) => {
        if (cancelled) return;
        const total = doc.numPages;
        const rendered: RenderedPage[] = [];
        for (let i = 1; i <= total; i++) {
          const page = await doc.getPage(i);
          const viewport = page.getViewport({ scale: 1.4 });
          const canvas = document.createElement('canvas');
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          const ctx = canvas.getContext('2d');
          if (!ctx) throw new Error('Canvas 2D context no disponible');
          // pdfjs-dist 4.x: `render` no acepta `canvas` (solo canvasContext + viewport).
          await page.render({ canvasContext: ctx, viewport }).promise;
          rendered.push({
            pageIndex: i - 1,
            width: viewport.width,
            height: viewport.height,
            canvas,
          });
        }
        if (!cancelled) setPages(rendered);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      task.destroy();
    };
  }, [src]);

  // Cuando el evidence abierto cambia, saltamos a su página.
  useEffect(() => {
    if (open?.item && open.item.pdf_page) {
      setActivePage(Math.max(0, open.item.pdf_page - 1));
    }
  }, [open?.item]);

  const currentPage = pages[activePage];

  // Calculamos regiones a resaltar: si no hay, fallback a página completa.
  // D4: el aviso se emite una vez por evidenceId.
  const highlights = useMemo(() => {
    if (!currentPage || !open?.item) return [];
    // El envelope actual no expone regions todavía; cuando el backend las
    // emita, se mapearán aquí. Mientras tanto: fallback de página completa
    // para hacer visible la evidencia.
    const emptyRegions: RegionWithFallback[] = [];
    if (emptyRegions.length === 0) {
      // Decisión D4: console.warn explícito cuando no hay regiones.
      // Permitimos el warning aunque la regla lo desaconseje.
      console.warn(
        '[pdf-viewer] evidence sin regiones, resaltando página completa',
        open.item.evidence_id,
      );
      return [fullPageFallback(currentPage.width, currentPage.height)];
    }
    return normalizeRegions(
      emptyRegions,
      currentPage.width,
      currentPage.height,
    );
  }, [currentPage, open?.item]);

  if (!open?.item) return null;

  return (
    <section
      ref={containerRef}
      aria-label={`Visor de evidencia ${open.item.evidence_id}`}
      className="flex flex-col gap-3 rounded-md border bg-card p-3"
    >
      <header className="flex items-center justify-between gap-2">
        <div className="flex flex-col">
          <span className="text-xs font-mono text-muted-foreground">{open.item.evidence_id}</span>
          <span className="text-xs text-muted-foreground">Página {open.item.pdf_page}</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setActivePage((p) => Math.max(0, p - 1))}
            disabled={activePage === 0}
            aria-label="Página anterior"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-xs tabular-nums text-muted-foreground">
            {activePage + 1} / {pages.length || '—'}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setActivePage((p) => Math.min(pages.length - 1, p + 1))}
            disabled={activePage >= pages.length - 1}
            aria-label="Página siguiente"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={closeEvidence}
            aria-label="Cerrar visor"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </header>

      {open.snippet && (
        <blockquote className="rounded-md border-l-2 border-primary bg-muted/50 p-2 text-xs italic">
          {open.snippet.slice(0, 280)}
          {open.snippet.length > 280 ? '…' : ''}
        </blockquote>
      )}

      <div className="relative overflow-auto rounded-md border bg-background" style={{ maxHeight: 600 }}>
        {loading && (
          <div className="flex h-64 items-center justify-center">
            <Skeleton className="h-40 w-3/4" />
          </div>
        )}
        {error && (
          <div className="flex h-40 flex-col items-center justify-center gap-2 text-destructive">
            <FileWarning className="h-6 w-6" />
            <span className="text-xs">{error}</span>
          </div>
        )}
        {currentPage && !loading && !error && (
          <div
            className="relative mx-auto"
            style={{ width: currentPage.width, height: currentPage.height }}
          >
            {/* Re-mounting the canvas via ref avoids layout thrash. */}
            <PageCanvas page={currentPage} />
            {highlights.map((region, i) => (
              <div
                key={i}
                className="pdf-highlight-fullpage pointer-events-none absolute"
                style={{
                  left: region.x,
                  top: region.y,
                  width: region.width,
                  height: region.height,
                }}
                aria-hidden="true"
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function PageCanvas({ page }: { page: RenderedPage }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.replaceChildren(page.canvas);
    return () => {
      el.replaceChildren();
    };
  }, [page]);
  return <div ref={ref} />;
}
