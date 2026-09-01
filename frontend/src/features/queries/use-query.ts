import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { EnvelopeRequest, EnvelopeResponse } from '@/api/queries';

/**
 * useQuerySync — POST síncrono a /api/v1/queries.
 *
 * Devuelve la EnvelopeResponse completa. No soporta streaming; para streaming
 * usar `use-query-stream.ts`. El componente decide en runtime según
 * `request.stream`.
 */
export function useQuerySync() {
  return useMutation({
    mutationFn: async (input: EnvelopeRequest): Promise<EnvelopeResponse> => {
      const { data, error, response } = await apiClient.POST('/api/v1/queries', {
        body: input,
      });
      if (error || !response.ok || !data) {
        const message =
          typeof error === 'object' && error && 'message' in error
            ? String((error as { message: unknown }).message)
            : `HTTP ${response.status}`;
        throw new Error(message);
      }
      return data as EnvelopeResponse;
    },
  });
}
