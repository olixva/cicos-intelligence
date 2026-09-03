import { Sparkles } from 'lucide-react';
import { cn } from '@/lib/cn';
import type { DemoCase } from '@/api/queries';

export interface EmptyStateProps {
  onSelect: (prompt: string) => void;
  cases: DemoCase[];
}

/**
 * EmptyState — bienvenida con ejemplos clickables. Click → inyecta el prompt.
 *
 * Las tarjetas son sobrias y sólo reaccionan al hover y al foco. La rejilla de
 * seis columnas centra la quinta tarjeta sin estirarla: todos los ejemplos
 * conservan el mismo ancho y una composición equilibrada.
 */
export function EmptyState({ onSelect, cases }: EmptyStateProps) {
  return (
    <section
      aria-label="Sugerencias"
      className="mx-auto flex w-full max-w-3xl flex-col items-center gap-6 px-4 py-12 text-center"
    >
      <header className="flex flex-col items-center gap-2">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Sparkles className="h-6 w-6" aria-hidden="true" />
        </span>
        <h1 className="text-balance text-xl font-semibold">
          Allianz CICOS · Claims Intelligence
        </h1>
        <p className="max-w-md text-sm text-muted-foreground">
          Consulta el manual CIDE/ASCIDE, analiza un siniestro o explora precedentes.
          Selecciona un ejemplo para empezar.
        </p>
      </header>
      <ul className="grid w-full grid-cols-1 items-stretch gap-3 sm:grid-cols-6">
        {cases.map((ex, index) => (
          <li
            key={ex.case_id}
            className={
              // Cinco elementos se distribuyen 2 + 2 + 1; el último queda
              // centrado y nunca ocupa una fila completa.
              index === cases.length - 1 && cases.length % 2 === 1
                ? 'sm:col-span-3 sm:col-start-2'
                : 'sm:col-span-3'
            }
          >
            <button
              type="button"
              onClick={() => onSelect(ex.text)}
              aria-label={`Probar ejemplo: ${ex.case_id}`}
              className={cn(
                'flex min-h-32 h-full w-full flex-col gap-1 rounded-lg border border-border bg-background',
                'px-3.5 py-3 text-left transition-colors',
                'hover:border-primary/60 hover:bg-accent',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              )}
            >
              <span className="text-[11px] font-medium uppercase tracking-wide text-primary">
                {ex.expected_intent === 'claim' ? 'Siniestro' : 'Pregunta'}
              </span>
              <span className="line-clamp-3 text-pretty text-sm leading-snug text-foreground/90">
                {ex.text}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
