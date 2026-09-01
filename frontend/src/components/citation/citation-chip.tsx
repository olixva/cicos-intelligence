import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { FileText } from 'lucide-react';
import { cn } from '@/lib/cn';
import { BorderBeam } from '@/components/ui/border-beam';

export interface CitationChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  evidenceId: string;
  pdfPage: number;
  /** Etiqueta corta (printed_label del backend). */
  label?: string;
  /** Si está seleccionado (highlight). */
  active?: boolean;
}

/**
 * CitationChip — Origin UI comp-265-inspired (spec UX v2).
 *
 * Botón pequeño que muestra el ID de evidencia en monospace, la página y
 * opcionalmente un label legible. Al pasar el cursor, un BorderBeam
 * recorre el borde. Click → abre PDF overlay vía `onClick`.
 */
export const CitationChip = forwardRef<HTMLButtonElement, CitationChipProps>(
  function CitationChip({ evidenceId, pdfPage, label, active, className, ...props }, ref) {
    const ariaLabel = label
      ? `Abrir ${label} (evidencia ${evidenceId}, página ${pdfPage})`
      : `Abrir evidencia ${evidenceId}, página ${pdfPage}`;

    return (
      <button
        ref={ref}
        type="button"
        aria-label={ariaLabel}
        aria-pressed={active ?? false}
        data-active={active ? 'true' : undefined}
        className={cn(
          'group relative isolate inline-flex items-center gap-1.5 overflow-hidden rounded-full border bg-background px-2.5 py-1 text-xs',
          'transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          active
            ? 'border-primary bg-primary/10 text-primary'
            : 'border-border text-foreground',
          className,
        )}
        {...props}
      >
        <span
          aria-hidden="true"
          className="absolute inset-0 -z-10 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
        >
          <BorderBeam size={60} duration={5} />
        </span>
        <FileText className="h-3 w-3" aria-hidden="true" />
        <span className="font-mono text-[10px] opacity-70">p.{pdfPage}</span>
        <span className="max-w-[200px] truncate">{label ?? evidenceId}</span>
      </button>
    );
  },
);
