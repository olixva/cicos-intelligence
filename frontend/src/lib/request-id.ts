import { v4 as uuidv4 } from 'uuid';

/**
 * Genera un X-Request-ID para correlacionar logs frontend ↔ backend.
 * Wrapper sobre uuid v4 para poder mockearlo en tests fácilmente.
 */
export function newRequestId(): string {
  return uuidv4();
}

/**
 * Valida que un string tenga forma de UUID v4 (lower/upper hex con guiones).
 * Útil para verificar X-Request-ID entrantes.
 */
export function isRequestId(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}
