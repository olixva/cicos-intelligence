import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { EnvelopeResponse } from '@/api/queries';
import type { StreamingEvent } from '@/lib/streaming-client';

// Mock de los hooks de health para que BannerSystem no dispare fetches reales.
vi.mock('@/api/health', () => ({
  useHealthLive: () => ({ isError: false, isLoading: false, data: null }),
  useHealthReady: () => ({ isError: false, isLoading: false, data: null }),
}));

const envelope: EnvelopeResponse = {
  request_id: 'req-abc',
  requested_mode: 'question',
  resolved_mode: 'question',
  metadata: {},
  evidence: [
    {
      evidence_id: 'ev-1',
      document_hash: 'abc123',
      pdf_page: 4,
      delivery: 'text',
    },
  ],
  result: {
    kind: 'question',
    status: 'answered',
    blocks: [{ text: 'Respuesta con cita.', evidence_ids: ['ev-1'] }],
  },
};

// Mock del streaming client: emite started + completed de forma síncrona.
vi.mock('@/lib/streaming-client', () => ({
  streamQuery: (_input: unknown, opts: { onEvent: (event: StreamingEvent) => void }) => {
    opts.onEvent({ type: 'started', requestId: 'req-abc', mode: 'question' });
    opts.onEvent({ type: 'completed', response: envelope });
    return { done: Promise.resolve(), controller: new AbortController() };
  },
}));

// Importamos DESPUÉS de los mocks.
import IndexRoute from '@/routes/_index';

function renderRoute() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });
  return render(
    <QueryClientProvider client={qc}>
      <IndexRoute />
    </QueryClientProvider>,
  );
}

describe('PdfOverlay src (Finding G3 #1 — 422 por falta de `version`)', () => {
  beforeAll(() => {
    // jsdom no implementa scrollIntoView (usado por el auto-scroll del Thread).
    Element.prototype.scrollIntoView = vi.fn();
  });

  it('pasa el document_hash como query param `version` al abrir una cita', async () => {
    const user = userEvent.setup();
    renderRoute();

    const input = screen.getByLabelText(/texto de la consulta/i);
    await user.type(input, '¿Qué dice el manual?');
    await user.keyboard('{Enter}');

    const chip = await screen.findByRole('button', {
      name: /Abrir evidencia ev-1, página 4/i,
    });
    await user.click(chip);

    const link = await screen.findByRole('link', { name: /Ver PDF en nueva pestaña/i });
    expect(link).toHaveAttribute('href', '/api/v1/manual/pdf?version=abc123');
  });
});
