import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Combina clases condicionales y resuelve conflictos de Tailwind.
 * Patrón estándar shadcn/ui: clsx primero (evalúa condicionales),
 * tailwind-merge después (resuelve conflictos de utility).
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
