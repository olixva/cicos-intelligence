import type { EnvelopeResponse } from '@/api/queries';
import { newRequestId } from '@/lib/request-id';

export interface FooterProps {
  requestId?: string;
  traceId?: string;
  response?: EnvelopeResponse | null;
}

/**
 * Footer — request_id, trace_id y link a Langfuse si está disponible.
 *
 * Decisión del spec UX: este footer debe ser siempre visible. Si no hay
 * respuesta todavía, mostramos el request_id que se enviará en el próximo
 * POST (uuid v4 generado en el cliente).
 */
export function Footer({ requestId, traceId, response }: FooterProps) {
  const resolvedRequestId = response?.request_id ?? requestId ?? newRequestId();
  const resolvedTraceId =
    response?.result && 'trace_id' in response.result
      ? (response.result.trace_id ?? null)
      : traceId ?? null;

  const langfuseUrl =
    response?.metadata?.langfuse_url ?? response?.metadata?.trace_url ?? null;

  return (
    <footer className="border-t bg-card/50 py-3 text-xs text-muted-foreground">
      <div className="container flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-4">
          <span>
            request_id:{' '}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">
              {resolvedRequestId}
            </code>
          </span>
          {resolvedTraceId && (
            <span>
              trace_id:{' '}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">
                {resolvedTraceId}
              </code>
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {langfuseUrl && (
            <a
              href={langfuseUrl}
              target="_blank"
              rel="noreferrer"
              className="text-primary underline-offset-4 hover:underline"
            >
              Ver en Langfuse ↗
            </a>
          )}
          <span>Allianz CICOS · MVP</span>
        </div>
      </div>
    </footer>
  );
}
