import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryForm } from '@/components/query-form';

describe('QueryForm', () => {
  it('muestra el contador y arranca en 0/2000', () => {
    render(<QueryForm onSubmit={() => {}} />);
    const counter = screen.getByText(/0 \/ 2000/);
    expect(counter).toBeInTheDocument();
  });

  it('el botón Enviar está deshabilitado con textarea vacío', () => {
    render(<QueryForm onSubmit={() => {}} />);
    const submit = screen.getByRole('button', { name: /enviar consulta/i });
    expect(submit).toBeDisabled();
  });

  it('habilita el botón cuando hay texto no-whitespace', async () => {
    const user = userEvent.setup();
    render(<QueryForm onSubmit={() => {}} />);
    const input = screen.getByLabelText(/texto de la consulta/i);
    await user.type(input, 'hola mundo');
    const submit = screen.getByRole('button', { name: /enviar consulta/i });
    expect(submit).toBeEnabled();
  });

  it('invoca onSubmit con el texto trimmeado', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<QueryForm onSubmit={onSubmit} />);
    const input = screen.getByLabelText(/texto de la consulta/i);
    await user.type(input, '  pregunta con espacios  ');
    const submit = screen.getByRole('button', { name: /enviar consulta/i });
    await user.click(submit);
    expect(onSubmit).toHaveBeenCalledWith('pregunta con espacios');
  });

  it('muestra el botón Detener cuando busy y onCancel', () => {
    const onCancel = vi.fn();
    render(<QueryForm onSubmit={() => {}} busy onCancel={onCancel} />);
    expect(screen.getByRole('button', { name: /detener/i })).toBeInTheDocument();
  });
});
