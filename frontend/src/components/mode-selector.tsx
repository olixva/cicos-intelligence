import { useEffect, useState } from 'react';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { isUiMode, type UiMode } from '@/api/queries';
import { loadKey, saveKey } from '@/lib/storage';

const STORAGE_KEY = 'cicos.mode.v1';
const URL_PARAM = 'mode';
const DEFAULT_MODE: UiMode = 'auto';

const OPTIONS: ReadonlyArray<{ value: UiMode; label: string; description: string }> = [
  { value: 'auto', label: 'Automático', description: 'El backend decide según tu texto.' },
  { value: 'question', label: 'Pregunta', description: 'Consulta directa sobre el manual.' },
  { value: 'claim', label: 'Siniestro', description: 'Análisis estructurado de un caso.' },
];

function readUrlMode(): UiMode | null {
  if (typeof window === 'undefined') return null;
  try {
    const u = new URL(window.location.href);
    const raw = u.searchParams.get(URL_PARAM);
    return isUiMode(raw) ? raw : null;
  } catch {
    return null;
  }
}

function persistMode(mode: UiMode): void {
  saveKey(STORAGE_KEY, mode);
}

export interface ModeSelectorProps {
  value: UiMode;
  onChange: (mode: UiMode) => void;
  /** Si true, permite controlar el modo desde fuera (controlled). */
  id?: string;
}

/**
 * ModeSelector — 3 radios (auto, question, claim).
 *
 * Persistencia:
 *   1. Lee primero `?mode=` en la URL (gana sobre el storage).
 *   2. Luego `cicos.mode.v1` en localStorage (con fallback URL state).
 *   3. Default: 'auto'.
 *
 * La URL se actualiza solo si difiere (no se reescribe en cada render).
 */
export function ModeSelector({ value, onChange, id = 'mode-selector' }: ModeSelectorProps) {
  // Hidratamos desde storage/URL sólo en el primer mount.
  const [hydrated] = useState(() => {
    const url = readUrlMode();
    if (url) {
      persistMode(url);
      return url;
    }
    const stored = loadKey(STORAGE_KEY);
    if (isUiMode(stored)) return stored;
    return DEFAULT_MODE;
  });

  // Empujamos el valor hidratado al padre solo si difiere.
  useEffect(() => {
    if (hydrated !== value) onChange(hydrated);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = (next: string) => {
    if (!isUiMode(next)) return;
    persistMode(next);
    onChange(next);
  };

  return (
    <fieldset
      aria-label="Modo de consulta"
      id={id}
      className="flex flex-col gap-2 rounded-md border bg-card p-3"
    >
      <legend className="px-1 text-xs font-medium text-muted-foreground">Modo</legend>
      <RadioGroup value={value} onValueChange={update} className="gap-2">
        {OPTIONS.map((opt) => (
          <Label
            key={opt.value}
            htmlFor={`${id}-${opt.value}`}
            className="flex items-start gap-3 rounded-md border border-transparent p-2 hover:bg-accent has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5"
          >
            <RadioGroupItem id={`${id}-${opt.value}`} value={opt.value} aria-label={opt.label} />
            <div className="flex flex-col">
              <span className="text-sm font-medium">{opt.label}</span>
              <span className="text-xs text-muted-foreground">{opt.description}</span>
            </div>
          </Label>
        ))}
      </RadioGroup>
    </fieldset>
  );
}
