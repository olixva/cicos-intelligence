import { useEffect, useRef } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { UserMessage } from '@/components/thread/user-message';
import { AssistantMessage } from '@/components/thread/assistant-message';
import type { CitationRef, ThreadMessage } from '@/lib/thread-state';

export interface ThreadProps {
  messages: ThreadMessage[];
  onOpenCitation?: (citation: CitationRef) => void;
  onRetryToolCall?: (toolCallId: string) => void;
  onSubmitClarification?: (clarifications: string[]) => void;
  ariaLabel?: string;
}

/**
 * Thread — contenedor scrollable del chat agéntico.
 *
 * Auto-scroll al fondo cuando se añade un mensaje (a menos que el usuario
 * haya subido manualmente). Como el streaming ya marca caret, este hook
 * sólo necesita un `IntersectionObserver` o un sentinel; aquí usamos un
 * truco simple: si el último render tiene un mensaje nuevo, hacemos
 * scrollIntoView del último nodo.
 */
export function Thread({
  messages,
  onOpenCitation,
  onRetryToolCall,
  onSubmitClarification,
  ariaLabel = 'Hilo de conversación',
}: ThreadProps) {
  const lastRef = useRef<HTMLDivElement | null>(null);
  const isAtBottomRef = useRef(true);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight);
    isAtBottomRef.current = distanceFromBottom < 64;
  };

  useEffect(() => {
    if (isAtBottomRef.current && lastRef.current) {
      lastRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [messages.length]);

  return (
    <ScrollArea
      aria-label={ariaLabel}
      onScrollCapture={handleScroll}
      className="h-full"
    >
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
        {messages.map((m, idx) => {
          const isLast = idx === messages.length - 1;
          return (
            <div key={m.id} ref={isLast ? lastRef : undefined}>
              {m.role === 'user' ? (
                <UserMessage message={m} />
              ) : (
                <AssistantMessage
                  message={m}
                  isLatest={isLast}
                  onOpenCitation={onOpenCitation}
                  onRetryToolCall={onRetryToolCall}
                  onSubmitClarification={onSubmitClarification}
                />
              )}
            </div>
          );
        })}
      </div>
    </ScrollArea>
  );
}
