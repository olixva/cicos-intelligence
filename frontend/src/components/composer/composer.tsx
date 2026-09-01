import { useCallback, useEffect, useState } from 'react';
import TextareaAutosize from 'react-textarea-autosize';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { ShimmerButton } from '@/components/ui/shimmer-button';
import { Send, Square, HelpCircle, FileWarning, AlertTriangle } from 'lucide-react';
import { isUiMode, type UiMode } from '@/api/queries';
import { loadKey, saveKey } from '@/lib/storage';
import { cn } from '@/lib/cn';

const MAX_CHARS = 4000;
const WARN_CHARS = 3200;
const STORAGE_KEY = 'cicos.mode.v2';

const OPTIONS: ReadonlyArray<{ value: UiMode; label: string; description: string }> = [
  { value: 'auto', label: 'Automático', description: 'El backend decide según tu texto.' },
  { value: 'question', label: 'Pregunta', description: 'Consulta directa sobre el manual.' },
  { value: 'claim', label: 'Siniestro', description: 'Análisis estructurado de un caso.' },
];

export interface ComposerProps {
  /** Estado de streaming actual (muestra botón Cancelar si true). */
  busy?: boolean;
  /** Modo vigente (controlado). */
  mode: UiMode;
  /** Notifica cambio de modo. */
  onModeChange: (mode: UiMode) => void;
  /** Enviar consulta. */
  onSubmit: (text: string) => void;
  /** Cancelar stream activo. */
  onCancel?: () => void;
  /** Placeholder contextual. */
  placeholder?: string;
  /** Valor inicial del textarea (controlled initialValue). */
  defaultValue?: string;
  /** Callback invocado cuando cambia el texto (para limpiar tras enviar). */
  onTextChange?: (text: string) => void;
  className?: string;
}

/**
 * Composer — input fijo abajo del thread.
 *
 * Origin UI comp-512-inspired: textarea autosize + radio group de modo
 * persistente + botones Enviar (shimmer Magic UI) / Cancelar.
 *
 * - Enter envía, Shift+Enter inserta salto.
 * - Contador 0 / 4000 con warning >= 3200.
 * - Modo persiste en localStorage (clave `cicos.mode.v2`).
 */
export function Composer({
  busy = false,
  mode,
  onModeChange,
  onSubmit,
  onCancel,
  placeholder = 'Escribe tu consulta sobre el manual CIDE/ASCIDE…',
  defaultValue = '',
  onTextChange,
  className,
}: ComposerProps) {
  const [text, setText] = useState(defaultValue);

  useEffect(() => {
    setText(defaultValue);
  }, [defaultValue]);

  const updateText = (next: string) => {
    setText(next);
    onTextChange?.(next);
  };

  // Hidratamos el modo desde storage o query string al primer mount.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    const fromUrl = url.searchParams.get('mode');
    if (isUiMode(fromUrl)) {
      saveKey(STORAGE_KEY, fromUrl);
      if (fromUrl !== mode) onModeChange(fromUrl);
      return;
    }
    const stored = loadKey(STORAGE_KEY);
    if (isUiMode(stored) && stored !== mode) onModeChange(stored);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const trimmed = text.trim();
  const tooLong = text.length > MAX_CHARS;
  const showWarning = text.length >= WARN_CHARS && !tooLong;
  const canSubmit = !busy && trimmed.length > 0 && !tooLong;

  const updateMode = useCallback(
    (next: string) => {
      if (!isUiMode(next)) return;
      saveKey(STORAGE_KEY, next);
      onModeChange(next);
    },
    [onModeChange],
  );

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (canSubmit) onSubmit(trimmed);
    }
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit(trimmed);
  };

  const counterClass = cn(
    'text-xs tabular-nums',
    tooLong
      ? 'text-destructive'
      : showWarning
        ? 'text-warning'
        : 'text-muted-foreground',
  );

  const PlaceholderIcon =
    mode === 'claim' ? AlertTriangle : mode === 'question' ? HelpCircle : FileWarning;

  return (
    <form
      onSubmit={handleSubmit}
      aria-busy={busy}
      className={cn(
        'flex flex-col gap-3 rounded-lg border bg-card p-3 shadow-sm',
        className,
      )}
    >
      <fieldset aria-label="Modo de consulta" className="flex flex-wrap items-center gap-3">
        <legend className="sr-only">Modo de consulta</legend>
        <RadioGroup value={mode} onValueChange={updateMode} className="flex flex-wrap gap-2">
          {OPTIONS.map((opt) => (
            <Label
              key={opt.value}
              htmlFor={`composer-mode-${opt.value}`}
              className="flex cursor-pointer items-start gap-2 rounded-md border border-transparent p-2 hover:bg-accent has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5"
            >
              <RadioGroupItem id={`composer-mode-${opt.value}`} value={opt.value} />
              <div className="flex flex-col">
                <span className="text-xs font-medium leading-none">{opt.label}</span>
                <span className="text-[10px] text-muted-foreground">{opt.description}</span>
              </div>
            </Label>
          ))}
        </RadioGroup>
      </fieldset>

      <div className="relative">
        <PlaceholderIcon
          className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground"
          aria-hidden="true"
        />
        <TextareaAutosize
          id="composer-input"
          value={text}
          onChange={(e) => updateText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={busy}
          minRows={2}
          maxRows={8}
          aria-describedby="composer-counter"
          aria-label="Texto de la consulta"
          className={cn(
            'flex w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm',
            'ring-offset-background placeholder:text-muted-foreground',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            'disabled:cursor-not-allowed disabled:opacity-50 resize-none',
          )}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
          <span id="composer-counter" aria-live="polite" className={counterClass}>
            {text.length} / {MAX_CHARS}
          </span>
          <span className="hidden sm:inline">
            <kbd className="rounded border bg-muted px-1 py-0.5 font-mono text-[10px]">Enter</kbd>{' '}
            para enviar ·{' '}
            <kbd className="rounded border bg-muted px-1 py-0.5 font-mono text-[10px]">
              Shift+Enter
            </kbd>{' '}
            nueva línea
          </span>
        </div>
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
              Cancelar
            </Button>
          )}
          {busy ? (
            <Button type="button" size="sm" disabled aria-label="Enviando">
              <Square className="h-3.5 w-3.5" aria-hidden="true" />
              Enviando…
            </Button>
          ) : (
            <ShimmerButton type="submit" size="sm" disabled={!canSubmit} aria-label="Enviar consulta">
              <Send className="h-3.5 w-3.5" aria-hidden="true" />
              Enviar
            </ShimmerButton>
          )}
        </div>
      </div>
    </form>
  );
}
