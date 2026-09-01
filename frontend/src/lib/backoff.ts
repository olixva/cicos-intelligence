/**
 * Curva de backoff exponencial para reintentos de queries fallidas.
 * Secuencia: 1s, 2s, 4s, 8s, 16s, cap 30s.
 * Aplica jitter de ±20% para evitar thundering herd.
 *
 * El consumidor decide cuándo invocar `delayFor(attempt)` entre reintentos.
 */

const BASE_MS = 1000;
const CAP_MS = 30_000;
const JITTER_RATIO = 0.2;

/** Calcula el delay (ms) para el N-ésimo reintento (1-indexed). */
export function delayFor(attempt: number): number {
  if (attempt < 1) return 0;
  const exponential = Math.min(BASE_MS * 2 ** (attempt - 1), CAP_MS);
  const jitter = exponential * JITTER_RATIO * (Math.random() * 2 - 1);
  return Math.max(0, Math.floor(exponential + jitter));
}

/** Decide si un reintento es admisible dado el número de intento (1..MAX). */
export function shouldRetry(attempt: number, maxAttempts = 5): boolean {
  return attempt >= 1 && attempt <= maxAttempts;
}

/** `await delayFor(attempt)` con manejo de cancelación opcional. */
export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(t);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });
}
