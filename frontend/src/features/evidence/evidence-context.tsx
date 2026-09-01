import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { EvidenceItem } from '@/api/queries';

/**
 * EvidenceContext — estado global de la pieza de evidencia abierta.
 *
 * El visor PDF (pdf-viewer.tsx) y los chips de evidencia (evidence-chip.tsx)
 * se comunican vía este context. Cuando el usuario hace click en un chip,
 * el chip llama `openEvidence(item)`. El visor escucha y renderiza la
 * página + regiones.
 *
 * Decisión D4: si `evidence.regions` está vacío, el visor cae al fallback
 * "página completa" con overlay tenue. El context no necesita saberlo.
 */

export interface OpenEvidence {
  item: EvidenceItem;
  /** Texto asociado al bloque, si el caller lo tiene (p.ej. AnswerBlockResponse.text). */
  snippet?: string;
}

interface EvidenceContextValue {
  open: OpenEvidence | null;
  openEvidence: (item: OpenEvidence['item'], snippet?: string) => void;
  closeEvidence: () => void;
  /** True si hay una evidencia abierta (util para ocultar la página de inicio). */
  hasOpen: boolean;
}

const EvidenceContext = createContext<EvidenceContextValue | null>(null);

export function EvidenceProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState<OpenEvidence | null>(null);

  const openEvidence = useCallback((item: OpenEvidence['item'], snippet?: string) => {
    setOpen({ item, snippet });
  }, []);

  const closeEvidence = useCallback(() => {
    setOpen(null);
  }, []);

  const value = useMemo<EvidenceContextValue>(
    () => ({ open, openEvidence, closeEvidence, hasOpen: open !== null }),
    [open, openEvidence, closeEvidence],
  );

  return <EvidenceContext.Provider value={value}>{children}</EvidenceContext.Provider>;
}

export function useEvidence(): EvidenceContextValue {
  const ctx = useContext(EvidenceContext);
  if (!ctx) {
    throw new Error('useEvidence debe usarse dentro de <EvidenceProvider>');
  }
  return ctx;
}
