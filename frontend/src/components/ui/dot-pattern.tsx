import { cn } from '@/lib/cn';

/**
 * DotPattern — primitivo portado de Magic UI.
 *
 * Patrón decorativo sutil de puntos (5% claro / 8% oscuro según tokens).
 * Se renderiza como background-image radial-gradient sin imagen física.
 * Usado en el fondo del chat para textura sin distraer.
 */
export interface DotPatternProps {
  /** Tamaño del grid en px. */
  size?: number;
  /** Color base del dot (CSS color). Default: token foreground. */
  color?: string;
  /** Opacidad adicional. */
  opacity?: number;
  /** Máscara radial para fade-out a los bordes. */
  withMask?: boolean;
  className?: string;
}

export function DotPattern({
  size = 22,
  color,
  opacity = 0.05,
  withMask = true,
  className,
}: DotPatternProps) {
  const dotColor = color ?? 'currentColor';

  return (
    <div
      aria-hidden="true"
      className={cn('pointer-events-none absolute inset-0', className)}
      style={{
        backgroundImage: `radial-gradient(${dotColor} ${Math.max(0.5, opacity)}px, transparent ${Math.max(1, opacity * 20)}px)`,
        backgroundSize: `${size}px ${size}px`,
        backgroundPosition: '0 0',
        ...(withMask
          ? {
              WebkitMaskImage:
                'radial-gradient(ellipse 70% 60% at 50% 40%, black 30%, transparent 80%)',
              maskImage:
                'radial-gradient(ellipse 70% 60% at 50% 40%, black 30%, transparent 80%)',
            }
          : null),
      }}
    />
  );
}
