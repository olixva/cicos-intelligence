import { CheckCircle2, MessageCircleQuestion } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';

interface ClarificationPanelProps {
  missingInformation: string[];
  onSubmit: (clarifications: string[]) => void;
}

/** Compact, keyboard-friendly follow-up form for an unresolved claim. */
export function ClarificationPanel({ missingInformation, onSubmit }: ClarificationPanelProps) {
  const [values, setValues] = useState<string[]>(() => missingInformation.map(() => ''));
  const hasValue = values.some((value) => value.trim());

  return (
    <section aria-label="Información necesaria" className="rounded-lg border border-primary/30 bg-primary/5 p-3">
      <div className="mb-3 flex items-start gap-2">
        <MessageCircleQuestion className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        <div>
          <h3 className="text-sm font-medium">Necesito un dato más para resolver el siniestro</h3>
          <p className="text-xs text-muted-foreground">Puedes escribir la respuesta o indicar que no lo sabes.</p>
        </div>
      </div>
      <div className="space-y-2">
        {missingInformation.map((field, index) => (
          <label key={`${field}-${index}`} className="block text-xs text-foreground/80">
            <span className="mb-1 block">{field}</span>
            <input
              value={values[index] ?? ''}
              placeholder="Escribe un dato…"
              onChange={(event) => {
                const next = [...values];
                next[index] = event.target.value;
                setValues(next);
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && hasValue) onSubmit(values.map((value) => value.trim()).filter(Boolean));
              }}
              className="flex h-8 w-full rounded-md border border-input bg-background px-2 text-xs outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
            />
            <button
              type="button"
              className="mt-1 text-[11px] text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => {
                const next = [...values];
                next[index] = 'No lo sé';
                setValues(next);
              }}
            >
              No lo sé
            </button>
          </label>
        ))}
      </div>
      <Button type="button" size="sm" className="mt-3 gap-1.5" disabled={!hasValue} onClick={() => onSubmit(values.map((value) => value.trim()).filter(Boolean))}>
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
        Continuar análisis
      </Button>
    </section>
  );
}
