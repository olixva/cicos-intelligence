import { useCallback, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, Square } from 'lucide-react';

const MAX_CHARS = 2000;
const WARN_CHARS = 1500;

export interface QueryFormProps {
  /** Callback al enviar. Recibe el texto validado. */
  onSubmit: (text: string) => void;
  /** Si true, deshabilita el formulario (ej: durante streaming). */
  busy?: boolean;
  /** Si se provee, se muestra un botón "Detener" junto al de enviar. */
  onCancel?: () => void;
  placeholder?: string;
}

/**
 * QueryForm — textarea con contador y botones.
 *
 * - Mínimo 1 carácter no-whitespace para habilitar el envío.
 * - Contador que cambia a warning a partir de 1500 y a error sobre 2000.
 * - El botón "Enviar" se deshabilita cuando busy=true o el texto está vacío
 *   o supera MAX_CHARS.
 */
export function QueryForm({
  onSubmit,
  busy = false,
  onCancel,
  placeholder = 'Describe tu consulta o caso…',
}: QueryFormProps) {
  const [text, setText] = useState('');

  const trimmed = text.trim();
  const isEmpty = trimmed.length === 0;
  const tooLong = text.length > MAX_CHARS;
  const showWarning = text.length >= WARN_CHARS && !tooLong;

  const canSubmit = useMemo(
    () => !busy && !isEmpty && !tooLong,
    [busy, isEmpty, tooLong],
  );

  const handleSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!canSubmit) return;
      onSubmit(trimmed);
    },
    [canSubmit, onSubmit, trimmed],
  );

  const counterColor = tooLong
    ? 'text-destructive'
    : showWarning
      ? 'text-warning'
      : 'text-muted-foreground';

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3" aria-busy={busy}>
      <label htmlFor="query-input" className="sr-only">
        Texto de la consulta
      </label>
      <Textarea
        id="query-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        disabled={busy}
        maxLength={MAX_CHARS + 200}
        aria-describedby="query-counter"
        className="min-h-[140px]"
      />
      <div className="flex items-center justify-between gap-3">
        <span
          id="query-counter"
          aria-live="polite"
          className={`text-xs tabular-nums ${counterColor}`}
        >
          {text.length} / {MAX_CHARS}
        </span>
        <div className="flex items-center gap-2">
          {busy && onCancel && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onCancel}
              aria-label="Detener"
            >
              <Square className="h-3.5 w-3.5" aria-hidden="true" />
              Detener
            </Button>
          )}
          <Button type="submit" size="sm" disabled={!canSubmit} aria-label="Enviar consulta">
            <Send className="h-3.5 w-3.5" aria-hidden="true" />
            Enviar
          </Button>
        </div>
      </div>
    </form>
  );
}
