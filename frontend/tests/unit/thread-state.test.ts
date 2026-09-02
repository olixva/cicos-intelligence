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
      // Sin `classify`: en modo explícito el backend no clasifica nada.
      expect(kinds).toEqual(['retrieve']);
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
      // Sin `classify`: el usuario ya declaró que es un siniestro.
      expect(kinds).toEqual(['check_rules', 'apply_decision']);
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

  it('STREAM_COMPLETED muestra el motivo cuando una pregunta no tiene bloques', () => {
    let state = initialState();
    state = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u-empty-question',
      assistantId: 'a-empty-question',
      text: '¿Cuánto corresponde según el baremo de 2025?',
      mode: 'question',
      createdAt: Date.now(),
    });
    const next = threadReducer(state, {
      type: 'STREAM_COMPLETED',
      response: {
        request_id: 'r-empty-question',
        requested_mode: 'question',
        resolved_mode: 'question',
        evidence: [],
        metadata: {},
        result: {
          kind: 'question',
          status: 'out_of_scope',
          blocks: [],
          trace_id: null,
        },
      },
      requestId: 'r-empty-question',
    });
    const assistant = next.messages[1];
    if (!assistant || assistant.role !== 'assistant') throw new Error('assistant missing');
    expect(assistant.streamedText).toContain('fuera del alcance');
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
    // Partiendo de un hilo vacío, NEW_THREAD reutiliza el hilo actual en vez de
    // acumular una entrada idéntica en la barra lateral.
    expect(next.activeThreadId).toBe(state.activeThreadId);
    expect(next.threads.length).toBe(state.threads.length);
  });

  it('SUBMIT en modo auto planifica sólo classify (el resto lo añade RESOLVE_TOOL_PLAN)', () => {
    const state = initialState();
    const next = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u-auto',
      assistantId: 'a-auto',
      text: 'auto',
      mode: 'auto',
      createdAt: Date.now(),
    });
    if (next.messages[1]?.role === 'assistant') {
      const kinds = next.messages[1].toolCalls.map((t: ToolCall) => t.kind);
      expect(kinds).toEqual(['classify']);
    }
  });

  // Finding G1 #1 — dedupe de citations por (evidenceId, pdfPage).
  it('STREAM_COMPLETED dedupa citations por (evidenceId, pdfPage) con orden estable', () => {
    let state = initialState();
    state = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u-cite',
      assistantId: 'a-cite',
      text: 'cita',
      mode: 'question',
      createdAt: Date.now(),
    });
    const next = threadReducer(state, {
      type: 'STREAM_COMPLETED',
      response: {
        request_id: 'r-cite',
        requested_mode: 'question',
        resolved_mode: 'question',
        evidence: [
          { evidence_id: 'ev-1', document_hash: 'hash-1', pdf_page: 18, delivery: 'text' },
          { evidence_id: 'ev-2', document_hash: 'hash-2', pdf_page: 26, delivery: 'text' },
        ],
        metadata: {},
        result: {
          kind: 'question',
          status: 'answered',
          blocks: [
            { text: 'Bloque A', evidence_ids: ['ev-1', 'ev-2'] },
            { text: 'Bloque B', evidence_ids: ['ev-1'] },
          ],
          trace_id: null,
        },
      },
      requestId: 'r-cite',
    });
    const assistant = next.messages[1];
    if (!assistant || assistant.role !== 'assistant') {
      throw new Error('assistant missing');
    }
    // 2 bloques citan ev-1/p.18 y 1 bloque cita ev-2/p.26. Tras dedupe,
    // debe haber exactamente 2 entries, una por par, en orden de primera
    // aparición (ev-1 antes que ev-2).
    expect(assistant.citations).toHaveLength(2);
    expect(assistant.citations[0]?.evidenceId).toBe('ev-1');
    expect(assistant.citations[0]?.pdfPage).toBe(18);
    expect(assistant.citations[1]?.evidenceId).toBe('ev-2');
    expect(assistant.citations[1]?.pdfPage).toBe(26);
    // El snippet debe ser el del primer bloque que cita cada par.
    expect(assistant.citations[0]?.snippet).toBe('Bloque A');
    expect(assistant.citations[1]?.snippet).toBe('Bloque A');
    // Las keys que usará el render no se duplican (defensa contra el bug original).
    const keys = assistant.citations.map((c) => `${c.evidenceId}-${c.pdfPage}`);
    expect(new Set(keys).size).toBe(keys.length);
  });

  // Finding G1 #2 — RESOLVE_TOOL_PLAN para modo auto con envelope claim.
  it('RESOLVE_TOOL_PLAN en auto añade check_rules + apply_decision y cierra classify', () => {
    let state = initialState();
    state = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u-rtp',
      assistantId: 'a-rtp',
      text: 'auto',
      mode: 'auto',
      createdAt: Date.now(),
    });
    const next = threadReducer(state, {
      type: 'RESOLVE_TOOL_PLAN',
      envelope: {
        request_id: 'r-rtp',
        requested_mode: 'auto',
        resolved_mode: 'claim',
        evidence: [],
        metadata: {},
        result: {
          kind: 'claim',
          convention: 'CIDE',
          applicability: 'applicable',
          decision: 'resolved',
          party_ids: [],
          facts: [],
          contradictions: [],
          conditions: [],
          missing_information: [],
          blocks: [],
          rules_evaluated: [],
        },
      },
      requested_mode: 'auto',
    });
    const assistant = next.messages[1];
    if (!assistant || assistant.role !== 'assistant') {
      throw new Error('assistant missing');
    }
    const kinds = assistant.toolCalls.map((tc) => tc.kind);
    expect(kinds).toEqual(['classify', 'check_rules', 'apply_decision']);
    for (const tc of assistant.toolCalls) {
      expect(tc.status).toBe('done');
      // El backend todavía no emite un stage por etapa, así que no hay
      // duración que mostrar. Antes se escribía 0 ms, que era falso.
      expect(tc.durationMs).toBeUndefined();
    }
  });

  it('RESOLVE_TOOL_PLAN en auto con question añade retrieve', () => {
    let state = initialState();
    state = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u-q',
      assistantId: 'a-q',
      text: 'auto',
      mode: 'auto',
      createdAt: Date.now(),
    });
    const next = threadReducer(state, {
      type: 'RESOLVE_TOOL_PLAN',
      envelope: {
        request_id: 'r-q',
        requested_mode: 'auto',
        resolved_mode: 'question',
        evidence: [{ evidence_id: 'ev-1', document_hash: 'h', pdf_page: 1, delivery: 'text' }],
        metadata: {},
        result: {
          kind: 'question',
          status: 'answered',
          blocks: [{ text: 't', evidence_ids: ['ev-1'] }],
          trace_id: null,
        },
      },
      requested_mode: 'auto',
    });
    const assistant = next.messages[1];
    if (!assistant || assistant.role !== 'assistant') {
      throw new Error('assistant missing');
    }
    expect(assistant.toolCalls.map((tc) => tc.kind)).toEqual(['classify', 'retrieve']);
  });

  it('RESOLVE_TOOL_PLAN en auto con clarification sólo cierra classify', () => {
    let state = initialState();
    state = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u-cl',
      assistantId: 'a-cl',
      text: 'auto',
      mode: 'auto',
      createdAt: Date.now(),
    });
    const next = threadReducer(state, {
      type: 'RESOLVE_TOOL_PLAN',
      envelope: {
        request_id: 'r-cl',
        requested_mode: 'auto',
        resolved_mode: 'clarification',
        evidence: [],
        metadata: {},
        result: {
          kind: 'clarification',
          message: 'Necesito más contexto.',
          missing_fields: ['convention'],
        },
      },
      requested_mode: 'auto',
    });
    const assistant = next.messages[1];
    if (!assistant || assistant.role !== 'assistant') {
      throw new Error('assistant missing');
    }
    expect(assistant.toolCalls.map((tc) => tc.kind)).toEqual(['classify']);
    expect(assistant.toolCalls[0]?.status).toBe('done');
  });

  it('RESOLVE_TOOL_PLAN no muta nada si requested_mode no es auto', () => {
    let state = initialState();
    state = threadReducer(state, {
      type: 'SUBMIT',
      messageId: 'u-n',
      assistantId: 'a-n',
      text: 'q',
      mode: 'question',
      createdAt: Date.now(),
    });
    const before = state.messages[1];
    const next = threadReducer(state, {
      type: 'RESOLVE_TOOL_PLAN',
      envelope: {
        request_id: 'r-n',
        requested_mode: 'question',
        resolved_mode: 'question',
        evidence: [],
        metadata: {},
        result: {
          kind: 'question',
          status: 'answered',
          blocks: [{ text: 't', evidence_ids: [] }],
          trace_id: null,
        },
      },
      requested_mode: 'question',
    });
    expect(next.messages[1]).toBe(before);
  });
});
