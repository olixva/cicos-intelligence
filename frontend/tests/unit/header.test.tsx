import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock de los hooks de health para que BannerSystem no dispare fetches
// reales durante el test (Finding G1 #3 — accesibilidad del header).
vi.mock('@/api/health', () => ({
  useHealthLive: () => ({ isError: false, isLoading: false, data: null }),
  useHealthReady: () => ({ isError: false, isLoading: false, data: null }),
}));

// Importamos DESPUÉS del mock para que el módulo sustituido se cargue.
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

describe('IndexRoute header (Finding G1 #3)', () => {
  it('muestra el botón "Modo administrador" en el header', () => {
    renderRoute();
    const btn = screen.getByRole('button', { name: 'Modo administrador' });
    expect(btn).toBeInTheDocument();
  });

  it('el botón "Modo administrador" tiene title accesible', () => {
    renderRoute();
    const btn = screen.getByRole('button', { name: 'Modo administrador' });
    expect(btn).toHaveAttribute('title', 'Modo administrador');
  });

  it('abre el panel de administración al pulsar el modo administrador', async () => {
    const user = userEvent.setup();
    renderRoute();
    // Antes: el EmptyState muestra 5 ejemplos (5 buttons con aria-label "Probar ejemplo: …").
    expect(
      screen.getAllByRole('button', { name: /Probar ejemplo:/i }).length,
    ).toBeGreaterThanOrEqual(1);
    // Tras pulsar "Nueva consulta", el reducer NEW_THREAD debe dejar los
    // mensajes a []. Como ya estaban vacíos, el empty state sigue visible,
    // pero el thread debe seguir siendo funcional (no debe explotar).
    await user.click(screen.getByRole('button', { name: 'Modo administrador' }));
    expect(screen.getByRole('heading', { name: 'Ingesta del manual' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Volver al chat' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Modo administrador' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Volver al chat' }));
    expect(screen.getByRole('button', { name: 'Modo administrador' })).toBeInTheDocument();
  });
});
