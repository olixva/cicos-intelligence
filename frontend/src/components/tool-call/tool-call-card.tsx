import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RotateCw,
  Search,
  GitBranch,
  ShieldCheck,
  ListChecks,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  applicabilityLabel,
  decisionLabel,
  type Applicability,
  type Decision,
} from '@/lib/claim-format';
import type { ToolCall, ToolCallKind } from '@/lib/thread-state';

const ICONS: Record<ToolCallKind, LucideIcon> = {
  classify: GitBranch,
  retrieve: Search,
  check_rules: ShieldCheck,
  apply_decision: ListChecks,
};

const LABELS: Record<ToolCallKind, { pending: string; done: string; error: string }> = {
  classify: { pending: 'Clasificando consulta', done: 'Consulta clasificada', error: 'Error al clasificar' },
  retrieve: { pending: 'Recuperando evidencia', done: 'Evidencia recuperada', error: 'Error recuperando evidencia' },
  check_rules: { pending: 'Verificando reglas', done: 'Reglas evaluadas', error: 'Error verificando reglas' },
  apply_decision: { pending: 'Aplicando decisión', done: 'Decisión emitida', error: 'Error aplicando decisión' },
};

export interface ToolCallCardProps {
  toolCall: ToolCall;
  /** Expandido por defecto. */
  defaultExpanded?: boolean;
  /** Reintentar (solo se muestra en estado error si está definido). */
  onRetry?: (id: string) => void;
}

/**
 * ToolCallCard — colapsable con switch sobre `kind`.
 *
 * Spec UX v2: discriminate exhaustivo (`satisfies never`) sobre
 * ToolCallKind para que añadir un kind nuevo al union del reducer
 * rompa el type-check aquí.
 *
 * Animaciones:
 *   - height expand/collapse via framer-motion `AnimatePresence`
 *   - shake horizontal en error
 */
export function ToolCallCard({ toolCall, defaultExpanded = false, onRetry }: ToolCallCardProps) {
  const [open, setOpen] = useState(defaultExpanded || toolCall.status === 'error');
  const Icon = ICONS[toolCall.kind];
  const labels = LABELS[toolCall.kind];
  const labelText =
    toolCall.status === 'pending'
      ? labels.pending
      : toolCall.status === 'error'
        ? labels.error
        : labels.done;

  const isPending = toolCall.status === 'pending';
  const isError = toolCall.status === 'error';

  return (
    <motion.article
      initial={{ opacity: 0, y: 6 }}
      animate={
        isError
          ? { opacity: 1, y: 0, x: [0, -4, 4, -4, 4, 0] }
          : { opacity: 1, y: 0 }
      }
      transition={{ duration: 0.25, x: { duration: 0.35 } }}
      className={cn(
        'group relative isolate overflow-hidden rounded-md border bg-card text-card-foreground',
        isError && 'border-destructive/60 bg-destructive/5',
      )}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={`tc-body-${toolCall.id}`}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Icon className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
        <span className="flex-1 font-medium">{labelText}</span>
        <StatusBadge status={toolCall.status} durationMs={toolCall.durationMs} />
        {open ? (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
        )}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={`tc-body-${toolCall.id}`}
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="overflow-hidden border-t bg-muted/30"
          >
            <div className="px-3 py-2 text-xs text-foreground">
              <ToolCallBody toolCall={toolCall} />
              {isError && toolCall.errorMessage && (
                <p className="mt-2 rounded border border-destructive/30 bg-destructive/5 p-2 text-destructive">
                  {toolCall.errorMessage}
                </p>
              )}
              {isError && onRetry && (
                <div className="mt-2 flex justify-end">
                  <button
                    type="button"
                    onClick={() => onRetry(toolCall.id)}
                    className="inline-flex items-center gap-1 rounded border border-destructive/40 px-2 py-1 text-[10px] text-destructive hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <RotateCw className="h-3 w-3" aria-hidden="true" />
                    Reintentar
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      {/* Spinner inline para estado pending sin expandir */}
      {isPending && (
        <span aria-hidden="true" className="absolute right-2 top-2 inline-flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
        </span>
      )}
    </motion.article>
  );
}

function StatusBadge({
  status,
  durationMs,
}: {
  status: ToolCall['status'];
  durationMs?: number;
}) {
  if (status === 'pending') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        En curso
      </span>
    );
  }
  if (status === 'error') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-destructive">
        <AlertCircle className="h-3 w-3" aria-hidden="true" />
        Error
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-success">
      <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
      {typeof durationMs === 'number' ? `${durationMs} ms` : 'OK'}
    </span>
  );
}

/** Switch literal sobre toolCall.kind con `satisfies never` para exhaustividad. */
function ToolCallBody({ toolCall }: { toolCall: ToolCall }) {
  switch (toolCall.kind) {
    case 'classify':
      return <ClassifyBody toolCall={toolCall} />;
    case 'retrieve':
      return <RetrieveBody toolCall={toolCall} />;
    case 'check_rules':
      return <CheckRulesBody toolCall={toolCall} />;
    case 'apply_decision':
      return <ApplyDecisionBody toolCall={toolCall} />;
    default: {
      const exhaustive: never = toolCall.kind;
      void exhaustive;
      return <p className="text-muted-foreground">Tipo de tool call desconocido.</p>;
    }
  }
}

function ClassifyBody({ toolCall }: { toolCall: ToolCall }) {
  const payload = toolCall.payload as { mode?: string; confidence?: number } | undefined;
  return (
    <div className="flex flex-col gap-1">
      <p className="text-muted-foreground">
        El router clasificó la consulta y eligió la rama óptima.
      </p>
      {payload?.mode && (
        <p>
          Rama seleccionada: <span className="font-mono text-[11px]">{payload.mode}</span>
          {payload.confidence !== undefined && (
            <> · confianza {(payload.confidence * 100).toFixed(0)}%</>
          )}
        </p>
      )}
    </div>
  );
}

function RetrieveBody({ toolCall }: { toolCall: ToolCall }) {
  const payload = toolCall.payload as
    | { chunks?: Array<{ evidenceId: string; pdfPage: number; preview: string; score?: number; printedLabel?: string }> }
    | undefined;
  if (!payload?.chunks || payload.chunks.length === 0) {
    return (
      <p className="text-muted-foreground">Sin chunks devueltos o sin evidencia accesible.</p>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {payload.chunks.map((c, i) => (
        <li key={`${c.evidenceId}-${i}`} className="rounded border bg-background p-2">
          <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
            <span className="font-mono">{c.evidenceId} · p.{c.pdfPage}</span>
            {typeof c.score === 'number' && (
              <span className="tabular-nums">score {c.score.toFixed(2)}</span>
            )}
          </div>
          <p className="mt-1 text-pretty">{c.preview}</p>
        </li>
      ))}
    </ul>
  );
}

function CheckRulesBody({ toolCall }: { toolCall: ToolCall }) {
  const payload = toolCall.payload as
    | {
        convention?: string | null;
        applicability?: Applicability;
        facts?: Array<{ name: string; value?: string | null; asserted_by?: string | null }>;
        contradictions?: Array<{ fact_name: string }>;
        missing_information?: string[];
      }
    | undefined;

  const facts = payload?.facts ?? [];
  const contradictions = payload?.contradictions ?? [];
  const missing = payload?.missing_information ?? [];
  const contradicted = new Set(contradictions.map((c) => c.fact_name));

  return (
    <div className="flex flex-col gap-2">
      <p className="text-muted-foreground">
        {payload?.applicability
          ? applicabilityLabel(payload.applicability)
          : 'Aplicabilidad sin determinar'}
        {payload?.convention ? ` · ${payload.convention}` : ''}
      </p>

      {facts.length > 0 && (
        <div>
          <p className="mb-0.5 font-medium">Hechos extraídos del relato</p>
          <ul className="flex flex-col gap-0.5">
            {facts.map((f, i) => (
              <li key={i} className="flex items-start gap-1.5">
                {contradicted.has(f.name) ? (
                  <AlertCircle className="mt-0.5 h-3 w-3 shrink-0 text-warning" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-success" aria-hidden="true" />
                )}
                <span>
                  <span className="font-mono text-[10px] opacity-70">{f.name}</span>
                  {f.value ? `: ${f.value}` : ''}
                  {f.asserted_by ? (
                    <span className="text-muted-foreground"> — según {f.asserted_by}</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {contradictions.length > 0 && (
        <p className="text-warning">
          {contradictions.length === 1
            ? '1 contradicción sin resolver entre las partes.'
            : `${contradictions.length} contradicciones sin resolver entre las partes.`}
        </p>
      )}

      {missing.length > 0 && (
        <div>
          <p className="mb-0.5 font-medium">Falta por confirmar</p>
          <ul className="flex flex-col gap-0.5">
            {missing.map((m, i) => (
              <li key={i} className="text-muted-foreground">
                — {m}
              </li>
            ))}
          </ul>
        </div>
      )}

      {facts.length === 0 && missing.length === 0 && (
        <p className="text-muted-foreground">
          No se extrajo ningún hecho aplicable del relato.
        </p>
      )}
    </div>
  );
}

function ApplyDecisionBody({ toolCall }: { toolCall: ToolCall }) {
  const payload = toolCall.payload as
    | {
        convention?: string | null;
        applicability?: Applicability;
        decision?: Decision;
        conditions?: string[];
      }
    | undefined;

  const decision = payload?.decision;
  // Una indeterminación no se pinta como éxito: sólo `resolved` va en verde.
  const decisionTone =
    decision === 'resolved'
      ? 'bg-success/10 text-success border-success/30'
      : decision === 'conditional'
        ? 'bg-warning/10 text-warning border-warning/30'
        : 'bg-muted text-muted-foreground border-border';

  const conditions = payload?.conditions ?? [];

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {payload?.convention && (
          <span className="rounded border bg-muted px-2 py-0.5 text-[10px] uppercase">
            {payload.convention}
          </span>
        )}
        <span className="rounded border bg-muted px-2 py-0.5 text-[11px]">
          {payload?.applicability
            ? applicabilityLabel(payload.applicability)
            : 'Aplicabilidad sin determinar'}
        </span>
        <span className={cn('rounded border px-2 py-0.5 text-[11px]', decisionTone)}>
          {decision ? decisionLabel(decision) : 'Sin determinar'}
        </span>
      </div>

      {conditions.length > 0 && (
        <div>
          <p className="mb-0.5 font-medium">Condiciones para poder concluir</p>
          <ul className="flex flex-col gap-0.5">
            {conditions.map((c, i) => (
              <li key={i} className="text-muted-foreground">
                — {c}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
