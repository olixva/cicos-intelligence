import { createParser, type ParsedEvent, type ParseEvent } from 'eventsource-parser';
import { env } from '@/env';
import { newRequestId } from '@/lib/request-id';
import type {
  EnvelopeRequest,
  EnvelopeResponse,
  UiMode,
} from '@/api/queries';

/**
 * streaming-client — POST + SSE para `/api/v1/queries/stream`.
 *
 * Decisión D2: usamos `fetch` + `ReadableStream` + `eventsource-parser@1`,
 * NUNCA `EventSource`. Razón: `EventSource` solo soporta GET, y el endpoint
 * es POST para permitir un body grande (`EnvelopeRequest`).
 *
 * Contrato SSE del backend (ver backend/.../routes/queries.py:213-262):
 *   - event: started   → { request_id, mode }
 *   - event: stage     → { stage, request_id }
 *   - event: completed → EnvelopeResponse JSON completo
 *   - event: failed    → { code, message, request_id, retryable }
 *
 * Esta capa es PURA: recibe el stream y emite eventos tipados. La
 * orquestación (estado del thread, render de tool calls, animaciones)
 * vive en `thread-state.ts`. La separación permite testear ambos por
 * separado.
 */

/** Evento emitido por el stream. Discriminated union por `type`. */
export type StreamingEvent =
  | { type: 'started'; requestId: string; mode: UiMode }
  | { type: 'stage'; stage: string; requestId: string }
  | { type: 'completed'; response: EnvelopeResponse }
  | { type: 'failed'; code: string; message: string; requestId: string; retryable: boolean }
  | { type: 'aborted' };

export interface StreamOptions {
  /** Modo de UI (`auto`/`question`/`claim`). */
  mode: UiMode;
  /** Idioma para el backend. */
  language?: 'es' | 'en';
  /** AbortSignal para cancelar la suscripción desde fuera. */
  signal: AbortSignal;
  /** Callback invocado por cada evento. */
  onEvent: (event: StreamingEvent) => void;
  /** Callback invocado al final (con o sin error). */
  onDone?: () => void;
  /** Callback invocado ante error fatal antes del primer evento. */
  onError?: (err: Error) => void;
}

/** Resultado devuelto por `streamQuery`. */
export interface StreamHandle {
  /** Promesa que se resuelve cuando el stream termina (cualquier causa). */
  done: Promise<void>;
  /** AbortController expuesto para `cancel()`. */
  controller: AbortController;
}

/** Helper para iniciar el POST + parseo SSE. */
export function streamQuery(input: EnvelopeRequest, opts: Omit<StreamOptions, 'mode'>): StreamHandle {
  return startStream(input, { ...opts, mode: input.mode });
}

/**
 * Lanza el POST contra `/api/v1/queries/stream` y conecta el parser.
 * Devuelve un handle con `.done` y `.controller`.
 */
export function startStream(input: EnvelopeRequest, opts: StreamOptions): StreamHandle {
  const controller = new AbortController();
  // Si el caller ya proveyó signal, conectamos abort.
  if (opts.signal) {
    if (opts.signal.aborted) controller.abort();
    else opts.signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  const requestId = newRequestId();
  const url = `${env.VITE_API_BASE_URL}/api/v1/queries/stream`;

  const done = (async () => {
    const parser = createParser((event: ParseEvent) => {
      if (event.type !== 'event') return;
      handleParsedEvent(event, opts.onEvent);
    });

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          'X-Request-ID': requestId,
        },
        body: JSON.stringify({ ...input, stream: true }),
        signal: controller.signal,
        credentials: 'same-origin',
      });

      if (!response.ok || !response.body) {
        const e = new Error(`HTTP ${response.status} ${response.statusText}`);
        opts.onError?.(e);
        opts.onEvent({
          type: 'failed',
          code: 'http_error',
          message: e.message,
          requestId,
          retryable: response.status >= 500,
        });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      for (;;) {
        const { value, done: readDone } = await reader.read();
        if (readDone) break;
        const text = decoder.decode(value, { stream: true });
        parser.feed(text);
      }
    } catch (err) {
      if ((err as { name?: string }).name === 'AbortError') {
        opts.onEvent({ type: 'aborted' });
        return;
      }
      const e = err instanceof Error ? err : new Error(String(err));
      opts.onError?.(e);
      opts.onEvent({
        type: 'failed',
        code: 'network_error',
        message: e.message,
        requestId,
        retryable: true,
      });
    } finally {
      opts.onDone?.();
    }
  })();

  return { done, controller };
}

/** Despacha un evento SSE crudo al callback tipado. */
function handleParsedEvent(
  msg: ParsedEvent,
  onEvent: (event: StreamingEvent) => void,
): void {
  const event = msg.event ?? 'message';
  const data = msg.data;

  try {
    switch (event) {
      case 'started': {
        const parsed = JSON.parse(data) as { request_id?: string; mode?: UiMode };
        onEvent({
          type: 'started',
          requestId: parsed.request_id ?? '',
          mode: (parsed.mode ?? 'auto') as UiMode,
        });
        return;
      }
      case 'stage': {
        const parsed = JSON.parse(data) as { stage?: string; request_id?: string };
        onEvent({
          type: 'stage',
          stage: parsed.stage ?? 'unknown',
          requestId: parsed.request_id ?? '',
        });
        return;
      }
      case 'completed': {
        const parsed = JSON.parse(data) as EnvelopeResponse;
        onEvent({ type: 'completed', response: parsed });
        return;
      }
      case 'failed': {
        const parsed = JSON.parse(data) as {
          code?: string;
          message?: string;
          request_id?: string;
          retryable?: boolean;
        };
        onEvent({
          type: 'failed',
          code: parsed.code ?? 'unknown',
          message: parsed.message ?? 'Error desconocido',
          requestId: parsed.request_id ?? '',
          retryable: parsed.retryable ?? true,
        });
        return;
      }
      default:
        // Ignorar eventos desconocidos — el parser los entrega igual.
        return;
    }
  } catch (err) {
    // JSON malformado: lo comunicamos como failure pero sin abortar el stream.
    const e = err instanceof Error ? err : new Error(String(err));
    onEvent({
      type: 'failed',
      code: 'parse_error',
      message: e.message,
      requestId: '',
      retryable: false,
    });
  }
}
