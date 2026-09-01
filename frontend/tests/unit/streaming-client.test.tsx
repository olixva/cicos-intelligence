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
