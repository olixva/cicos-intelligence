import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CitationChip } from '@/components/citation/citation-chip';

describe('CitationChip', () => {
  it('muestra evidencia ID, página y label accesible correcto', () => {
    render(
      <CitationChip
        evidenceId="ev-001"
        pdfPage={12}
        label="CIDE art. 12"
        aria-label="custom-aria"
      />,
    );
    const btn = screen.getByRole('button', { name: /custom-aria/i });
    expect(btn).toBeInTheDocument();
    // Cuando label está presente, el chip muestra el label en lugar del ID.
    expect(btn).toHaveTextContent('CIDE art. 12');
    expect(btn).toHaveTextContent('p.12');
  });

  it('label por defecto incluye evidence_id y página', () => {
    render(<CitationChip evidenceId="ev-xyz" pdfPage={3} />);
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('aria-label')).toMatch(/ev-xyz/);
    expect(btn.getAttribute('aria-label')).toMatch(/3/);
  });

  it('invoca onClick al hacer click', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<CitationChip evidenceId="ev-001" pdfPage={1} onClick={onClick} />);
    await user.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('marca aria-pressed cuando active=true', () => {
    render(<CitationChip evidenceId="ev-001" pdfPage={1} active />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-pressed', 'true');
  });

  it('usa font-mono para el ID', () => {
    const { container } = render(<CitationChip evidenceId="ev-001" pdfPage={1} />);
    // El span "p.X" lleva font-mono text-[10px] — verificamos que existe.
    expect(container.querySelector('.font-mono')).toBeInTheDocument();
  });
});
