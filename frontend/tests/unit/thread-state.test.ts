import { describe, it, expect } from 'vitest';
import {
  initialState,
  threadReducer,
  type ToolCall,
  type ToolCallKind,
} from '@/lib/thread-state';

describe('threadReducer', () => {
  it('SUBMIT añade mensajes user+assistant con tool calls planned por modo', () => {
    const state = initialState();
    const next = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u1',
      assistantId: 'a1',
      text: 'hola',
      mode: 'question',
      createdAt: Date.now(),
    });
    expect(next.messages.length).toBe(2);
    expect(next.messages[0]?.role).toBe('user');
    expect(next.messages[1]?.role).toBe('assistant');
    if (next.messages[1]?.role === 'assistant') {
      const kinds = next.messages[1].toolCalls.map((t: ToolCall) => t.kind as ToolCallKind);
      expect(kinds).toEqual(['classify', 'retrieve']);
    }
    expect(next.isStreaming).toBe(true);
  });

  it('SUBMIT en modo claim planifica check_rules + apply_decision', () => {
    const state = initialState();
    const next = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u2',
      assistantId: 'a2',
      text: 'siniestro',
      mode: 'claim',
      createdAt: Date.now(),
    });
    if (next.messages[1]?.role === 'assistant') {
      const kinds = next.messages[1].toolCalls.map((t: ToolCall) => t.kind);
      expect(kinds).toEqual(['classify', 'check_rules', 'apply_decision']);
    }
  });

  it('TOOL_CALL_DONE actualiza status del tool call por id', () => {
    let state = initialState();
    state = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u',
      assistantId: 'a',
      text: 'x',
      mode: 'auto',
      createdAt: Date.now(),
    });
    const tcId = (state.messages[1] as { toolCalls: ToolCall[] }).toolCalls[0]!.id;
    const next = threadReducer(state, {
      type: 'TOOL_CALL_DONE',
      id: tcId,
      durationMs: 50,
      payload: { mode: 'auto' },
    });
    const assistant = next.messages[1] as { toolCalls: ToolCall[] };
    expect(assistant.toolCalls[0]?.status).toBe('done');
    expect(assistant.toolCalls[0]?.durationMs).toBe(50);
  });

  it('STREAM_COMPLETED cierra isStreaming y guarda envelope', () => {
    let state = initialState();
    state = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u',
      assistantId: 'a',
      text: 'x',
      mode: 'auto',
      createdAt: Date.now(),
    });
    const next = threadReducer(state, {
      type: 'STREAM_COMPLETED',
      response: {
        request_id: 'r-1',
        requested_mode: 'auto',
        resolved_mode: 'question',
        evidence: [],
        metadata: {},
        result: {
          kind: 'question',
          status: 'answered',
          blocks: [{ text: 'Respuesta', evidence_ids: [] }],
          trace_id: null,
        },
      },
      requestId: 'r-1',
    });
    expect(next.isStreaming).toBe(false);
    const assistant = next.messages[1];
    if (assistant && assistant.role === 'assistant') {
      expect(assistant.status).toBe('done');
      expect(assistant.envelope?.request_id).toBe('r-1');
      expect(assistant.streamedText.length).toBeGreaterThan(0);
    }
  });

  it('STREAM_FAILED marca el assistant como error', () => {
    let state = initialState();
    state = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u',
      assistantId: 'a',
      text: 'x',
      mode: 'auto',
      createdAt: Date.now(),
    });
    const next = threadReducer(state, {
      type: 'STREAM_FAILED',
      message: 'network_error: fail',
      requestId: 'r',
    });
    expect(next.isStreaming).toBe(false);
    const assistant = next.messages[1];
    if (assistant && assistant.role === 'assistant') {
      expect(assistant.status).toBe('error');
      expect(assistant.errorMessage).toMatch(/fail/);
    }
  });

  it('OPEN_PDF / CLOSE_PDF controla el estado del overlay', () => {
    let state = initialState();
    expect(state.openPdf).toBeNull();
    state = threadReducer(state, {
      type: 'OPEN_PDF',
      target: {
        evidence: {
          evidence_id: 'ev-1',
          document_hash: 'h',
          pdf_page: 1,
          delivery: 'text',
        },
        snippet: 'hola',
      },
    });
    expect(state.openPdf?.evidence.evidence_id).toBe('ev-1');
    state = threadReducer(state, { type: 'CLOSE_PDF' });
    expect(state.openPdf).toBeNull();
  });

  it('NEW_THREAD resetea mensajes y añade summary al sidebar', () => {
    const state = initialState();
    const next = threadReducer(state, {
      type: 'NEW_THREAD',
      id: 't-1',
      title: 'Hilo de prueba',
    });
    expect(next.messages).toEqual([]);
    expect(next.activeThreadId).toBe('t-1');
    expect(next.threads[0]?.id).toBe('t-1');
  });
});
