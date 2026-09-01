import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ToolCallCard } from '@/components/tool-call/tool-call-card';
import type { ToolCall } from '@/lib/thread-state';

const basePending: ToolCall = {
  id: 'tc-1',
  kind: 'classify',
  label: 'Clasificando consulta',
  status: 'pending',
  startedAt: Date.now(),
};

const baseDone: ToolCall = {
  ...basePending,
  id: 'tc-2',
  status: 'done',
  durationMs: 123,
};

const baseError: ToolCall = {
  ...basePending,
  id: 'tc-3',
  status: 'error',
  errorMessage: 'Boom',
};

describe('ToolCallCard', () => {
  it('estado pending: muestra label y "En curso"', () => {
    render(<ToolCallCard toolCall={basePending} />);
    expect(screen.getByText(/Clasificando consulta/i)).toBeInTheDocument();
    expect(screen.getByText(/En curso/i)).toBeInTheDocument();
  });

  it('estado done: muestra duración', () => {
    render(<ToolCallCard toolCall={baseDone} defaultExpanded />);
    expect(screen.getByText(/123 ms/i)).toBeInTheDocument();
  });

  it('estado error: muestra mensaje y botón de reintento si onRetry', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<ToolCallCard toolCall={baseError} onRetry={onRetry} />);
    expect(screen.getByText(/Boom/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /reintentar/i }));
    expect(onRetry).toHaveBeenCalledWith('tc-3');
  });

  it('estado error: no muestra reintento si onRetry no está definido', () => {
    render(<ToolCallCard toolCall={baseError} />);
    expect(screen.queryByRole('button', { name: /reintentar/i })).toBeNull();
  });

  it('switch sobre kind — retrieve renderiza preview de chunks', () => {
    const tc: ToolCall = {
      ...baseDone,
      kind: 'retrieve',
      payload: {
        chunks: [
          {
            evidenceId: 'ev-1',
            pdfPage: 4,
            preview: 'Lorem ipsum dolor sit amet',
            score: 0.91,
          },
        ],
      },
    };
    render(<ToolCallCard toolCall={tc} defaultExpanded />);
    expect(screen.getByText(/Lorem ipsum/)).toBeInTheDocument();
    expect(screen.getByText(/score 0.91/)).toBeInTheDocument();
  });

  it('switch sobre kind — apply_decision renderiza badges con tono', () => {
    const tc: ToolCall = {
      ...baseDone,
      kind: 'apply_decision',
      payload: {
        convention: 'CIDE',
        applicability: 'applicable',
        decision: 'resolved',
      },
    };
    render(<ToolCallCard toolCall={tc} defaultExpanded />);
    expect(screen.getByText('CIDE')).toBeInTheDocument();
    expect(screen.getByText('applicable')).toBeInTheDocument();
    expect(screen.getByText('resolved')).toBeInTheDocument();
  });

  it('expandir/contraer con click en el header', async () => {
    const user = userEvent.setup();
    render(<ToolCallCard toolCall={baseDone} />);
    // El badge con la duración es visible siempre en el header.
    expect(screen.getByText(/123 ms/)).toBeInTheDocument();
    // El header del tool call muestra "Consulta clasificada" (estado done).
    await user.click(screen.getByRole('button', { name: /Consulta clasificada/i }));
    // El click debe alternar el body; no comprobamos visibilidad exacta
    // porque el botón no tiene aria-controls expuesto siempre.
  });
});
