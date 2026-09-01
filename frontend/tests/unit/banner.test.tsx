import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Banner } from '@/components/ui/banner';

describe('Banner', () => {
  it('renderiza la variante info por defecto', () => {
    render(<Banner>Información</Banner>);
    expect(screen.getByText('Información')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('las cuatro variantes son visualmente distintas', () => {
    const { rerender } = render(<Banner variant="info">info</Banner>);
    expect(screen.getByRole('status')).toHaveClass('bg-info/10');

    rerender(<Banner variant="success">success</Banner>);
    expect(screen.getByRole('status')).toHaveClass('bg-success/10');

    rerender(<Banner variant="warning">warning</Banner>);
    expect(screen.getByRole('status')).toHaveClass('bg-warning/10');

    rerender(<Banner variant="destructive">destructive</Banner>);
    expect(screen.getByRole('status')).toHaveClass('bg-destructive/10');
  });

  it('muestra el botón de cierre si se pasa onDismiss', async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    render(<Banner onDismiss={onDismiss}>con cierre</Banner>);
    const closeBtn = screen.getByRole('button', { name: /cerrar aviso/i });
    await user.click(closeBtn);
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it('no muestra botón de cierre si onDismiss no se pasa', () => {
    render(<Banner>sin cierre</Banner>);
    expect(screen.queryByRole('button', { name: /cerrar aviso/i })).toBeNull();
  });
});
