/**
 * Defectos observados por el usuario en la app, fijados como contrato.
 *
 * Los tres primeros son de honestidad: la interfaz no puede afirmar que
 * clasificó cuando no clasificó, ni mostrar duraciones que no midió.
 */
import { describe, expect, it } from 'vitest';
import { threadReducer, initialState, type ThreadState } from '@/lib/thread-state';

function submit(state: ThreadState, mode: 'auto' | 'question' | 'claim'): ThreadState {
  return threadReducer(state, {
    type: 'SUBMIT',
    messageId: 'u1',
    assistantId: 'a1',
    text: 'texto',
    mode,
    createdAt: 1_000,
  });
}

function toolKinds(state: ThreadState): string[] {
  const assistant = state.messages.find((m) => m.role === 'assistant');
  return assistant && assistant.role === 'assistant'
    ? assistant.toolCalls.map((tc) => tc.kind)
    : [];
}

describe('el plan de tool calls refleja lo que el backend hace de verdad', () => {
  it('no muestra "clasificando" cuando el usuario ya eligió modo siniestro', () => {
    // El backend sólo emite el stage `dispatch` en modo auto. Si el usuario
    // ya declaró el modo, no hay clasificación que mostrar.
    expect(toolKinds(submit(initialState(), 'claim'))).not.toContain('classify');
  });

  it('no muestra "clasificando" cuando el usuario ya eligió modo pregunta', () => {
    expect(toolKinds(submit(initialState(), 'question'))).not.toContain('classify');
  });

  it('sí muestra "clasificando" en modo automático, que es cuando ocurre', () => {
    expect(toolKinds(submit(initialState(), 'auto'))).toContain('classify');
  });

  it('conserva las etapas propias de cada modo explícito', () => {
    expect(toolKinds(submit(initialState(), 'question'))).toEqual(['retrieve']);
    expect(toolKinds(submit(initialState(), 'claim'))).toEqual([
      'check_rules',
      'apply_decision',
    ]);
  });
});

describe('las duraciones nunca se inventan', () => {
  it('un tool call cerrado sin medición real no expone durationMs', () => {
    // El backend no emite todavía un stage por etapa, así que la interfaz
    // no puede saber cuánto tardó cada una. Antes escribía 0 ms o repetía
    // el total en las tres tarjetas.
    const submitted = submit(initialState(), 'claim');
    const assistant = submitted.messages.find((m) => m.role === 'assistant');
    const id = assistant && assistant.role === 'assistant' ? assistant.toolCalls[0].id : '';
    const done = threadReducer(submitted, { type: 'TOOL_CALL_DONE', id, payload: {} });
    const after = done.messages.find((m) => m.role === 'assistant');
    const call = after && after.role === 'assistant' ? after.toolCalls[0] : undefined;
    expect(call?.status).toBe('done');
    expect(call?.durationMs).toBeUndefined();
  });

  it('acepta una duración cuando procede realmente del backend', () => {
    const submitted = submit(initialState(), 'claim');
    const assistant = submitted.messages.find((m) => m.role === 'assistant');
    const id = assistant && assistant.role === 'assistant' ? assistant.toolCalls[0].id : '';
    const done = threadReducer(submitted, {
      type: 'TOOL_CALL_DONE',
      id,
      durationMs: 1234,
      payload: {},
    });
    const after = done.messages.find((m) => m.role === 'assistant');
    const call = after && after.role === 'assistant' ? after.toolCalls[0] : undefined;
    expect(call?.durationMs).toBe(1234);
  });
});

describe('hilos vacíos', () => {
  it('no acumula un hilo nuevo cuando el actual todavía está vacío', () => {
    // Abrir "nuevo chat" dos veces seguidas sin escribir nada no debe dejar
    // dos entradas idénticas en la barra lateral.
    const first = threadReducer(initialState(), { type: 'NEW_THREAD', id: 't1' });
    const second = threadReducer(first, { type: 'NEW_THREAD', id: 't2' });
    expect(second.threads.length).toBe(first.threads.length);
    expect(second.activeThreadId).toBe(first.activeThreadId);
  });

  it('sí abre un hilo nuevo cuando el actual tiene mensajes', () => {
    const withMessages = submit(
      threadReducer(initialState(), { type: 'NEW_THREAD', id: 't1' }),
      'question',
    );
    const next = threadReducer(withMessages, { type: 'NEW_THREAD', id: 't2' });
    expect(next.threads.length).toBe(withMessages.threads.length + 1);
    expect(next.activeThreadId).toBe('t2');
  });
});
