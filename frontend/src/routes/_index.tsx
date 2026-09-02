import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { Plus } from 'lucide-react';
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
import type { EnvelopeResponse, EvidenceItem } from '@/api/queries';

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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const [showSidebar, setShowSidebar] = useState(false);
  const [draftPrompt, setDraftPrompt] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const startedAtRef = useRef<Map<string, number>>(new Map());
  const messagesRef = useRef<ThreadMessage[]>(state.messages);
  useEffect(() => {
    messagesRef.current = state.messages;
  }, [state.messages]);

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
            // Mapeo simple de stage → tool call done. Si en el futuro el
            // backend emite más stages (retrieve, check_rules, apply_decision)
            // podemos mapearlos aquí.
            const stageToKind: Record<string, 'classify' | 'retrieve' | 'check_rules' | 'apply_decision'> = {
              dispatch: 'classify',
              retrieve: 'retrieve',
              check_rules: 'check_rules',
              apply_decision: 'apply_decision',
            };
            const kind = stageToKind[event.stage];
            if (kind) {
              // El reducer actualiza por id; necesitamos el id concreto del tool call.
              // Como el reducer no expone los ids, lo hacemos via dispatch
              // TOOL_CALL_DONE inline. Pero el reducer espera el id…
              // Hack controlado: dispatch TOOL_CALL_PENDING? No, mejor lo
              // delegamos a STREAM_COMPLETED que cierra todos los pending.
            }
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

      controllerRef.current = streamQuery(buildRequest(text, state.mode), {
        signal: new AbortController().signal,
        onEvent: handleEvent,
      }).controller;
    },
    [state.mode, state.isStreaming],
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
                  onClick={handleNewThread}
                  aria-label="Nueva consulta"
                  title="Nueva consulta"
                  className="h-7 gap-1 px-2 text-xs"
                >
                  <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                  <span className="hidden sm:inline">Nueva consulta</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Nueva consulta</TooltipContent>
            </Tooltip>
          </div>
        </header>

        <div className="flex flex-1 overflow-hidden">
          {showSidebar && (
            <ThreadSidebar
              threads={state.threads}
              activeThreadId={state.activeThreadId}
              collapsed={sidebarCollapsed}
              onSelect={handleSelectThread}
              onNewThread={handleNewThread}
              onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
            />
          )}

          <main className="flex flex-1 flex-col overflow-hidden">
            <div className="border-b bg-background/70 px-4 py-2 backdrop-blur">
              <BannerSystem />
            </div>

            <div className="flex-1 overflow-hidden">
              {state.messages.length === 0 ? (
                <EmptyState onSelect={handleSelectExample} />
              ) : (
                <Thread
                  messages={state.messages}
                  onOpenCitation={handleOpenCitation}
                />
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
          </main>
        </div>

        <Footer response={lastEnvelope ?? null} />

        <PdfOverlay
          open={!!state.openPdf}
          onOpenChange={handleClosePdf}
          src="/api/v1/manual/pdf"
          evidence={state.openPdf?.evidence ?? null}
          snippet={state.openPdf?.snippet ?? null}
        />
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

  const started = Date.now();
  for (const tc of lastAssistant.toolCalls) {
    if (tc.status !== 'pending') continue;
    const payload = derivePayload(tc.kind, envelope);
    dispatch({
      type: 'TOOL_CALL_DONE',
      id: tc.id,
      durationMs: started - tc.startedAt,
      payload,
    });
  }
}

function derivePayload(
  kind: 'classify' | 'retrieve' | 'check_rules' | 'apply_decision',
  envelope: EnvelopeResponse,
): unknown {
  switch (kind) {
    case 'classify':
      return { mode: envelope.resolved_mode };
    case 'retrieve':
      return {
        chunks: (envelope.evidence ?? []).map((e) => ({
          evidenceId: e.evidence_id,
          pdfPage: e.pdf_page,
          preview: '',
          score: undefined,
        })),
      };
    case 'check_rules':
      if (envelope.result && envelope.result.kind === 'claim') {
        return { convention: envelope.result.convention, rules: [] };
      }
      return { convention: null, rules: [] };
    case 'apply_decision':
      if (envelope.result && envelope.result.kind === 'claim') {
        return {
          convention: envelope.result.convention,
          applicability: envelope.result.applicability,
          decision: envelope.result.decision,
        };
      }
      if (envelope.result && envelope.result.kind === 'clarification') {
        return {
          convention: null,
          applicability: 'undetermined',
          decision: 'undetermined',
        };
      }
      return { convention: null, applicability: null, decision: null };
    default: {
      const exhaustive: never = kind;
      void exhaustive;
      return null;
    }
  }
}
