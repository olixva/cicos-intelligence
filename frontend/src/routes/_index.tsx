import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ThreadSidebar } from '@/components/sidebar/thread-sidebar';
import { Thread } from '@/components/thread/thread';
import { Composer } from '@/components/composer/composer';
import { EmptyState } from '@/components/empty-state/empty-state';
import { PdfOverlay } from '@/components/pdf-overlay/pdf-overlay';
import { BannerSystem } from '@/components/banner-system';
import { Footer } from '@/components/footer';
import { DotPattern } from '@/components/ui/dot-pattern';
import { IngestionPanel } from '@/components/admin/ingestion-panel';
import {
  getIngestionSnapshot,
  getIngestionExtractions,
  startIngestion,
  subscribeToIngestion,
  type IngestionSnapshot,
} from '@/api/ingestion';
import { getDemoCases, type DemoCase } from '@/api/queries';
import { streamQuery, type StreamingEvent } from '@/lib/streaming-client';
import {
  buildRequest,
  initialState,
  threadReducer,
  type CitationRef,
  type MessageAssistant,
  type ThreadAction,
  type ThreadMessage,
  type UiMode,
} from '@/lib/thread-state';
import {
  loadThreadHydration,
  persistThreadState,
} from '@/lib/thread-store';
import type { EnvelopeResponse, EvidenceItem } from '@/api/queries';
import { derivePayloadForKind } from '@/lib/tool-call-payload';

/**
 * IndexRoute — layout del chat agéntico.
 *
 * Compone:
 *   - BannerSystem arriba (estado del backend)
 *   - ThreadSidebar (≥1280px) | Header móvil
 *   - Thread (scroll vertical) + EmptyState si vacío
 *   - Composer fijo abajo
 *   - PdfOverlay modal controlado por estado del thread
 *   - Footer con request_id y link Langfuse
 */
export default function IndexRoute() {
  const [state, dispatch] = useReducer(threadReducer, undefined, () => initialState('auto'));
  const hydratedRef = useRef(false);
  // La barra lateral ya no se contrae. Contraída sólo mostraba iconos de chat
  // idénticos entre sí, sin forma de distinguir un hilo de otro, así que el
  // control ocupaba sitio sin aportar información.
  const sidebarCollapsed = false;
  const [showSidebar, setShowSidebar] = useState(false);
  const [draftPrompt, setDraftPrompt] = useState<string | null>(null);
  const [demoCases, setDemoCases] = useState<DemoCase[]>([]);
  const [adminMode, setAdminMode] = useState(false);
  const [ingestionSnapshot, setIngestionSnapshot] = useState<IngestionSnapshot>({
    active_job: null,
    last_job: null,
  });
  const [ingestionExtractions, setIngestionExtractions] = useState<Awaited<ReturnType<typeof getIngestionExtractions>>['items']>([]);
  const [ingestionTotal, setIngestionTotal] = useState(0);
  const [ingestionOffset, setIngestionOffset] = useState(0);
  const ingestionPageSize = 20;
  const controllerRef = useRef<AbortController | null>(null);
  const startedAtRef = useRef<Map<string, number>>(new Map());
  const messagesRef = useRef<ThreadMessage[]>(state.messages);
  useEffect(() => {
    messagesRef.current = state.messages;
  }, [state.messages]);

  // T11 — hydrate the thread list from localStorage on mount, then
  // re-hydrate whenever the persistence key changes (e.g. devtools).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hydration = loadThreadHydration();
    if (hydration.threads.length === 0 && hydration.activeThreadId === null) {
      hydratedRef.current = true;
      return;
    }
    const activeId = hydration.activeThreadId ?? hydration.threads[0]?.id ?? 'demo-1';
    const activeRecord = hydration.threadRecords[activeId];
    dispatch({
      type: 'HYDRATE_THREADS',
      threads: hydration.threads,
      activeThreadId: activeId,
      threadMessages: Object.fromEntries(
        Object.entries(hydration.threadRecords).map(([id, record]) => [id, record.messages])
      ),
      threadSessionIds: Object.fromEntries(
        Object.entries(hydration.threadRecords).map(([id, record]) => [id, record.session_id])
      ),
      threadModes: Object.fromEntries(
        Object.entries(hydration.threadRecords).map(([id, record]) => [id, record.mode])
      ),
    });
    if (activeRecord) {
      dispatch({ type: 'SELECT_THREAD', id: activeId });
    }
    hydratedRef.current = true;
  }, []);

  useEffect(() => {
    void getDemoCases().then(setDemoCases).catch(() => setDemoCases([]));
  }, []);

  // T11 — persist the active state to localStorage after every
  // dispatch once hydration has completed. We coalesce writes by
  // reading the latest reducer state via a ref so multiple synchronous
  // actions do not stamp the same payload.
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);
  useEffect(() => {
    if (!hydratedRef.current) return;
    persistThreadState(stateRef.current, {});
  }, [state]);

  // Show sidebar only at >= 1280px (spec UX v2).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(min-width: 1280px)');
    const handler = () => setShowSidebar(mq.matches);
    handler();
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const handleSubmit = useCallback(
    (text: string) => {
      if (state.isStreaming) return;
      const messageId = crypto.randomUUID?.() ?? `${Date.now()}-u`;
      const assistantId = crypto.randomUUID?.() ?? `${Date.now()}-a`;
      dispatch({
        type: 'SUBMIT',
        messageId,
        assistantId,
        text,
        mode: state.mode,
        createdAt: Date.now(),
      });
      // Snapshot el assistantId para el callback de eventos.
      const targetAssistantId = assistantId;

      const handleEvent = (event: StreamingEvent) => {
        switch (event.type) {
          case 'started': {
            dispatch({ type: 'STREAM_STARTED', requestId: event.requestId, mode: event.mode });
            // Marcamos el primer tool call del assistant (classify) como done.
            // En el backend el primer stage es `dispatch`, que mapeamos a classify.
            // Para el resto (retrieve/check_rules/apply_decision) los cerramos al
            // recibir el stage o al completion.
            startedAtRef.current.set(targetAssistantId, Date.now());
            // Cerramos todos los tool calls pending con una duración simbólica.
            // El backend no emite stages intermedios suficientes para granular —
            // cerramos todos cuando llega 'completed'/'failed' o marcamos por
            // mapping (question → classify+retrieve; claim → classify+check+decision).
            return;
          }
          case 'stage': {
            // El backend sólo emite un stage hoy (`dispatch`, y sólo en modo
            // auto), que STREAM_COMPLETED ya cierra junto al resto del plan.
            // Cuando el backend emita un stage por etapa con su `timestamp`,
            // aquí es donde se calculará la duración real de cada una.
            return;
          }
          case 'completed': {
            // Cerramos todos los tool calls del assistant activo con payloads
            // derivados del envelope. Usamos un ref para evitar stale closure.
            dispatchToolCallsFromEnvelope(dispatch, messagesRef.current, event.response);
            dispatch({
              type: 'STREAM_COMPLETED',
              response: event.response,
              requestId: event.response.request_id,
            });
            return;
          }
          case 'failed': {
            dispatch({
              type: 'STREAM_FAILED',
              message: `${event.code}: ${event.message}`,
              requestId: event.requestId,
            });
            return;
          }
          case 'aborted': {
            dispatch({ type: 'STREAM_ABORTED' });
            return;
          }
          default: {
            const exhaustive: never = event;
            void exhaustive;
          }
        }
      };

      controllerRef.current = streamQuery(buildRequest(text, state.mode, 'es', state.threadSessionIds[state.activeThreadId] ?? null), {
        signal: new AbortController().signal,
        onEvent: handleEvent,
      }).controller;
    },
    [state.mode, state.isStreaming, state.activeThreadId, state.threadSessionIds],
  );

  const handleCancel = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    dispatch({ type: 'STREAM_ABORTED' });
  }, []);

  const handleNewThread = useCallback(() => {
    controllerRef.current?.abort();
    const newId = `t-${Date.now()}`;
    dispatch({ type: 'NEW_THREAD', id: newId });
  }, []);

  const openAdminMode = useCallback(() => {
    setAdminMode(true);
    setIngestionOffset(0);
    void Promise.all([getIngestionSnapshot(), getIngestionExtractions(0, ingestionPageSize)])
      .then(([nextSnapshot, nextExtractions]) => {
        setIngestionSnapshot(nextSnapshot);
        setIngestionExtractions(nextExtractions.items);
        setIngestionTotal(nextExtractions.total);
      })
      .catch(() => undefined);
  }, []);

  const handleIngestionPageChange = useCallback((nextOffset: number) => {
    setIngestionOffset(nextOffset);
    void getIngestionExtractions(nextOffset, ingestionPageSize)
      .then((page) => { setIngestionExtractions(page.items); setIngestionTotal(page.total); })
      .catch(() => undefined);
  }, []);

  const handleStartIngestion = useCallback(() => {
    void startIngestion()
      .then((job) => setIngestionSnapshot({ active_job: job, last_job: null }))
      .then(() => {
        const close = subscribeToIngestion(() => {
          void getIngestionSnapshot().then(setIngestionSnapshot).catch(() => undefined);
        }, () => undefined);
        window.setTimeout(close, 30 * 60 * 1000);
      })
      .catch(() => undefined);
  }, []);

  const handleSelectThread = useCallback(
    (id: string) => {
      controllerRef.current?.abort();
      dispatch({ type: 'SELECT_THREAD', id });
    },
    [],
  );

  const handleOpenCitation = useCallback(
    (citation: CitationRef) => {
      // Convertimos la CitationRef en EvidenceItem para el overlay.
      const evidence: EvidenceItem = {
        evidence_id: citation.evidenceId,
        document_hash: citation.documentHash,
        pdf_page: citation.pdfPage,
        delivery: 'text',
      };
      dispatch({ type: 'OPEN_PDF', target: { evidence, snippet: citation.snippet } });
    },
    [],
  );

  const handleClosePdf = useCallback((open: boolean) => {
    if (!open) dispatch({ type: 'CLOSE_PDF' });
  }, []);

  const handleSelectExample = useCallback((prompt: string) => {
    setDraftPrompt(prompt);
  }, []);

  const handleModeChange = useCallback((mode: UiMode) => {
    dispatch({ type: 'HYDRATE_MODE', mode });
  }, []);

  // Si draftPrompt se setea, propagamos al composer via key remount del textarea.
  // En esta versión, simplemente lo inyectamos al estado del composer a través
  // de un effect que setea una marca visible para el usuario.
  useEffect(() => {
    if (!draftPrompt) return;
    // Reset after a tick para evitar bucle.
    const t = window.setTimeout(() => setDraftPrompt(null), 50);
    return () => window.clearTimeout(t);
  }, [draftPrompt]);

  // Finding G3 #1: `/api/v1/manual/pdf` exige el query param `version`
  // (el sha256 del documento). Sin él el backend responde 422 y pdfjs
  // falla con "Unexpected server response (422) while retrieving PDF".
  const pdfDocumentHash = state.openPdf?.evidence?.document_hash;
  const pdfSrc = pdfDocumentHash
    ? `/api/v1/manual/pdf?version=${encodeURIComponent(pdfDocumentHash)}`
    : null;

  const lastEnvelope: EnvelopeResponse | undefined = (() => {
    for (let i = state.messages.length - 1; i >= 0; i--) {
      const m = state.messages[i];
      if (m && m.role === 'assistant' && m.envelope) return m.envelope;
    }
    return undefined;
  })();

  return (
    <TooltipProvider delayDuration={250}>
      <div className="relative flex min-h-screen flex-col bg-background text-foreground">
        {/* Dot pattern sutil de fondo (5% claro / 8% oscuro). */}
        <div className="pointer-events-none fixed inset-0 -z-10 text-foreground">
          <DotPattern size={22} opacity={0.05} />
        </div>

        <header className="flex h-14 items-center justify-between border-b bg-card/80 px-4 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="grid h-7 w-7 place-items-center rounded bg-primary text-xs font-bold text-primary-foreground">
              C
            </div>
            <h1 className="text-sm font-semibold sm:text-base">
              Allianz CICOS · Claims Intelligence
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Chat agéntico
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={adminMode ? () => setAdminMode(false) : openAdminMode}
                  aria-label={adminMode ? 'Volver al chat' : 'Modo administrador'}
                  title={adminMode ? 'Volver al chat' : 'Modo administrador'}
                  className="h-7 gap-1 px-2 text-xs"
                >
                  <span className="hidden sm:inline">{adminMode ? 'Volver al chat' : 'Modo administrador'}</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>{adminMode ? 'Volver al chat' : 'Modo administrador'}</TooltipContent>
            </Tooltip>
          </div>
        </header>

        <div className="flex flex-1 overflow-hidden">
          {showSidebar && !adminMode && (
            <ThreadSidebar
              threads={state.threads}
              activeThreadId={state.activeThreadId}
              collapsed={sidebarCollapsed}
              onSelect={handleSelectThread}
              onNewThread={handleNewThread}
            />
          )}

          <main className="flex flex-1 flex-col overflow-hidden">
            <div className="border-b bg-background/70 px-4 py-2 backdrop-blur">
              <BannerSystem />
            </div>

            {adminMode ? (
              <div className="flex-1 overflow-hidden">
                <IngestionPanel
                  snapshot={ingestionSnapshot}
                  extractions={ingestionExtractions}
                  totalExtractions={ingestionTotal}
                  offset={ingestionOffset}
                  pageSize={ingestionPageSize}
                  onPageChange={handleIngestionPageChange}
                  onStart={handleStartIngestion}
                />
              </div>
            ) : (
              <>
                <div className="flex-1 overflow-hidden">
                  {state.messages.length === 0 ? (
                    <EmptyState cases={demoCases} onSelect={handleSelectExample} />
                  ) : (
                    <Thread messages={state.messages} onOpenCitation={handleOpenCitation} />
                  )}
                </div>
                <div className="border-t bg-background/80 p-3 backdrop-blur">
                  <div className="mx-auto w-full max-w-3xl">
                    <ComposerWithDraft
                      busy={state.isStreaming}
                      mode={state.mode}
                      onModeChange={handleModeChange}
                      onSubmit={handleSubmit}
                      onCancel={handleCancel}
                      draftPrompt={draftPrompt}
                      onDraftConsumed={() => setDraftPrompt(null)}
                    />
                  </div>
                </div>
              </>
            )}
          </main>
        </div>

        <Footer
          requestId={state.pendingRequestId}
          response={lastEnvelope ?? null}
        />

        {pdfSrc && (
          <PdfOverlay
            open={!!state.openPdf}
            onOpenChange={handleClosePdf}
            src={pdfSrc}
            evidence={state.openPdf?.evidence ?? null}
            snippet={state.openPdf?.snippet ?? null}
          />
        )}
      </div>
    </TooltipProvider>
  );
}

/**
 * ComposerWithDraft — wrapper que acepta un `draftPrompt` opcional
 * para inyectar texto al composer al hacer click en un ejemplo del
 * EmptyState. Usa el `defaultValue` controlado del Composer: cuando
 * cambia el draft, el textarea se actualiza. Tras enviar, también
 * limpiamos el draft (vía `onTextChange`).
 */
function ComposerWithDraft({
  busy,
  mode,
  onModeChange,
  onSubmit,
  onCancel,
  draftPrompt,
  onDraftConsumed,
}: {
  busy: boolean;
  mode: UiMode;
  onModeChange: (mode: UiMode) => void;
  onSubmit: (text: string) => void;
  onCancel?: () => void;
  draftPrompt: string | null;
  onDraftConsumed?: () => void;
}) {
  const [draft, setDraft] = useState<string>('');

  useEffect(() => {
    if (draftPrompt !== null) setDraft(draftPrompt);
  }, [draftPrompt]);

  return (
    <Composer
      busy={busy}
      mode={mode}
      onModeChange={onModeChange}
      onSubmit={(text) => {
        onSubmit(text);
        setDraft('');
        onDraftConsumed?.();
      }}
      onCancel={onCancel}
      placeholder={
        draft
          ? 'Edita el ejemplo antes de enviar…'
          : 'Escribe tu consulta sobre el manual CIDE/ASCIDE…'
      }
      defaultValue={draft}
    />
  );
}

/**
 * dispatchToolCallsFromEnvelope — cierra los tool calls del assistant activo
 * derivando sus payloads del envelope final.
 *
 * No es un reducer action puro (muta startedAtRef + dispatch) pero el
 * scope es local al route y no afecta la lógica del reducer principal.
 */
function dispatchToolCallsFromEnvelope(
  dispatch: React.Dispatch<ThreadAction>,
  messages: ThreadMessage[],
  envelope: EnvelopeResponse,
) {
  let lastAssistant: MessageAssistant | undefined;
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m && m.role === 'assistant') {
      lastAssistant = m;
      break;
    }
  }
  if (!lastAssistant) return;

  // Finding G1 #2: en modo 'auto' el plan inicial sólo tenía 'classify'.
  // Aquí reescribimos el plan para que refleje el resolved_mode del
  // envelope (claim → check_rules + apply_decision; question → retrieve;
  // clarification → sólo classify). El reducer cierra el classify
  // pendiente y añade los cards que faltan.
  dispatch({
    type: 'RESOLVE_TOOL_PLAN',
    envelope,
    requested_mode: envelope.requested_mode,
  });

  // Sin `durationMs`: el backend no emite todavía un stage por etapa, así que
  // no sabemos cuánto tardó cada una. Antes se enviaba `Date.now() - startedAt`,
  // idéntico para las tres tarjetas porque comparten `startedAt`, lo que
  // presentaba el total como si fuera el tiempo de cada etapa.
  for (const tc of lastAssistant.toolCalls) {
    if (tc.status !== 'pending') continue;
    dispatch({
      type: 'TOOL_CALL_DONE',
      id: tc.id,
      payload: derivePayloadForKind(tc.kind, envelope),
    });
  }
}

