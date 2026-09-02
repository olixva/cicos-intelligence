import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Footer } from '@/components/footer';

describe('Footer (Finding G2 #1)', () => {
  it('muestra el request_id pasado en la prop `requestId`', () => {
    render(<Footer requestId="11111111-2222-4333-8444-555555555555" />);
    const code = screen.getByText('11111111-2222-4333-8444-555555555555');
    expect(code).toBeInTheDocument();
  });

  it('prioriza `response.request_id` sobre `requestId`', () => {
    render(
      <Footer
        requestId="11111111-2222-4333-8444-555555555555"
        response={
          {
            request_id: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
            requested_mode: 'question',
            resolved_mode: 'question',
            result: { kind: 'question', status: 'answered', blocks: [], trace_id: null },
            evidence: [],
            metadata: {},
          } as never
        }
      />,
    );
    const code = screen.getByText('aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee');
    expect(code).toBeInTheDocument();
  });

  it('persiste estable tras N re-renders sin respuesta ni requestId prop', () => {
    const { rerender } = render(<Footer />);
    const code = screen.getByText(/^[0-9a-f-]{36}$/i);
    const firstId = code.textContent;
    expect(firstId).toMatch(/^[0-9a-f-]{36}$/i);

    // Forzamos N re-renders del Footer sin tocar props: el id debe
    // permanecer estable (memoizado en `useState` lazy init).
    for (let i = 0; i < 10; i += 1) {
      rerender(<Footer />);
    }
    expect(screen.getByText(/^[0-9a-f-]{36}$/i).textContent).toBe(firstId);
  });

  it('el id fallback cambia tras un re-mount del componente', () => {
    const { unmount } = render(<Footer />);
    const firstId = screen.getByText(/^[0-9a-f-]{36}$/i).textContent;

    unmount();

    render(<Footer />);
    const secondId = screen.getByText(/^[0-9a-f-]{36}$/i).textContent;

    // Cada montaje genera un id nuevo (probabilistic). Como `uuidv4`
    // tiene 122 bits de entropía, la probabilidad de colisión es
    // ~1/2^122; si el test falla por colisión hay un bug real.
    expect(secondId).toMatch(/^[0-9a-f-]{36}$/i);
    expect(secondId).not.toBe(firstId);
  });
});
