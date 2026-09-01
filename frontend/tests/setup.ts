import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Limpia el DOM después de cada test para evitar contaminación entre casos.
afterEach(() => {
  cleanup();
});
