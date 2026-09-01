import { useCallback, useRef, useState } from 'react';
import { createParser, type ParsedEvent } from 'eventsource-parser';
import { newRequestId } from '@/lib/request-id';
import { env } from '@/env';
import type { EnvelopeRequest, EnvelopeResponse } from '@/api/queries';

/**
 * useQueryStream — POST /api/v1/queries/stream con SSE.
 *
 * Decisión D2: usamos `fetch` + `ReadableStream` + `eventsource-parser@1`,
 * NUNCA `EventSource`. Razón: `EventSource` solo soporta GET, y el endpoint
 * es POST para permitir un body grande (`EnvelopeRequest`).
 *
 * Eventos esperados del backend (ver `routes/queries.py:289`):
 *   - event: chunk      → data: { delta, partial?, finished? }
 *   - event: done       → data: { request_id, ... }
 *   - event: error      → data: { message }
 *
 * En este scaffold MVP el hook mantiene un buffer de deltas y resuelve con
 * la `EnvelopeResponse` final cuando llega `done`. El backend ya emite
 * bloques parciales como `QuestionResult.blocks`; el consumidor decide cómo
 * renderizar el streaming (no implementado en Fase 5b; será Fase 5b+).
 */

export interface StreamChunk {
  event: string | undefined;
  data: unknown;
}

export interface UseQueryStreamState {
  status: 'idle' | 'streaming' | 'done' | 'error';
  chunks: StreamChunk[];
  result: EnvelopeResponse | null;
  error: Error | null;
}

const INITIAL: UseQueryStreamState = {
  status: 'idle',
  chunks: [],
  result: null,
  error: null,
};

export function useQueryStream() {
  const [state, setState] = useState<UseQueryStreamState>(INITIAL);
  const controllerRef = useRef<AbortController | null>(null);

  const start = useCallback(async (input: EnvelopeRequest) => {
    setState(INITIAL);
    const controller = new AbortController();
    controllerRef.current = controller;

    const url = `${env.VITE_API_BASE_URL}/api/v1/queries/stream`;
    const requestId = newRequestId();

    setState({ status: 'streaming', chunks: [], result: null, error: null });

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          'X-Request-ID': requestId,
        },
        body: JSON.stringify(input),
        signal: controller.signal,
        credentials: 'same-origin',
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status} ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const parser = createParser((event) => {
        // eventsource-parser@1 emite ParsedEvent o ReconnectInterval. Solo
        // nos interesan los eventos con `type === 'event'`.
        if (event.type !== 'event') return;
        const msg: ParsedEvent = event;
        setState((prev) => {
          const chunks = [...prev.chunks, { event: msg.event, data: msg.data }];
          return { ...prev, chunks };
        });
        // Final envelope arrives in `done` event with the full payload.
        if (msg.event === 'done') {
          try {
            const parsed = JSON.parse(msg.data) as EnvelopeResponse;
            setState((prev) => ({ ...prev, status: 'done', result: parsed }));
          } catch (err) {
            const e = err instanceof Error ? err : new Error(String(err));
            setState((prev) => ({ ...prev, status: 'error', error: e }));
          }
        } else if (msg.event === 'error') {
          setState((prev) => ({
            ...prev,
            status: 'error',
            error: new Error(typeof msg.data === 'string' ? msg.data : 'stream error'),
          }));
        }
      });

      // Bucle principal: leer chunks crudos, decodificarlos y alimentar el parser.
      // El parser gestiona internamente los saltos de línea del SSE.
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        const text = decoder.decode(value, { stream: true });
        parser.feed(text);
      }

      setState((prev) => (prev.status === 'streaming' ? { ...prev, status: 'done' } : prev));
    } catch (err) {
      if ((err as { name?: string }).name === 'AbortError') {
        setState((prev) => ({ ...prev, status: 'idle' }));
        return;
      }
      const e = err instanceof Error ? err : new Error(String(err));
      setState((prev) => ({ ...prev, status: 'error', error: e }));
    } finally {
      controllerRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  const reset = useCallback(() => setState(INITIAL), []);

  return { state, start, cancel, reset };
}
