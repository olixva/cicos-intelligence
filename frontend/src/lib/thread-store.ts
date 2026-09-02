/**
 * Real thread persistence.
 *
 * Replaces the mock thread list with localStorage-backed storage:
 * - Each thread carries a stable ``session_id`` so traces in Langfuse
 *   can be stitched together across reloads.
 * - Per-thread messages survive page reloads and are restored when
 *   the user clicks a thread in the sidebar.
 * - Failures are silent (the thread list simply resets) so a quota
 *   exceeded or a sandbox restriction never crashes the chat.
 *
 * The store deliberately keeps the message format identical to the
 * reducer state so the persisted shape round-trips through the
 * frontend without translation.
 */

import type {
  ThreadMessage,
  ThreadSummary,
  ThreadState,
  UiMode,
} from './thread-state';

const STORAGE_KEY = 'cicos.threads.v1';

interface PersistedThread {
  summary: ThreadSummary;
  session_id: string;
  mode: UiMode;
  messages: ThreadMessage[];
}

interface PersistedPayload {
  version: 1;
  threads: PersistedThread[];
  active_thread_id: string | null;
}

export interface HydrationResult {
  threads: ThreadSummary[];
  activeThreadId: string | null;
  threadRecords: Record<string, PersistedThread>;
}

function isThreadMessage(value: unknown): value is ThreadMessage {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as { role?: unknown; id?: unknown };
  if (typeof candidate.id !== 'string') return false;
  return candidate.role === 'user' || candidate.role === 'assistant';
}

function readPersisted(): PersistedPayload | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    const candidate = parsed as Partial<PersistedPayload>;
    if (candidate.version !== 1 || !Array.isArray(candidate.threads)) return null;
    return {
      version: 1,
      threads: candidate.threads.filter(
        (entry): entry is PersistedThread =>
          !!entry &&
          typeof entry === 'object' &&
          typeof entry.session_id === 'string' &&
          typeof entry.mode === 'string' &&
          Array.isArray(entry.messages) &&
          entry.messages.every(isThreadMessage) &&
          !!entry.summary &&
          typeof entry.summary.id === 'string',
      ),
      active_thread_id:
        typeof candidate.active_thread_id === 'string'
          ? candidate.active_thread_id
          : null,
    };
  } catch {
    return null;
  }
}

function writePersisted(payload: PersistedPayload): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    /* ignore quota / sandbox errors */
  }
}

export function loadThreadHydration(): HydrationResult {
  const persisted = readPersisted();
  if (persisted === null) {
    return { threads: [], activeThreadId: null, threadRecords: {} };
  }
  const records: Record<string, PersistedThread> = {};
  const summaries: ThreadSummary[] = [];
  for (const entry of persisted.threads) {
    records[entry.summary.id] = entry;
    summaries.push(entry.summary);
  }
  return {
    threads: summaries,
    activeThreadId:
      persisted.active_thread_id && records[persisted.active_thread_id]
        ? persisted.active_thread_id
        : (summaries[0]?.id ?? null),
    threadRecords: records,
  };
}

export function persistThreadState(
  state: ThreadState,
  threadRecords: Record<string, PersistedThread>,
): void {
  const records: Record<string, PersistedThread> = { ...threadRecords };
  // Always overwrite the active thread with the current in-memory
  // messages so streaming deltas land in storage even before the
  // STREAM_COMPLETED action fires.
  if (state.activeThreadId) {
    if (state.messages.length === 0) {
      // Un hilo sin mensajes no es una conversación y no se guarda: antes
      // sobrevivía a la recarga y reaparecía en la barra lateral con un
      // título inventado a partir de su identificador.
      delete records[state.activeThreadId];
    } else {
      records[state.activeThreadId] = {
        summary: ensureSummary(state),
        session_id: records[state.activeThreadId]?.session_id ?? makeSessionId(),
        mode: state.mode,
        messages: state.messages,
      };
    }
  }
  // Ningún hilo persistido puede quedar vacío, aunque venga de una versión
  // anterior del almacenamiento.
  for (const [id, record] of Object.entries(records)) {
    if (record.messages.length === 0) delete records[id];
  }
  const payload: PersistedPayload = {
    version: 1,
    threads: Object.values(records).sort((a, b) => b.summary.updatedAt - a.summary.updatedAt),
    active_thread_id: state.activeThreadId,
  };
  writePersisted(payload);
}

function ensureSummary(state: ThreadState): ThreadSummary {
  const existing = state.threads.find((summary) => summary.id === state.activeThreadId);
  if (existing && existing.title.trim()) return existing;
  // El reducer titula cada hilo con su primer mensaje al enviarlo; este
  // camino sólo cubre estados heredados. Derivar del texto real evita el
  // antiguo "Hilo demo-1", que no decía nada de la conversación.
  const firstUser = state.messages.find((message) => message.role === 'user');
  const source = firstUser && firstUser.role === 'user' ? firstUser.text.trim() : '';
  const clean = source.replace(/\s+/g, ' ');
  return {
    id: state.activeThreadId,
    title: clean.length > 48 ? `${clean.slice(0, 48).trimEnd()}…` : clean || 'Consulta',
    updatedAt: Date.now(),
  };
}

function makeSessionId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `s-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
