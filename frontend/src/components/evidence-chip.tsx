import { FileText, Image as ImageIcon, BookOpen } from 'lucide-react';
import { useEvidence } from '@/features/evidence/evidence-context';
import type { EvidenceItem } from '@/api/queries';
import { cn } from '@/lib/cn';

const ICONS = {
  text: FileText,
  image: ImageIcon,
  rule: BookOpen,
} as const;

export interface EvidenceChipProps {
  item: EvidenceItem;
  snippet?: string;
  className?: string;
}

/**
 * EvidenceChip — botón pequeño clicable que abre la pieza de evidencia en
 * el visor PDF vía el EvidenceContext. El visor escucha el context y
 * renderiza la página + regiones (D4: fallback a página completa si regions
 * está vacío).
 */
export function EvidenceChip({ item, snippet, className }: EvidenceChipProps) {
  const { openEvidence, open } = useEvidence();
  const Icon = ICONS[item.delivery] ?? FileText;
  const isOpen = open?.item.evidence_id === item.evidence_id;

  return (
    <button
      type="button"
      onClick={() => openEvidence(item, snippet)}
      aria-pressed={isOpen}
      aria-label={`Abrir evidencia ${item.evidence_id}, página ${item.pdf_page}`}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-0.5 text-xs',
        'transition-colors hover:bg-accent',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        isOpen
          ? 'border-primary bg-primary/10 text-primary'
          : 'border-border text-foreground',
        className,
      )}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      <span className="font-mono text-[10px] opacity-70">p.{item.pdf_page}</span>
      <span className="max-w-[160px] truncate">{item.evidence_id}</span>
    </button>
  );
}
