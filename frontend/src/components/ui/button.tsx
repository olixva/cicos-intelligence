import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cn } from '@/lib/cn';
import { buttonVariants, type ButtonVariantProps } from '@/components/ui/button-variants';

/**
 * Button — primitivo shadcn/ui.
 * Variantes: primary, secondary, outline, ghost, destructive, link.
 * Tamaños: sm, md, lg, icon.
 * Soporta `asChild` (Radix Slot) para componer con otros elementos.
 */
export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    ButtonVariantProps {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(buttonVariants({ variant, size }), className)}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';
