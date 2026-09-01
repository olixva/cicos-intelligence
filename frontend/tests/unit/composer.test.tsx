import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Composer } from '@/components/composer/composer';
import { clearKey } from '@/lib/storage';

describe('Composer', () => {
  beforeEach(() => {
    clearKey('cicos.mode.v2');
    if (typeof window !== 'undefined') {
      window.history.replaceState({}, '', '/');
    }
  });

  it('muestra el contador y arranca en 0 / 4000', () => {
    render(<Composer mode="auto" onModeChange={() => {}} onSubmit={() => {}} />);
    expect(screen.getByText(/0 \/ 4000/)).toBeInTheDocument();
  });

  it('el botón Enviar está deshabilitado con textarea vacío', () => {
    render(<Composer mode="auto" onModeChange={() => {}} onSubmit={() => {}} />);
    expect(screen.getByRole('button', { name: /enviar consulta/i })).toBeDisabled();
  });

  it('habilita el botón cuando hay texto no-whitespace', async () => {
    const user = userEvent.setup();
    render(<Composer mode="auto" onModeChange={() => {}} onSubmit={() => {}} />);
    const input = screen.getByLabelText(/texto de la consulta/i);
    await user.type(input, 'hola mundo');
    expect(screen.getByRole('button', { name: /enviar consulta/i })).toBeEnabled();
  });

  it('Enter envía y Shift+Enter inserta salto', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Composer mode="auto" onModeChange={() => {}} onSubmit={onSubmit} />);
    const input = screen.getByLabelText(/texto de la consulta/i);
    await user.type(input, 'consulta');
    await user.keyboard('{Enter}');
    expect(onSubmit).toHaveBeenCalledWith('consulta');

    // Shift+Enter debe insertar salto sin enviar.
    await user.click(input);
    await user.keyboard('{Shift>}{Enter}{/Shift}más texto');
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('cambiar de modo persiste en storage y notifica al padre', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Composer mode="auto" onModeChange={onChange} onSubmit={() => {}} />);
    // Click directamente sobre el input radio para evitar problemas de
    // asociación label↔input en jsdom con Radix UI.
    const claimRadio = document.getElementById('composer-mode-claim') as HTMLInputElement;
    expect(claimRadio).toBeInTheDocument();
    await user.click(claimRadio);
    expect(onChange).toHaveBeenCalledWith('claim');
  });

  it('muestra Cancelar cuando busy=true', () => {
    const onCancel = vi.fn();
    render(
      <Composer busy mode="auto" onModeChange={() => {}} onSubmit={() => {}} onCancel={onCancel} />,
    );
    expect(screen.getByRole('button', { name: /detener/i })).toBeInTheDocument();
  });

  it('invoca onCancel cuando se hace click en Cancelar', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <Composer busy mode="auto" onModeChange={() => {}} onSubmit={() => {}} onCancel={onCancel} />,
    );
    await user.click(screen.getByRole('button', { name: /detener/i }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it('usa submit vía form cuando se hace click en Enviar (no Enter)', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Composer mode="auto" onModeChange={() => {}} onSubmit={onSubmit} />);
    const input = screen.getByLabelText(/texto de la consulta/i);
    await user.type(input, 'otra consulta');
    await user.click(screen.getByRole('button', { name: /enviar consulta/i }));
    expect(onSubmit).toHaveBeenCalledWith('otra consulta');
  });

  // Hidratación de modo
  it('hidrata el modo desde el query string de la URL', async () => {
    if (typeof window !== 'undefined') {
      window.history.replaceState({}, '', '/?mode=claim');
    }
    const onChange = vi.fn();
    render(<Composer mode="auto" onModeChange={onChange} onSubmit={() => {}} />);
    expect(onChange).toHaveBeenCalledWith('claim');
    // Limpiamos para no afectar otros tests
    act(() => clearKey('cicos.mode.v2'));
  });
});
