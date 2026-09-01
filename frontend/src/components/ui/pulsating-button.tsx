import { cn } from '@/lib/cn';
import { Button, type ButtonProps } from '@/components/ui/button';

/**
 * PulsatingButton — Magic UI primitive ported (spec UX v2).
 *
 * Botón con un anillo pulsante alrededor. Útil para acciones primarias
 * que invitan al click. Usado en el EmptyState para los ejemplos.
 *
 * Implementación: composición sobre Button shadcn + keyframe
 * `pulsating-ring` definido en globals.css.
 */
export interface PulsatingButtonProps extends ButtonProps {
  /** Color del anillo pulsante (default = primary). */
  pulseColor?: string;
}

export function PulsatingButton({
  pulseColor,
  className,
  children,
  ...props
}: PulsatingButtonProps) {
  return (
    <Button
      className={cn(
        'relative bg-primary text-primary-foreground hover:bg-primary/90 pulsating-ring',
        className,
      )}
      style={{ ['--tw-shadow-color' as string]: pulseColor }}
      {...props}
    >
      {children}
    </Button>
  );
}
