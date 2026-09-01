import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, ExternalLink, FileWarning, X, Copy } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import type { EvidenceItem } from '@/api/queries';
import { fullPageFallback, normalizeRegions } from '@/lib/pdf-utils';

/**
 * PdfOverlay — modal fullscreen shadcn para mostrar la evidencia.
 *
 * Sustituye al PdfViewer lateral del spec UX v1 (spec UX v2 lo declara
 * modal). Carga pdfjs-dist lazy para evitar inflar el bundle principal
 * (≈1.1MB si se importa arriba). Si `regions` está vacío: fallback a
 * página completa con `console.warn` (decisión D4).
 */
export interface PdfOverlayProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Source del PDF (típicamente `/api/v1/manual/pdf`). */
  src: string;
  /** Evidencia que abrió el modal. */
  evidence: EvidenceItem | null;
  /** Snippet del bloque que pidió la apertura. */
  snippet?: string | null;
}

interface RenderedPage {
  pageIndex: number;
  width: number;
  height: number;
  canvas: HTMLCanvasElement;
}

const MIN_SCALE = 0.6;
const MAX_SCALE = 2.4;

export function PdfOverlay({ open, onOpenChange, src, evidence, snippet }: PdfOverlayProps) {
  const [pages, setPages] = useState<RenderedPage[]>([]);
  const [activePage, setActivePage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scale, setScale] = useState(1.2);
  const [copied, setCopied] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Lazy import de pdfjs-dist: solo entra en el bundle cuando se abre el modal.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const pdfjsLib = await import('pdfjs-dist');
        const workerSrcMod = (await import(
          /* @vite-ignore */ 'pdfjs-dist/build/pdf.worker.min.mjs?url'
        )) as { default: string };
        if (!cancelled) {
          pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrcMod.default;
        }
        const task = pdfjsLib.getDocument(src);
        const doc = await task.promise;
        if (cancelled) return;
        const rendered: RenderedPage[] = [];
        for (let i = 1; i <= doc.numPages; i++) {
          const page = await doc.getPage(i);
          const viewport = page.getViewport({ scale: 1.4 });
          const canvas = document.createElement('canvas');
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          const ctx = canvas.getContext('2d');
          if (!ctx) throw new Error('Canvas 2D context no disponible');
          await page.render({ canvasContext: ctx, viewport }).promise;
          rendered.push({
            pageIndex: i - 1,
            width: viewport.width,
            height: viewport.height,
            canvas,
          });
        }
        if (!cancelled) setPages(rendered);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [open, src]);

  // Cuando cambia la evidencia (o se abre), saltar a su página.
  useEffect(() => {
    if (evidence?.pdf_page) {
      setActivePage(Math.max(0, evidence.pdf_page - 1));
    }
  }, [evidence]);

  const currentPage = pages[activePage];

  // Decisión D4: regions del envelope cuando llegan; si no, fallback.
  // Como el envelope actual todavía no expone `regions` por evidence_id,
  // siempre caemos al fallback (console.warn explícito).
  const highlights = useMemo(() => {
    if (!currentPage || !evidence) return [];
    const regions: Array<{ page: number; x: number; y: number; width: number; height: number }> = [];
    if (regions.length === 0) {
      console.warn(
        '[pdf-overlay] evidence sin regiones, resaltando página completa',
        evidence.evidence_id,
      );
      return [fullPageFallback(currentPage.width, currentPage.height)];
    }
    return normalizeRegions(
      regions,
      currentPage.width,
      currentPage.height,
    );
  }, [currentPage, evidence]);

  const handleCopyId = () => {
    if (!evidence) return;
    void navigator.clipboard.writeText(evidence.evidence_id).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    });
  };

  if (!evidence) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-5xl gap-0 p-0 sm:max-w-5xl"
        aria-label={`Visor de evidencia ${evidence.evidence_id}`}
      >
        <DialogHeader className="border-b px-5 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-0.5">
              <DialogTitle className="text-base">Evidencia {evidence.evidence_id}</DialogTitle>
              <DialogDescription className="font-mono text-xs">
                {evidence.document_hash} · página {evidence.pdf_page}
              </DialogDescription>
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
              <Separator orientation="vertical" className="mx-1 h-5" />
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setScale((s) => Math.max(MIN_SCALE, s - 0.2))}
                aria-label="Reducir zoom"
              >
                <span className="text-xs">−</span>
              </Button>
              <span className="text-xs tabular-nums text-muted-foreground">
                {Math.round(scale * 100)}%
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setScale((s) => Math.min(MAX_SCALE, s + 0.2))}
                aria-label="Aumentar zoom"
              >
                <span className="text-xs">+</span>
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onOpenChange(false)}
                aria-label="Cerrar visor"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </DialogHeader>

        {snippet && (
          <blockquote className="border-l-2 border-primary bg-muted/50 px-5 py-2 text-xs italic">
            {snippet.length > 320 ? `${snippet.slice(0, 320)}…` : snippet}
          </blockquote>
        )}

        <div
          ref={containerRef}
          className="relative max-h-[70vh] overflow-auto bg-muted/30 px-5 py-4"
        >
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
              className="relative mx-auto origin-top bg-white shadow-md"
              style={{
                width: currentPage.width * scale,
                height: currentPage.height * scale,
              }}
            >
              <PageCanvas page={currentPage} scale={scale} />
              {highlights.map((region, i) => (
                <div
                  key={i}
                  className="pdf-highlight-fullpage pointer-events-none absolute"
                  style={{
                    left: region.x * scale,
                    top: region.y * scale,
                    width: region.width * scale,
                    height: region.height * scale,
                  }}
                  aria-hidden="true"
                />
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-2 border-t px-5 py-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopyId}
              aria-label="Copiar ID de evidencia"
            >
              <Copy className="h-3.5 w-3.5" />
              {copied ? 'Copiado' : evidence.evidence_id}
            </Button>
          </div>
          <a
            href={src}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            Ver PDF en nueva pestaña <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function PageCanvas({ page, scale }: { page: RenderedPage; scale: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Aplicamos el escalado via CSS sobre el canvas ya renderizado.
    const canvas = page.canvas;
    canvas.style.transformOrigin = 'top left';
    canvas.style.transform = `scale(${scale})`;
    el.replaceChildren(canvas);
    return () => {
      el.replaceChildren();
      canvas.style.transform = '';
    };
  }, [page, scale]);
  return <div ref={ref} />;
}
