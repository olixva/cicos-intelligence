import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ModeSelector } from '@/components/mode-selector';
import { loadKey, clearKey, saveKey } from '@/lib/storage';

describe('ModeSelector', () => {
  beforeEach(() => {
    clearKey('cicos.mode.v1');
    if (typeof window !== 'undefined') {
      window.history.replaceState({}, '', '/');
    }
  });

  it('hidrata con "auto" por defecto cuando no hay storage ni URL', () => {
    render(<ModeSelector value="auto" onChange={() => {}} />);
    const autoRadio = screen.getByLabelText('Automático');
    expect(autoRadio).toBeChecked();
  });

  it('lee el modo desde el query string y lo persiste', async () => {
    window.history.replaceState({}, '', '/?mode=claim');
    const onChange = vi.fn();
    render(<ModeSelector value="auto" onChange={onChange} />);

    expect(onChange).toHaveBeenCalledWith('claim');
    expect(loadKey('cicos.mode.v1')).toBe('claim');
  });

  it('lee el modo desde el storage cuando no hay URL', () => {
    // Usamos saveKey (que cae a URL state si LS no está disponible, p.ej.
    // en jsdom sin flag --localstorage-file).
    saveKey('cicos.mode.v1', 'question');
    const onChange = vi.fn();
    render(<ModeSelector value="auto" onChange={onChange} />);
    expect(onChange).toHaveBeenCalledWith('question');
  });

  it('al cambiar de opción, persiste y notifica', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ModeSelector value="auto" onChange={onChange} />);

    await user.click(screen.getByLabelText('Siniestro'));
    expect(onChange).toHaveBeenLastCalledWith('claim');
    expect(loadKey('cicos.mode.v1')).toBe('claim');
  });
});
