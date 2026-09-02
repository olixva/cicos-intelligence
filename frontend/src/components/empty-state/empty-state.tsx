import { Sparkles } from 'lucide-react';
import { cn } from '@/lib/cn';

export interface EmptyStateProps {
  onSelect: (prompt: string) => void;
}

const EXAMPLES: ReadonlyArray<{ label: string; prompt: string }> = [
  {
    label: 'Pregunta frecuente',
    prompt: '¿Qué dice el manual CIDE sobre los daños materiales en colisiones frontales?',
  },
  {
    label: 'Siniestro corto',
    prompt:
      'Vehículo A gira a la izquierda en un cruce con semáforo en ámbar y es embestido por el vehículo B que circulaba en sentido contrario. ¿Convenio aplicable?',
  },
  {
    label: 'Consulta ASCIDE',
    prompt: '¿Cuál es el plazo de prescripción de las acciones recogidas en el convenio ASCIDE?',
  },
  {
    label: 'Baremo y cuantías',
    prompt: '¿Cómo se calcula la indemnización por lesiones temporales según el baremo 2025?',
  },
  {
    label: 'Clarificación',
    prompt: 'Necesito analizar un caso de atropello con responsabilidad cruzada.',
  },
];

/**
 * EmptyState — bienvenida con ejemplos clickables. Click → inyecta el prompt.
 *
 * Las tarjetas eran `PulsatingButton`, que anima un `box-shadow` expandiéndose
 * 12 px hacia fuera en bucle infinito. Con una separación de 8 px los halos de
 * tarjetas contiguas se solapaban, y la animación permanente competía con el
 * propio texto. Ahora son tarjetas sobrias que sólo reaccionan al hover y al
 * foco, con altura uniforme para que la rejilla quede cuadrada.
 */
export function EmptyState({ onSelect }: EmptyStateProps) {
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
      <ul className="grid w-full grid-cols-1 items-stretch gap-3 sm:grid-cols-2">
        {EXAMPLES.map((ex, index) => (
          <li
            key={ex.label}
            className={
              // Con cinco ejemplos en dos columnas el último dejaba un hueco.
              // Ocupando el ancho completo la rejilla cierra bien.
              index === EXAMPLES.length - 1 && EXAMPLES.length % 2 === 1
                ? 'sm:col-span-2'
                : undefined
            }
          >
            <button
              type="button"
              onClick={() => onSelect(ex.prompt)}
              aria-label={`Probar ejemplo: ${ex.label}`}
              className={cn(
                'flex h-full w-full flex-col gap-1 rounded-lg border border-border bg-background',
                'px-3.5 py-3 text-left transition-colors',
                'hover:border-primary/60 hover:bg-accent',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              )}
            >
              <span className="text-[11px] font-medium uppercase tracking-wide text-primary">
                {ex.label}
              </span>
              <span className="text-pretty text-sm leading-snug text-foreground/90">
                {ex.prompt}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
