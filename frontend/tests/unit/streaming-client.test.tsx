import { describe, it, expect, vi } from 'vitest';
import { streamQuery } from '@/lib/streaming-client';
import type { EnvelopeRequest } from '@/api/queries';

/**
 * Mockeamos eventsource-parser a través de un fetch fake que entrega un
 * stream de chunks SSE y verificamos que el callback onEvent recibe los
 * eventos tipados correctos.
 */

function makeResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

const baseRequest: EnvelopeRequest = {
  text: 'test',
  mode: 'auto',
  language: 'es',
  stream: true,
};

describe('streaming-client', () => {
  it('emite started → stage → completed en orden', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        makeResponse([
          'event: started\ndata: {"request_id":"r1","mode":"auto"}\n\n',
          'event: stage\ndata: {"stage":"dispatch","request_id":"r1"}\n\n',
          'event: completed\ndata: {"request_id":"r1","requested_mode":"auto","resolved_mode":"question","result":{"kind":"question","status":"answered","blocks":[],"trace_id":"t"}}\n\n',
        ]),
      );

    const events: string[] = [];
    const handle = streamQuery(baseRequest, {
      signal: new AbortController().signal,
      onEvent: (e) => events.push(e.type),
    });
    await handle.done;
    fetchSpy.mockRestore();

    expect(events).toEqual(['started', 'stage', 'completed']);
  });

  it('emite failed cuando el HTTP responde con 5xx', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response('error', { status: 503 }));

    const events: { type: string; code?: string }[] = [];
    const handle = streamQuery(baseRequest, {
      signal: new AbortController().signal,
      onEvent: (e) => {
        if (e.type === 'failed') events.push({ type: e.type, code: e.code });
        else events.push({ type: e.type });
      },
    });
    await handle.done;
    fetchSpy.mockRestore();

    expect(events.find((e) => e.type === 'failed')).toBeDefined();
    expect(events.find((e) => e.type === 'failed')?.code).toBe('http_error');
  });

  it('AbortController cancela el stream y emite aborted', async () => {
    const controller = new AbortController();
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(
        () =>
          new Promise<never>((_resolve, reject) => {
            controller.signal.addEventListener('abort', () => {
              reject(Object.assign(new Error('Aborted'), { name: 'AbortError' }));
            });
          }),
      );

    const events: string[] = [];
    const handle = streamQuery(baseRequest, {
      signal: controller.signal,
      onEvent: (e) => events.push(e.type),
    });
    controller.abort();
    await handle.done;
    fetchSpy.mockRestore();

    expect(events).toContain('aborted');
  });
});

describe('el cliente lee los campos donde el backend los pone', () => {
  /** Empuja una trama SSE por el parser y devuelve el evento emitido. */
  async function emit(event: string, data: unknown) {
    const { startStream } = await import('@/lib/streaming-client');
    const received: unknown[] = [];
    const body = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } }),
    );
    const handle = startStream(
      { text: 'x', mode: 'auto', language: 'es', stream: true },
      { mode: 'auto', signal: new AbortController().signal, onEvent: (e) => received.push(e) },
    );
    await handle.done;
    return received[0] as Record<string, unknown>;
  }

  it('saca code y message del payload de un evento failed', async () => {
    // Formato real desde que los eventos llevan event_id + timestamp.
    const got = await emit('failed', {
      event: 'failed',
      event_id: 'e-1',
      request_id: 'r-1',
      timestamp: '2026-09-02T13:49:46+00:00',
      payload: { code: 'internal_error', message: 'routing workflow timed out', retryable: true },
    });
    expect(got.code).toBe('internal_error');
    expect(got.message).toBe('routing workflow timed out');
    expect(got.message).not.toBe('Error desconocido');
  });

  it('saca stage del payload', async () => {
    const got = await emit('stage', {
      event: 'stage',
      request_id: 'r-1',
      payload: { stage: 'dispatch', resolved_mode: 'claim' },
    });
    expect(got.stage).toBe('dispatch');
  });

  it('saca mode del payload de un evento started', async () => {
    const got = await emit('started', {
      event: 'started',
      request_id: 'r-1',
      payload: { mode: 'claim' },
    });
    expect(got.mode).toBe('claim');
  });

  it('sigue aceptando el formato antiguo con los campos en la raíz', async () => {
    const got = await emit('failed', {
      code: 'http_error',
      message: 'boom',
      request_id: 'r-1',
    });
    expect(got.code).toBe('http_error');
    expect(got.message).toBe('boom');
  });
});

describe('el evento completed trae el sobre dentro de payload.response', () => {
  async function emitCompleted(data: unknown) {
    const { startStream } = await import('@/lib/streaming-client');
    const received: Array<Record<string, unknown>> = [];
    const body = `event: completed\ndata: ${JSON.stringify(data)}\n\n`;
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } }),
    );
    const handle = startStream(
      { text: 'x', mode: 'auto', language: 'es', stream: true },
      {
        mode: 'auto',
        signal: new AbortController().signal,
        onEvent: (e) => received.push(e as unknown as Record<string, unknown>),
      },
    );
    await handle.done;
    return received[0];
  }

  const envelope = {
    request_id: 'r-1',
    requested_mode: 'auto',
    resolved_mode: 'question',
    result: { kind: 'question', status: 'answered', blocks: [{ text: 'Respuesta.', evidence_ids: [] }] },
    evidence: [],
    metadata: {},
  };

  it('desenvuelve el sobre en vez de tratar la trama como el sobre', async () => {
    const got = await emitCompleted({
      event: 'completed',
      event_id: 'e-1',
      request_id: 'r-1',
      payload: { response: envelope },
    });
    const response = got.response as typeof envelope;
    // Sin desenvolver, `result` era undefined y el chat quedaba en blanco.
    expect(response.result).toBeDefined();
    expect(response.result.kind).toBe('question');
    expect(response.request_id).toBe('r-1');
  });

  it('sigue aceptando un sobre plano', async () => {
    const got = await emitCompleted(envelope);
    expect((got.response as typeof envelope).result.kind).toBe('question');
  });
});
