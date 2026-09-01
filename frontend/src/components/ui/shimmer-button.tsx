import { cn } from '@/lib/cn';
import { Button, type ButtonProps } from '@/components/ui/button';

/**
 * ShimmerButton — Magic UI primitive ported (spec UX v2).
 *
 * Botón con un barrido (shimmer) diagonal infinito detrás del texto.
 * Se usa en el botón "Enviar" del Composer cuando está idle.
 *
 * El original Magic UI se renderiza como `<button>` con un `<span>`
 * absoluto que recorre 400% del ancho. Aquí componemos sobre nuestro
 * `Button` de shadcn para mantener variantes accesibles.
 */
export interface ShimmerButtonProps extends ButtonProps {
  /** Color del shimmer (CSS color o `currentColor`). */
  shimmerColor?: string;
  /** Duración del barrido en segundos. */
  shimmerDuration?: string;
  /** Color del fondo (override del variant primary). */
  background?: string;
}

export function ShimmerButton({
  shimmerColor = '#ffffff',
  shimmerDuration = '2.4s',
  background,
  className,
  children,
  ...props
}: ShimmerButtonProps) {
  return (
    <Button
      className={cn(
        'relative overflow-hidden isolate',
        // Forzamos primary brand aquí para que el shimmer tenga contraste.
        'bg-primary text-primary-foreground',
        className,
      )}
      style={{ background }}
      {...props}
    >
      {/* shimmer layer (detrás del texto) */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 left-0 w-[200%] -z-10"
      >
        <span
          className="block h-full w-1/2 shimmer-slide"
          style={{
            background: `linear-gradient(90deg, transparent 0%, ${shimmerColor}55 50%, transparent 100%)`,
            animationDuration: shimmerDuration,
          }}
        />
      </span>
      <span className="relative z-10 inline-flex items-center gap-2">{children}</span>
    </Button>
  );
}
