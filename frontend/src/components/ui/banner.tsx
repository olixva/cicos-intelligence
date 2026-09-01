import { forwardRef, type HTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/cn';
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';

/**
 * Banner — 4 variantes (info | success | warning | destructive).
 * Decisión del spec UX: cada banner lleva icono semántico + dismiss.
 */
const bannerVariants = cva(
  'relative w-full rounded-md border px-4 py-3 text-sm flex items-start gap-3 [&>svg]:shrink-0',
  {
    variants: {
      variant: {
        info: 'border-info/30 bg-info/10 text-foreground [&>svg]:text-info',
        success: 'border-success/30 bg-success/10 text-foreground [&>svg]:text-success',
        warning: 'border-warning/30 bg-warning/10 text-foreground [&>svg]:text-warning',
        destructive:
          'border-destructive/30 bg-destructive/10 text-foreground [&>svg]:text-destructive',
      },
    },
    defaultVariants: { variant: 'info' },
  },
);

const ICONS = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  destructive: AlertCircle,
} as const;

export interface BannerProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof bannerVariants> {
  /** Si se pasa, se muestra un botón de cierre. */
  onDismiss?: () => void;
  /** Etiqueta semántica (se anuncia a screen readers). */
  ariaLabel?: string;
}

export const Banner = forwardRef<HTMLDivElement, BannerProps>(
  ({ className, variant = 'info', children, onDismiss, ariaLabel, ...props }, ref) => {
    const Icon = ICONS[variant ?? 'info'];
    return (
      <div
        ref={ref}
        role="status"
        aria-live="polite"
        aria-label={ariaLabel}
        className={cn(bannerVariants({ variant }), className)}
        {...props}
      >
        <Icon aria-hidden="true" className="h-4 w-4 mt-0.5" />
        <div className="flex-1 text-pretty">{children}</div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Cerrar aviso"
            className="rounded-sm p-0.5 opacity-70 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        )}
      </div>
    );
  },
);
Banner.displayName = 'Banner';
