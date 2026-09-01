import { cn } from '@/lib/cn';

/**
 * BorderBeam — Magic UI primitive ported (spec UX v2).
 *
 * Trazo animado que orbita el borde de su contenedor padre. Útil para
 * indicar estado "live" o foco en citation chips y tool cards.
 *
 * Por defecto sólo se muestra en hover/focus del padre (via group-hover),
 * para no distraer en estado idle.
 */
export interface BorderBeamProps {
  /** Color del haz. */
  color?: string;
  /** Tamaño del haz en px. */
  size?: number;
  /** Duración de la rotación en segundos. */
  duration?: number;
  /** Delay en segundos. */
  delay?: number;
  className?: string;
}

export function BorderBeam({
  color = 'hsl(var(--primary))',
  size = 80,
  duration = 4,
  delay = 0,
  className,
}: BorderBeamProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'pointer-events-none absolute inset-0 rounded-[inherit] border-beam-anim',
        // Recortamos al borde usando mask para que el haz parezca correr
        // solo por el contorno.
        '[mask-clip:padding-box,border-box] [-webkit-mask-composite:xor] [mask-composite:exclude]',
        className,
      )}
      style={{
        padding: '1px',
        background: `conic-gradient(from 0deg, transparent 0deg, ${color} 90deg, transparent 180deg)`,
        WebkitMaskImage: `linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)`,
        maskImage: `linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)`,
        animationDuration: `${duration}s`,
        animationDelay: `${delay}s`,
      }}
    >
      <span
        aria-hidden="true"
        className="absolute inset-0 block"
        style={{
          width: `${size}px`,
          background: `radial-gradient(${color} 0%, transparent 70%)`,
          opacity: 0.85,
        }}
      />
    </span>
  );
}
