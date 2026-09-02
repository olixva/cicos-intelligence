import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { cn } from '@/lib/cn';

/**
 * TextGenerateEffect — Magic UI primitive ported (spec UX v2).
 *
 * Aplica un typewriter palabra-por-palabra al texto recibido. Pensado
 * para mostrar el `streamedText` del AssistantMessage cuando isStreaming.
 *
 * Si `streaming` es false, muestra el texto final completo (sin caret).
 */
export interface TextGenerateEffectProps {
  text: string;
  streaming?: boolean;
  /** Velocidad en ms por palabra. */
  intervalMs?: number;
  className?: string;
}

export function TextGenerateEffect({
  text,
  streaming = false,
  intervalMs = 28,
  className,
}: TextGenerateEffectProps) {
  const [revealed, setRevealed] = useState<string>(streaming ? '' : text);
  const words = text.split(/(\s+)/);

  useEffect(() => {
    if (!streaming) {
      setRevealed(text);
      return;
    }
    setRevealed('');
    let cancelled = false;
    let i = 0;
    const tick = () => {
      if (cancelled) return;
      i += 1;
      setRevealed(words.slice(0, i).join(''));
      if (i < words.length) {
        window.setTimeout(tick, intervalMs);
      }
    };
    window.setTimeout(tick, intervalMs);
    return () => {
      cancelled = true;
    };
    // Re-ejecutar cuando el texto cambie.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, streaming, intervalMs]);

  const isStillTyping = streaming && revealed.length < text.length;

  return (
    <div className={cn('text-pretty leading-relaxed', className)}>
      <AnimatePresence>
        {streaming ? (
          <span>
            {revealed}
            {isStillTyping && <span className="streaming-caret" aria-hidden="true" />}
          </span>
        ) : (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
          >
            {text}
          </motion.span>
        )}
      </AnimatePresence>
      {/* Texto oculto para lectores de pantalla: siempre el texto completo.
          `aria-hidden` evita que la live region del padre (assistant-message)
          anuncie el contenido dos veces (Finding G3 #2). */}
      <span className="sr-only" aria-hidden="true">
        {text}
      </span>
    </div>
  );
}
