import createClient, { type Middleware } from 'openapi-fetch';
import { newRequestId } from '@/lib/request-id';
import type { paths } from '@/types/api.gen';
import { env } from '@/env';

/**
 * Cliente OpenAPI tipado.
 *
 * Mismo origen: `VITE_API_BASE_URL=""` significa que las
 * llamadas son relatives al origin del frontend (el reverse proxy del
 * backend está sirviendo `/api/v1/*`).
 *
 * Los tipos vienen de `src/types/api.gen.ts`, regenerado
 * en cada dev/build/test por `predev/prebuild/pretest`.
 *
 * Middleware X-Request-ID: cada llamada genera un uuid v4 si el caller
 * no provee uno. El backend lo logueará y el footer lo mostrará.
 */

const REQUEST_ID_HEADER = 'X-Request-ID';

export type ApiClient = ReturnType<typeof createClient<paths>>;

const requestIdMiddleware: Middleware = {
  async onRequest({ request }) {
    const existing = request.headers.get(REQUEST_ID_HEADER);
    if (!existing) {
      request.headers.set(REQUEST_ID_HEADER, newRequestId());
    }
    return request;
  },
};

export const apiClient: ApiClient = createClient<paths>({
  baseUrl: env.VITE_API_BASE_URL,
  headers: {
    Accept: 'application/json',
  },
});

apiClient.use(requestIdMiddleware);

/** Helper para pasar un requestId explícito en una llamada concreta. */
export function withRequestId(headers: Record<string, string> = {}): Record<string, string> {
  return { [REQUEST_ID_HEADER]: newRequestId(), ...headers };
}

export { REQUEST_ID_HEADER };
