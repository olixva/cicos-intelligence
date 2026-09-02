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

describe('un hilo vacío no sobrevive a salir de él', () => {
  /** Hilo inicial con mensajes + un `t2` vacío y activo. Devuelve ambos ids. */
  function conHiloVacioActivo(): { estado: ThreadState; conMensajes: string } {
    const base = initialState();
    const conMensajes = base.activeThreadId as string;
    const conversacion = submit(base, 'question');
    return {
      estado: threadReducer(conversacion, { type: 'NEW_THREAD', id: 't2' }),
      conMensajes,
    };
  }

  it('descarta el hilo vacío al cambiar a otro del historial', () => {
    const { estado, conMensajes } = conHiloVacioActivo();
    expect(estado.activeThreadId).toBe('t2');
    expect(estado.threads.map((t) => t.id)).toContain('t2');

    const despues = threadReducer(estado, { type: 'SELECT_THREAD', id: conMensajes });
    expect(despues.activeThreadId).toBe(conMensajes);
    expect(despues.threads.map((t) => t.id)).not.toContain('t2');
  });

  it('no deja rastro del hilo vacío en los mapas del estado', () => {
    const { estado, conMensajes } = conHiloVacioActivo();
    const despues = threadReducer(estado, { type: 'SELECT_THREAD', id: conMensajes });
    expect(despues.threadMessages['t2']).toBeUndefined();
    expect(despues.threadSessionIds['t2']).toBeUndefined();
    expect(despues.threadModes['t2']).toBeUndefined();
  });

  it('conserva el hilo de origen cuando sí tenía mensajes', () => {
    const { estado, conMensajes } = conHiloVacioActivo();
    // Salimos de `t2` (vacío) hacia el hilo con mensajes: `t2` desaparece,
    // pero el que tiene conversación se queda.
    const despues = threadReducer(estado, { type: 'SELECT_THREAD', id: conMensajes });
    expect(despues.threads.map((t) => t.id)).toContain(conMensajes);
  });

  it('restaura los mensajes del hilo elegido', () => {
    const { estado, conMensajes } = conHiloVacioActivo();
    const despues = threadReducer(estado, { type: 'SELECT_THREAD', id: conMensajes });
    expect(despues.messages.length).toBeGreaterThan(0);
  });
});

describe('un hilo entra en el historial al recibir su primer mensaje', () => {
  it('lista el hilo activo inicial, que antes no tenía entrada propia', () => {
    const base = initialState();
    expect(base.threads).toHaveLength(0);

    const conversacion = submit(base, 'question');
    expect(conversacion.threads.map((t) => t.id)).toEqual([base.activeThreadId]);
  });

  it('titula el hilo con el texto del primer mensaje, no con un contador', () => {
    const conversacion = threadReducer(initialState(), {
      type: 'SUBMIT',
      messageId: 'u1',
      assistantId: 'a1',
      text: '¿Cuándo se aplica el convenio CIDE?',
      mode: 'question',
      createdAt: 1_000,
    });
    expect(conversacion.threads[0].title).toBe('¿Cuándo se aplica el convenio CIDE?');
  });

  it('recorta un primer mensaje largo en vez de desbordar la barra lateral', () => {
    const largo = 'Durante una lluvia intensa se produce una colisión múltiple en la autopista';
    const conversacion = threadReducer(initialState(), {
      type: 'SUBMIT',
      messageId: 'u1',
      assistantId: 'a1',
      text: largo,
      mode: 'claim',
      createdAt: 1_000,
    });
    const title = conversacion.threads[0].title;
    expect(title.length).toBeLessThanOrEqual(49);
    expect(title.endsWith('…')).toBe(true);
  });

  it('no lista un hilo que nunca recibió un mensaje', () => {
    const conMensajes = submit(initialState(), 'question');
    const nuevo = threadReducer(conMensajes, { type: 'NEW_THREAD', id: 't2' });
    // `t2` existe como hilo activo pero aún no es una conversación; al volver
    // al anterior desaparece sin dejar rastro.
    const vuelta = threadReducer(nuevo, {
      type: 'SELECT_THREAD',
      id: conMensajes.activeThreadId,
    });
    expect(vuelta.threads).toHaveLength(1);
  });
});
