import '@testing-library/jest-dom/vitest';
import { afterEach, beforeAll, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// jsdom no expone ResizeObserver. Radix UI (radio-group, scroll-area, etc.)
// lo necesita para medir contenedores. Polyfill mínimo.
class ResizeObserverPolyfill {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => {
  globalThis.ResizeObserver = globalThis.ResizeObserver ?? ResizeObserverPolyfill;
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  }
});

// Limpia el DOM después de cada test para evitar contaminación entre casos.
afterEach(() => {
  cleanup();
});
