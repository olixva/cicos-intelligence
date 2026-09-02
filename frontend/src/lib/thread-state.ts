import { claimSummaryText, type ClaimResultView } from '@/lib/claim-format';
import type {
  EnvelopeRequest,
  EnvelopeResponse,
  EvidenceItem,
  UiMode,
} from '@/api/queries';
import { derivePayloadForKind, type ToolCallKind } from '@/lib/tool-call-payload';

/** Re-export del tipo UiMode para que callers no necesiten importar queries.ts. */
export type { UiMode };

/**
 * thread-state.ts — reducer puro del thread + estado del stream.
 *
 * Diseñado para que las acciones se deriven 1:1 de los eventos del
 * streaming-client (`StreamingEvent`) más las acciones del usuario
 * (`SUBMIT`, `CANCEL`, `OPEN_PDF`, `CLOSE_PDF`). El reducer es puro;
 * el hook `useThread` (en este mismo archivo) lo conecta al ciclo
 * de vida real con fetch + AbortController.
 *
 * Decisión sobre `@assistant-ui/react`: el runtime oficial asume un
 * transporte HTTP con shape distinto al SSE del backend
 * (`started | stage | completed | failed`). Acoplarnos a su runtime
 * requeriría adaptar el contrato del backend o construir un adapter
 * no trivial. Hemos decidido implementar el thread manualmente sobre
 * `eventsource-parser`, que es la elección del spec UX v2 y la que ya
 * usaba `use-query-stream.ts` del scaffold anterior. Documentado en
 * el commit body de la fase.
 */

// =====================================================================
//  Tipos públicos
// =====================================================================

/** Tipos de tool calls que el chat agéntico puede mostrar.
 *  La definición vive junto al constructor de payloads compartido para que
 *  ambos caminos (modo explícito y Automático) no puedan divergir. */
export type { ToolCallKind };

/** Estado de un tool call: pending → done | error. */
export type ToolCallStatus = 'pending' | 'done' | 'error';

export interface ToolCall<TPayload = unknown> {
  /** Identificador único local (uuid). */
  id: string;
  /** Tipo discriminado — usado por ToolCallCard para sub-renderizar. */
  kind: ToolCallKind;
  /** Etiqueta visible mientras está pending. */
  label: string;
  /** Estado del tool call. */
  status: ToolCallStatus;
  /** Payload específico del kind (chunks, decisión, …). */
  payload?: TPayload;
  /** Duración en ms si ha terminado. */
  durationMs?: number;
  /** Mensaje de error si status === 'error'. */
  errorMessage?: string;
  /** Inicio en epoch ms. */
  startedAt: number;
}

export interface CitationRef {
  evidenceId: string;
  documentHash: string;
  pdfPage: number;
  /** Texto del bloque del que viene la cita (snippet). */
  snippet?: string;
  /** Texto corto para el chip. */
  label?: string;
}

export interface MessageUser {
  id: string;
  role: 'user';
  /** Texto enviado. */
  text: string;
  /** Modo elegido. */
  mode: UiMode;
  /** Timestamp epoch ms. */
  createdAt: number;
}

export interface MessageAssistant {
  id: string;
  role: 'assistant';
  /** Estado del streaming de la respuesta. */
  status: 'streaming' | 'done' | 'error';
  /** Bloque de texto acumulado mientras llega streaming. */
  streamedText: string;
  /** Tool calls emitidos antes del texto (derivan de los stages del backend). */
  toolCalls: ToolCall[];
  /** Respuesta final cuando status === 'done'. */
  envelope?: EnvelopeResponse;
  /** Citas extraídas del envelope (cuando llega `completed`). */
  citations: CitationRef[];
  /** requestId del backend si está disponible. */
  requestId?: string;
  /** Mensaje de error si status === 'error'. */
  errorMessage?: string;
  /** Inicio en epoch ms. */
  createdAt: number;
}

export type ThreadMessage = MessageUser | MessageAssistant;

export interface OpenPdfTarget {
  /** Source de la evidencia que abrió el PDF. */
  evidence: EvidenceItem;
  /** Snippet asociado, si lo hay. */
  snippet?: string;
}

export interface ThreadState {
  /** Mensajes del thread activo (vista operativa). */
  messages: ThreadMessage[];
  /** Mensajes por hilo — fuente de verdad cuando el usuario cambia de hilo. */
  threadMessages: Record<string, ThreadMessage[]>;
  /** Id de sesión Langfuse por hilo. */
  threadSessionIds: Record<string, string>;
  /** Modo vigente por hilo. */
  threadModes: Record<string, UiMode>;
  /** Mensaje asistente en curso (referencia para el reducer). */
  activeAssistantId: string | null;
  /** ¿Hay un stream activo? */
  isStreaming: boolean;
  /** Tool calls pendientes (cola de creación). */
  pendingToolCalls: ToolCallKind[];
  /** PDF overlay target — null = cerrado. */
  openPdf: OpenPdfTarget | null;
  /** Request id "actual" para el footer (mientras no hay done). */
  pendingRequestId?: string;
  /** Modo vigente (persistido). */
  mode: UiMode;
  /** Lista de hilos persistidos. */
  threads: ThreadSummary[];
  /** Hilo activo en el sidebar. */
  activeThreadId: string;
}

export interface ThreadSummary {
  id: string;
  title: string;
  updatedAt: number;
}

// =====================================================================
//  Acciones
// =====================================================================

export type ThreadAction =
  | { type: 'HYDRATE_MODE'; mode: UiMode }
  | {
      type: 'HYDRATE_THREADS';
      threads: ThreadSummary[];
      activeThreadId: string;
      threadMessages: Record<string, ThreadMessage[]>;
      threadSessionIds: Record<string, string>;
      threadModes: Record<string, UiMode>;
    }
  | { type: 'NEW_THREAD'; id: string; title?: string }
  | { type: 'SELECT_THREAD'; id: string }
  | { type: 'SUBMIT'; messageId: string; assistantId: string; text: string; mode: UiMode; createdAt: number }
  | { type: 'STREAM_STARTED'; requestId: string; mode: UiMode }
  | { type: 'TOOL_CALL_PENDING'; kind: ToolCallKind; label: string; createdAt: number }
  | { type: 'TOOL_CALL_DONE'; id: string; durationMs?: number; payload?: unknown }
  | { type: 'TOOL_CALL_ERROR'; id: string; message: string }
  | { type: 'STREAM_TEXT'; delta: string }
  | { type: 'STREAM_COMPLETED'; response: EnvelopeResponse; requestId: string }
  | { type: 'STREAM_FAILED'; message: string; requestId: string }
  | { type: 'STREAM_ABORTED' }
  | { type: 'OPEN_PDF'; target: OpenPdfTarget }
  | { type: 'CLOSE_PDF' }
  | { type: 'CANCEL' }
  | { type: 'RESOLVE_TOOL_PLAN'; envelope: EnvelopeResponse; requested_mode: UiMode };

// =====================================================================
//  Helpers
// =====================================================================

const DEFAULT_MODE: UiMode = 'auto';

function now(): number {
  return Date.now();
}

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function freshActiveAssistant(): MessageAssistant {
  return {
    id: uuid(),
    role: 'assistant',
    status: 'streaming',
    streamedText: '',
    toolCalls: [],
    citations: [],
    createdAt: now(),
  };
}

function defaultThreadSummary(): ThreadSummary[] {
  // Audit fix (T11): el sidebar ya no carga hilos mock. El historial se
  // hidrata desde localStorage en el mount y queda vacío si no hay
  // nada persistido. Cada hilo se crea bajo demanda con ``NEW_THREAD``.
  return [];
}

/** Título corto de un hilo, derivado de su primer mensaje. */
function threadTitle(text: string): string {
  const clean = text.trim().replace(/\s+/g, ' ');
  return clean.length > 48 ? `${clean.slice(0, 48).trimEnd()}…` : clean || 'Consulta';
}

export function initialState(mode: UiMode = DEFAULT_MODE): ThreadState {
  return {
    messages: [],
    threadMessages: {},
    threadSessionIds: {},
    threadModes: {},
    activeAssistantId: null,
    isStreaming: false,
    pendingToolCalls: [],
    openPdf: null,
    mode,
    threads: defaultThreadSummary(),
    activeThreadId: 'demo-1',
  };
}

// =====================================================================
//  Reducer puro
// =====================================================================

export function threadReducer(state: ThreadState, action: ThreadAction): ThreadState {
  // T11 — capture the next state in a variable so we can mirror the
  // active thread's message list into ``threadMessages`` before
  // returning. Without this the sidebar would still show the old
  // mock list and selecting another thread would clear the chat.
  const next = threadReducerInner(state, action);
  if (!next.activeThreadId) return next;
  if (next.threadMessages[next.activeThreadId] === next.messages) return next;
  return {
    ...next,
    threadMessages: { ...next.threadMessages, [next.activeThreadId]: next.messages },
  };
}

function threadReducerInner(state: ThreadState, action: ThreadAction): ThreadState {
  switch (action.type) {
    case 'HYDRATE_MODE':
      return { ...state, mode: action.mode };

    case 'HYDRATE_THREADS': {
      // T11 — restore the persisted thread list and the per-thread
      // message streams. The active thread's messages become the live
      // ``messages`` field so the chat view re-hydrates instantly.
      const targetId = action.activeThreadId;
      const targetMessages = action.threadMessages[targetId] ?? [];
      const targetMode = action.threadModes[targetId] ?? state.mode;
      // Preserve any in-flight streaming session by not clearing the
      // active assistant; the hydration is best-effort and must not
      // clobber a live call mid-stream.
      return {
        ...state,
        threads: action.threads,
        activeThreadId: targetId,
        threadMessages: action.threadMessages,
        threadSessionIds: action.threadSessionIds,
        threadModes: action.threadModes,
        messages: targetMessages,
        mode: targetMode,
      };
    }

    case 'NEW_THREAD': {
      // Abrir "nuevo chat" sobre un hilo que todavía no tiene mensajes no crea
      // nada: reutilizamos el hilo vacío en vez de acumular entradas idénticas
      // en la barra lateral.
      if (state.messages.length === 0 && state.activeThreadId) {
        return state;
      }
      const id = action.id;
      const summary: ThreadSummary = {
        id,
        // Sin título hasta que haya un primer mensaje del que derivarlo.
        title: action.title ?? '',
        updatedAt: now(),
      };
      return {
        ...state,
        messages: [],
        threadMessages: { ...state.threadMessages, [id]: [] },
        threadSessionIds: {
          ...state.threadSessionIds,
          [id]: state.threadSessionIds[id] ?? uuid(),
        },
        threadModes: { ...state.threadModes, [id]: state.mode },
        activeAssistantId: null,
        isStreaming: false,
        pendingToolCalls: [],
        openPdf: null,
        threads: [summary, ...state.threads],
        activeThreadId: id,
      };
    }

    case 'SELECT_THREAD': {
      // T11 fix: seleccionar restaura los mensajes del hilo elegido en
      // lugar de vaciarlos, para que el sidebar abra conversaciones reales.
      const targetId = action.id;
      const targetMessages = state.threadMessages[targetId] ?? [];
      const targetMode = state.threadModes[targetId] ?? state.mode;

      // Un hilo del que se sale sin haber escrito nada no llegó a existir como
      // conversación: se descarta al abandonarlo, igual que `NEW_THREAD` no
      // crea uno nuevo estando ya en uno vacío. Así la barra lateral sólo
      // enumera conversaciones reales.
      const leaving = state.activeThreadId;
      const discardEmpty = leaving !== null && leaving !== targetId && state.messages.length === 0;

      const threads = discardEmpty
        ? state.threads.filter((thread) => thread.id !== leaving)
        : state.threads;

      /** Copia el mapa sin la clave del hilo descartado. */
      function withoutLeaving<T>(map: Record<string, T>): Record<string, T> {
        if (!discardEmpty || leaving === null) return map;
        const next = { ...map };
        delete next[leaving];
        return next;
      }

      return {
        ...state,
        threads,
        threadMessages: withoutLeaving(state.threadMessages),
        threadSessionIds: withoutLeaving(state.threadSessionIds),
        threadModes: withoutLeaving(state.threadModes),
        activeThreadId: targetId,
        messages: targetMessages,
        mode: targetMode,
        activeAssistantId: null,
        isStreaming: false,
        pendingToolCalls: [],
        openPdf: null,
      };
    }

    case 'SUBMIT': {
      const userMsg: MessageUser = {
        id: action.messageId,
        role: 'user',
        text: action.text,
        mode: action.mode,
        createdAt: action.createdAt,
      };
      const assistant = freshActiveAssistant();
      assistant.id = action.assistantId;
      // `classify` sólo existe en modo 'auto': es la única situación en la que
      // el backend clasifica la intención, y la única en la que emite el stage
      // `dispatch`. En modos explícitos el usuario ya declaró el recorrido, así
      // que mostrar "Clasificando consulta…" afirmaba un trabajo inexistente.
      // En 'auto' el resto del plan se completa al recibir el envelope final
      // vía RESOLVE_TOOL_PLAN.
      const plan: ToolCallKind[] =
        action.mode === 'claim'
          ? ['check_rules', 'apply_decision']
          : action.mode === 'question'
            ? ['retrieve']
            : ['classify'];
      assistant.toolCalls = plan.map((kind) => ({
        id: uuid(),
        kind,
        label: labels[kind].pending,
        status: 'pending',
        startedAt: now(),
      }));
      // Un hilo entra en el historial cuando recibe su primer mensaje, no al
      // crearse: así la barra lateral sólo enumera conversaciones reales, y el
      // hilo activo inicial —que no tenía entrada propia— deja de perderse.
      const alreadyListed = state.threads.some((thread) => thread.id === state.activeThreadId);
      const threads = alreadyListed
        ? state.threads.map((thread) =>
            thread.id === state.activeThreadId
              ? { ...thread, title: thread.title || threadTitle(action.text), updatedAt: now() }
              : thread,
          )
        : [
            { id: state.activeThreadId, title: threadTitle(action.text), updatedAt: now() },
            ...state.threads,
          ];

      return {
        ...state,
        threads,
        messages: [...state.messages, userMsg, assistant],
        activeAssistantId: assistant.id,
        isStreaming: true,
        mode: action.mode,
        pendingToolCalls: plan,
        openPdf: null,
      };
    }

    case 'STREAM_STARTED':
      return {
        ...state,
        pendingRequestId: action.requestId,
      };

    case 'TOOL_CALL_PENDING': {
      if (!state.activeAssistantId) return state;
      const id = uuid();
      const toolCall: ToolCall = {
        id,
        kind: action.kind,
        label: action.label,
        status: 'pending',
        startedAt: action.createdAt,
      };
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.role === 'assistant' && m.id === state.activeAssistantId
            ? { ...m, toolCalls: [...m.toolCalls, toolCall] }
            : m,
        ),
        pendingToolCalls: state.pendingToolCalls.filter((k) => k !== action.kind),
      };
    }

    case 'TOOL_CALL_DONE': {
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.role === 'assistant'
            ? {
                ...m,
                toolCalls: m.toolCalls.map((tc) =>
                  tc.id === action.id
                    ? {
                        ...tc,
                        status: 'done' as const,
                        // Sólo se registra una duración cuando procede de una
                        // medición real del backend. Antes se escribía 0 ms o
                        // se repetía el total en cada tarjeta.
                        ...(action.durationMs === undefined
                          ? {}
                          : { durationMs: action.durationMs }),
                        payload: action.payload,
                      }
                    : tc,
                ),
              }
            : m,
        ),
      };
    }

    case 'TOOL_CALL_ERROR': {
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.role === 'assistant'
            ? {
                ...m,
                toolCalls: m.toolCalls.map((tc) =>
                  tc.id === action.id ? { ...tc, status: 'error', errorMessage: action.message } : tc,
                ),
              }
            : m,
        ),
      };
    }

    case 'STREAM_TEXT': {
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.role === 'assistant' && m.id === state.activeAssistantId
            ? { ...m, streamedText: m.streamedText + action.delta }
            : m,
        ),
      };
    }

    case 'STREAM_COMPLETED': {
      const envelope = action.response;
      const citations = extractCitations(envelope);
      return {
        ...state,
        isStreaming: false,
        pendingToolCalls: [],
        pendingRequestId: undefined,
        messages: state.messages.map((m) => {
          if (m.role !== 'assistant' || m.id !== state.activeAssistantId) return m;
          const text = mergeStreamedText(m.streamedText, envelope);
          return {
            ...m,
            status: 'done',
            streamedText: text,
            envelope,
            citations,
            requestId: envelope.request_id ?? action.requestId,
          };
        }),
      };
    }

    case 'STREAM_FAILED':
      return {
        ...state,
        isStreaming: false,
        pendingToolCalls: [],
        pendingRequestId: undefined,
        messages: state.messages.map((m) => {
          if (m.role !== 'assistant' || m.id !== state.activeAssistantId) return m;
          return { ...m, status: 'error', errorMessage: action.message };
        }),
      };

    case 'STREAM_ABORTED':
      return {
        ...state,
        isStreaming: false,
        pendingToolCalls: [],
        pendingRequestId: undefined,
      };

    case 'OPEN_PDF':
      return { ...state, openPdf: action.target };

    case 'CLOSE_PDF':
      return { ...state, openPdf: null };

    case 'CANCEL':
      return {
        ...state,
        isStreaming: false,
        pendingToolCalls: [],
        messages: state.messages.filter((m) => m.id !== state.activeAssistantId),
      };

    case 'RESOLVE_TOOL_PLAN': {
      // Sólo aplica a modo 'auto': reescribe el plan de tool calls del
      // assistant activo para que refleje el resolved_mode del envelope.
      // Finding G1 #2 — cerrar el classify pendiente y añadir los cards
      // que faltan (claim → check_rules + apply_decision, question →
      // retrieve, clarification → sólo classify).
      if (action.requested_mode !== 'auto') return state;
      if (!state.activeAssistantId) return state;

      const envelope = action.envelope;
      const resolved = envelope.resolved_mode;
      const required: ToolCallKind[] = ['classify'];
      if (resolved === 'claim') {
        required.push('check_rules', 'apply_decision');
      } else if (resolved === 'question') {
        required.push('retrieve');
      }

      const updatedMessages = state.messages.map((m) => {
        if (m.role !== 'assistant' || m.id !== state.activeAssistantId) return m;
        const existingKinds = new Set(m.toolCalls.map((tc) => tc.kind));
        const updated: ToolCall[] = m.toolCalls.map((tc) => {
          if (tc.status !== 'pending') return tc;
          if (!required.includes(tc.kind)) return tc;
          return {
            ...tc,
            status: 'done' as const,
            payload: derivePayloadForKind(tc.kind, envelope),
          };
        });
        for (const kind of required) {
          if (existingKinds.has(kind)) continue;
          updated.push({
            id: uuid(),
            kind,
            label: labels[kind].done,
            status: 'done',
            payload: derivePayloadForKind(kind, envelope),
            startedAt: m.createdAt,
          });
        }
        updated.sort((a, b) => required.indexOf(a.kind) - required.indexOf(b.kind));
        return { ...m, toolCalls: updated };
      });

      return { ...state, messages: updatedMessages };
    }
  }
}

// =====================================================================
//  Etiquetas legibles para los tool calls
// =====================================================================

export const labels: Record<ToolCallKind, { pending: string; done: string }> = {
  classify: { pending: 'Clasificando consulta…', done: 'Consulta clasificada' },
  retrieve: { pending: 'Recuperando evidencia…', done: 'Evidencia recuperada' },
  check_rules: { pending: 'Verificando reglas del convenio…', done: 'Reglas evaluadas' },
  apply_decision: { pending: 'Aplicando decisión…', done: 'Decisión emitida' },
};

// =====================================================================
//  Utilidades
// =====================================================================

/**
 * Deriva el payload que se asocia a un tool call cerrado por
 * `RESOLVE_TOOL_PLAN`. Réplica de `derivePayload` en `routes/_index.tsx`
 * para mantener el reducer puro (no cruza con código del route).
 */
function extractCitations(envelope: EnvelopeResponse): CitationRef[] {
  const result = envelope.result;
  if (!result || result.kind !== 'question') return [];
  const blocks = (result.blocks ?? []) as Array<{ text?: string; evidence_ids?: string[] }>;
  const evidence = envelope.evidence ?? [];
  const byId = new Map(evidence.map((e) => [e.evidence_id, e]));
  // Dedupe por tupla (evidenceId, pdfPage) — varios bloques pueden citar
  // el mismo chunk y el render usa `${evidenceId}-${pdfPage}` como React
  // key (assistant-message.tsx), así que duplicados provocaban
  // "Encountered two children with the same key". El Map preserva el
  // orden de inserción, así que mantenemos el primer bloque que cita
  // cada par (Finding G1 #1).
  const byKey = new Map<string, CitationRef>();
  for (const block of blocks) {
    const ids = Array.isArray(block.evidence_ids) ? block.evidence_ids : [];
    for (const id of ids) {
      const ev = byId.get(id);
      if (!ev) continue;
      const key = `${ev.evidence_id}-${ev.pdf_page}`;
      if (byKey.has(key)) continue;
      byKey.set(key, {
        evidenceId: ev.evidence_id,
        documentHash: ev.document_hash,
        pdfPage: ev.pdf_page,
        snippet: block.text,
      });
    }
  }
  return Array.from(byKey.values());
}

/** Combina el texto streamed con el envelope final cuando llega. */
function mergeStreamedText(streamed: string, envelope: EnvelopeResponse): string {
  // Si el stream ya acumuló texto, lo conservamos. Si no, derivamos del envelope.
  if (streamed.length > 0) return streamed;
  const result = envelope.result;
  if (!result) return '';
  if (result.kind === 'question') {
    const blocks = (result.blocks ?? []) as Array<{ text?: string }>;
    const answer = blocks.map((b) => b.text ?? '').filter(Boolean).join('\n\n');
    if (answer) return answer;
    if (result.status === 'out_of_scope') {
      return 'Esta consulta queda fuera del alcance de la fuente documental suministrada. No puedo responderla con fiabilidad usando este manual.';
    }
    if (result.status === 'insufficient_evidence') {
      return 'No hay evidencia suficiente en el manual suministrado para responder esta consulta.';
    }
    if (result.status === 'partial') {
      return 'La respuesta sólo puede determinarse parcialmente con la evidencia recuperada.';
    }
    return 'No se ha generado una respuesta textual para esta consulta.';
  }
  if (result.kind === 'clarification') return result.message;
  if (result.kind === 'claim') {
    // Redactado en castellano con las condiciones, lo que falta y las
    // contradicciones. Antes devolvía los enums crudos del backend.
    return claimSummaryText(result as unknown as ClaimResultView);
  }
  return '';
}

/** Devuelve un `EnvelopeRequest` ya listo para enviar a partir de un texto. */
export function buildRequest(
  text: string,
  mode: UiMode,
  language: 'es' | 'en' = 'es',
  sessionId: string | null = null,
  clarifications: string[] = [],
  continuation: { threadId?: string | null; resume?: boolean } = {},
): EnvelopeRequest {
  return {
    text: text.trim(),
    mode,
    language,
    stream: true,
    session_id: sessionId,
    ...(clarifications.length > 0
      ? { clarifications: clarifications as EnvelopeRequest['clarifications'] }
      : {}),
    ...(continuation.threadId ? { thread_id: continuation.threadId } : {}),
    ...(continuation.resume ? { resume: true } : {}),
  } as EnvelopeRequest;
}
