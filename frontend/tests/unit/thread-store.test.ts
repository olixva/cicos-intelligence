/**
 * Tests for the real thread persistence (T11).
 *
 * The frontend audit finding (the sidebar mock data shows fake
 * conversations) is fixed by replacing the mock thread list with
 * localStorage-backed persistence. These tests cover the
 * serialisation round-trip and the contract the reducer expects.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

type PersistedPayload = {
  version: number;
  threads: Array<{
    summary: { id: string; title: string; updatedAt: number };
    session_id: string;
    mode: string;
    messages: unknown[];
  }>;
  active_thread_id: string | null;
};

const STORAGE_KEY = 'cicos.threads.v1';

interface FakeStorage {
  store: Map<string, string>;
  window: { localStorage: FakeLocalStorage };
}

interface FakeLocalStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
  clear(): void;
}

function installFakeStorage(): FakeStorage {
  const store = new Map<string, string>();
  const localStorage: FakeLocalStorage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
    clear: () => store.clear(),
  };
  const fakeWindow = { localStorage };
  (globalThis as unknown as { window: typeof fakeWindow }).window = fakeWindow;
  return { store, window: fakeWindow };
}

describe('thread-store (T11)', () => {
  let storage: FakeStorage;
  beforeEach(() => {
    storage = installFakeStorage();
  });
  afterEach(() => {
    storage.store.clear();
  });

  it('returns empty hydration when storage is empty', async () => {
    const { loadThreadHydration } = await import('@/lib/thread-store');
    const hydration = loadThreadHydration();
    expect(hydration).toEqual({
      threads: [],
      activeThreadId: null,
      threadRecords: {},
    });
  });

  it('round-trips threads and messages', async () => {
    const { loadThreadHydration, persistThreadState } = await import(
      '@/lib/thread-store'
    );
    const state = {
      activeThreadId: 't-1',
      messages: [
        {
          id: 'u-1',
          role: 'user',
          text: 'Hola',
          mode: 'question',
          createdAt: 1700000000000,
        },
        {
          id: 'a-1',
          role: 'assistant',
          status: 'done',
          streamedText: '',
          toolCalls: [],
          citations: [],
          createdAt: 1700000000100,
          content: 'Respuesta.',
        },
      ],
      threads: [{ id: 't-1', title: 'Pregunta 1', updatedAt: 1700000000100 }],
      mode: 'question',
    } as const;
    persistThreadState(state as never, {});
    const hydration = loadThreadHydration();
    expect(hydration.threads.map((thread) => thread.id)).toEqual(['t-1']);
    const record = hydration.threadRecords['t-1']!;
    expect(record.session_id).toBeTruthy();
    expect(record.messages).toHaveLength(2);
    expect((record.messages[0] as { text: string }).text).toBe('Hola');
  });

  it('versioned payload survives a manual write', async () => {
    const { loadThreadHydration } = await import('@/lib/thread-store');
    const raw: PersistedPayload = {
      version: 1,
      threads: [
        {
          summary: { id: 't-x', title: 'x', updatedAt: 1 },
          session_id: 's-x',
          mode: 'auto',
          messages: [],
        },
      ],
      active_thread_id: 't-x',
    };
    storage.window.localStorage.setItem(STORAGE_KEY, JSON.stringify(raw));
    const hydration = loadThreadHydration();
    expect(hydration.activeThreadId).toBe('t-x');
    expect(hydration.threadRecords['t-x']?.session_id).toBe('s-x');
  });

  it('discards corrupted payloads silently', async () => {
    const { loadThreadHydration } = await import('@/lib/thread-store');
    storage.window.localStorage.setItem(STORAGE_KEY, 'not-json{');
    storage.window.localStorage.setItem(
      'cicos.threads.v2',
      JSON.stringify({ version: 2, threads: [] })
    );
    const hydration = loadThreadHydration();
    expect(hydration).toEqual({
      threads: [],
      activeThreadId: null,
      threadRecords: {},
    });
  });

  it('assigns a fresh session_id when the active thread has none', async () => {
    const { persistThreadState, loadThreadHydration } = await import(
      '@/lib/thread-store'
    );
    // Con un mensaje: un hilo vacío ya no se persiste, porque todavía no es
    // una conversación.
    const state = {
      activeThreadId: 't-fresh',
      messages: [{ id: 'u1', role: 'user', text: 'hola', mode: 'auto', createdAt: 1 }],
      threads: [{ id: 't-fresh', title: 'nuevo', updatedAt: 1 }],
      mode: 'auto',
    } as const;
    persistThreadState(state as never, {});
    const hydration = loadThreadHydration();
    expect(hydration.threadRecords['t-fresh']?.session_id).toBeTruthy();
  });

  it('no persiste un hilo sin mensajes', async () => {
    const { persistThreadState, loadThreadHydration } = await import('@/lib/thread-store');
    const state = {
      activeThreadId: 't-vacio',
      messages: [],
      threads: [{ id: 't-vacio', title: '', updatedAt: 1 }],
      mode: 'auto',
    } as const;
    persistThreadState(state as never, {});
    expect(loadThreadHydration().threadRecords['t-vacio']).toBeUndefined();
  });

  it('titula desde el primer mensaje en vez de desde el identificador', async () => {
    const { persistThreadState, loadThreadHydration } = await import('@/lib/thread-store');
    const state = {
      activeThreadId: 'demo-1',
      messages: [
        { id: 'u1', role: 'user', text: '¿Cuándo se aplica el CIDE?', mode: 'auto', createdAt: 1 },
      ],
      threads: [],
      mode: 'auto',
    } as const;
    persistThreadState(state as never, {});
    const title = loadThreadHydration().threadRecords['demo-1']?.summary.title;
    expect(title).toBe('¿Cuándo se aplica el CIDE?');
    expect(title).not.toContain('Hilo demo-1');
  });
});
