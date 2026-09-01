import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';

type LiveBody = { status?: string };

/**
 * GET /health/live — el proceso FastAPI responde.
 * No cachear entre usuarios; usar staleTime corto.
 */
export function useHealthLive() {
  return useQuery({
    queryKey: ['health', 'live'],
    queryFn: async () => {
      const { data, error, response } = await apiClient.GET('/health/live', {});
      if (error || !response.ok) {
        throw new Error(`health/live ${response.status}: ${JSON.stringify(error)}`);
      }
      return data as LiveBody;
    },
    refetchInterval: 30_000,
    staleTime: 10_000,
    retry: 1,
  });
}

type ReadyBody = { status?: string; reason?: string };

/**
 * GET /health/ready — indica si el backend puede servir queries reales.
 * Distinto de /health/live: ready=503 si falta el probe real (ver R6 del plan).
 */
export function useHealthReady() {
  return useQuery({
    queryKey: ['health', 'ready'],
    queryFn: async () => {
      const { data, response } = await apiClient.GET('/health/ready', {});
      return { status: response.status, body: (data ?? {}) as ReadyBody };
    },
    refetchInterval: 30_000,
    staleTime: 10_000,
    retry: 1,
  });
}
