import { Sparkles, ChevronDown, ChevronUp, AlertCircle } from 'lucide-react';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { TextGenerateEffect } from '@/components/ui/text-generate-effect';
import { ToolCallCard } from '@/components/tool-call/tool-call-card';
import { CitationChip } from '@/components/citation/citation-chip';
import { cn } from '@/lib/cn';
import { ClarificationPanel } from '@/components/thread/clarification-panel';
import type {
  CitationRef,
  MessageAssistant,
} from '@/lib/thread-state';

export interface AssistantMessageProps {
  message: MessageAssistant;
  /** ¿Es el último mensaje? Controla auto-scroll externo. */
  isLatest?: boolean;
  /** Click en citation chip → abre PDF overlay. */
  onOpenCitation?: (citation: CitationRef) => void;
  /** Reintentar un tool call individual. */
  onRetryToolCall?: (toolCallId: string) => void;
  onSubmitClarification?: (clarifications: string[]) => void;
}

const MODE_LABEL: Record<string, string> = {
  question: 'Pregunta',
  claim: 'Siniestro',
  clarification: 'Necesita más contexto',
  auto: 'Auto',
};

/**
 * AssistantMessage — burbuja con avatar Sparkles, tool calls arriba,
 * contenido streamed (text-generate-effect cuando streaming), citation
 * chips al final y metadata collapsable.
 */
export function AssistantMessage({
  message,
  onOpenCitation,
  onRetryToolCall,
  onSubmitClarification,
}: AssistantMessageProps) {
  const [metaOpen, setMetaOpen] = useState(false);
  const isStreaming = message.status === 'streaming';
  const isError = message.status === 'error';
  const envelope = message.envelope;
  const resolvedMode = envelope?.resolved_mode;
  const traceId =
    envelope && envelope.result && 'trace_id' in envelope.result
      ? envelope.result.trace_id
      : null;
  const langfuseUrl = envelope?.metadata?.langfuse_url ?? envelope?.metadata?.trace_url ?? null;
  const missingInformation = envelope?.result?.kind === 'claim'
    ? envelope.result.missing_information
    : envelope?.result?.kind === 'clarification'
      ? envelope.result.missing_fields
      : [];

  return (
    <article
      aria-label="Mensaje del asistente"
      className="flex items-start gap-3"
      data-role="assistant"
    >
      <Avatar className="h-8 w-8 border bg-primary text-primary-foreground">
        <AvatarFallback className="bg-primary text-primary-foreground">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
        </AvatarFallback>
      </Avatar>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <header className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <span className="font-medium text-foreground">Asistente</span>
          {resolvedMode && (
            <>
              <span aria-hidden="true">·</span>
              <span>{MODE_LABEL[resolvedMode] ?? resolvedMode}</span>
            </>
          )}
          {message.requestId && (
            <>
              <span aria-hidden="true">·</span>
              <code className="font-mono text-[9px]">{message.requestId.slice(0, 8)}</code>
            </>
          )}
        </header>

        {message.toolCalls.length > 0 && (
          <div
            aria-label="Tool calls"
            className="flex flex-col gap-1.5"
            aria-live="polite"
          >
            {message.toolCalls.map((tc) => (
              <ToolCallCard
                key={tc.id}
                toolCall={tc}
                onRetry={onRetryToolCall ? (id) => onRetryToolCall(id) : undefined}
              />
            ))}
          </div>
        )}

        <div
          aria-live="polite"
          aria-atomic="false"
          className={cn(
            'rounded-lg border bg-card px-3 py-2 text-sm shadow-sm',
            isError && 'border-destructive/40 bg-destructive/5',
          )}
        >
          {isError ? (
            <p className="flex items-start gap-2 text-destructive">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span className="text-pretty">{message.errorMessage ?? 'Error desconocido.'}</span>
            </p>
          ) : message.streamedText.length === 0 && isStreaming ? (
            <p className="text-muted-foreground">Generando respuesta…</p>
          ) : (
            <TextGenerateEffect text={message.streamedText} streaming={isStreaming} />
          )}
        </div>

        {onSubmitClarification && missingInformation.length > 0 && message.status === 'done' && (
          <ClarificationPanel
            missingInformation={missingInformation}
            onSubmit={onSubmitClarification}
          />
        )}

        {message.citations.length > 0 && (
          <div
            aria-label="Citas de evidencia"
            className="flex flex-wrap items-center gap-1.5"
          >
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Fuentes
            </span>
            {message.citations.map((c) => (
              <CitationChip
                key={`${c.evidenceId}-${c.pdfPage}`}
                evidenceId={c.evidenceId}
                pdfPage={c.pdfPage}
                label={undefined}
                onClick={() => onOpenCitation?.(c)}
              />
            ))}
          </div>
        )}

        {(message.requestId || traceId || langfuseUrl) && (
          <>
            <Separator className="my-1" />
            <div className="flex items-center justify-between text-[10px] text-muted-foreground">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setMetaOpen((o) => !o)}
                aria-expanded={metaOpen}
                aria-controls={`meta-${message.id}`}
                className="h-6 gap-1 px-1 text-[10px] font-normal text-muted-foreground hover:text-foreground"
              >
                {metaOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                Metadata
              </Button>
              {langfuseUrl && (
                <a
                  href={langfuseUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary hover:underline"
                >
                  Ver en Langfuse ↗
                </a>
              )}
            </div>
            {metaOpen && (
              <motion.dl
                id={`meta-${message.id}`}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="grid grid-cols-[max-content_1fr] gap-x-2 gap-y-0.5 text-[10px]"
              >
                {message.requestId && (
                  <>
                    <dt className="text-muted-foreground">request_id</dt>
                    <dd className="font-mono break-all">{message.requestId}</dd>
                  </>
                )}
                {resolvedMode && (
                  <>
                    <dt className="text-muted-foreground">resolved_mode</dt>
                    <dd className="font-mono">{resolvedMode}</dd>
                  </>
                )}
                {traceId && (
                  <>
                    <dt className="text-muted-foreground">trace_id</dt>
                    <dd className="font-mono break-all">{traceId}</dd>
                  </>
                )}
              </motion.dl>
            )}
          </>
        )}
      </div>
    </article>
  );
}
