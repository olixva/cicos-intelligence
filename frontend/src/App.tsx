import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import IndexRoute from '@/routes/_index';
import { EvidenceProvider } from '@/features/evidence/evidence-context';

/**
 * App — proveedores globales. QueryClient con defaults sensatos:
 *   - retry 1 (los errores deben llegar rápido al UI)
 *   - staleTime 30s (evita refetch innecesario)
 *   - refetchOnWindowFocus false (no agresivo)
 */
export default function App() {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
          mutations: {
            retry: 0,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={client}>
      <EvidenceProvider>
        <IndexRoute />
      </EvidenceProvider>
    </QueryClientProvider>
  );
}
