import { Sparkles } from 'lucide-react';
import { PulsatingButton } from '@/components/ui/pulsating-button';

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
 * EmptyState — mensaje de bienvenida con 5 ejemplos clickables.
 *
 * Spec UX v2: pulsating-button de Magic UI como affordance para
 * descubrir los ejemplos. Click → inyecta el prompt al composer.
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
      <ul className="grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
        {EXAMPLES.map((ex) => (
          <li key={ex.label}>
            <PulsatingButton
              type="button"
              variant="outline"
              className="h-auto w-full justify-start whitespace-normal bg-background px-3 py-2 text-left text-sm font-normal text-foreground hover:bg-accent"
              onClick={() => onSelect(ex.prompt)}
              aria-label={`Probar ejemplo: ${ex.label}`}
            >
              <span className="flex w-full flex-col gap-0.5 text-left">
                <span className="text-xs font-medium uppercase tracking-wide text-primary">
                  {ex.label}
                </span>
                <span className="text-pretty text-sm text-foreground/90">{ex.prompt}</span>
              </span>
            </PulsatingButton>
          </li>
        ))}
      </ul>
    </section>
  );
}
