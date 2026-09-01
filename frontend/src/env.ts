import { z } from 'zod';

/**
 * Validador de variables de entorno en runtime.
 *
 * Decisión D1: el frontend no tiene secretos. La única variable esperada es
 * VITE_API_BASE_URL (string vacío = mismo origin, caso por defecto del
 * reverse proxy).
 *
 * Zod falla rápido en build/dev si falta algo crítico. Usamos un schema
 * laxo porque VITE_API_BASE_URL="" es un valor válido (mismo origin).
 */

const EnvSchema = z.object({
  VITE_API_BASE_URL: z.string().default(''),
  MODE: z.enum(['development', 'production', 'test']).default('development'),
  DEV: z.boolean().default(false),
  PROD: z.boolean().default(false),
});

export type Env = z.infer<typeof EnvSchema>;

function readEnv(): Env {
  // Import.meta.env está disponible en Vite; aquí hacemos la lectura cruda
  // porque zod exige un objeto literal, no unknown.
  const raw: Record<string, unknown> = {
    VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL ?? '',
    MODE: import.meta.env.MODE ?? 'development',
    DEV: import.meta.env.DEV ?? false,
    PROD: import.meta.env.PROD ?? false,
  };
  const parsed = EnvSchema.safeParse(raw);
  if (!parsed.success) {
    // No abortamos el árbol entero: caemos a defaults seguros para no
    // romper el render. El warning sigue siendo informativo.
    console.warn('[env] validación falló, usando defaults', parsed.error.format());
    return EnvSchema.parse({});
  }
  return parsed.data;
}

export const env: Env = readEnv();
