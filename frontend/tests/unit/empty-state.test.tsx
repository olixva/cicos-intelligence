import { render, screen } from '@testing-library/react';

import { EmptyState } from '@/components/empty-state/empty-state';

const cases = [
  { case_id: 'q1', text: 'Pregunta corta', language: 'es' as const, expected_intent: 'question' as const },
  { case_id: 'q2', text: 'Pregunta larga', language: 'es' as const, expected_intent: 'question' as const },
  { case_id: 'c1', text: 'Siniestro sin datos', language: 'es' as const, expected_intent: 'claim' as const },
  { case_id: 'c2', text: 'Siniestro no aplicable', language: 'es' as const, expected_intent: 'claim' as const },
  { case_id: 'c3', text: 'Siniestro resuelto', language: 'es' as const, expected_intent: 'claim' as const },
];

test('muestra etiquetas neutrales y tarjetas de altura uniforme', () => {
  render(<EmptyState cases={cases} onSelect={() => undefined} />);

  expect(screen.getAllByText('Pregunta')).toHaveLength(2);
  expect(screen.getAllByText('Siniestro')).toHaveLength(3);
  expect(screen.getAllByRole('button').every((card) => card.className.includes('min-h-32'))).toBe(true);
  expect(screen.getByText('Pregunta corta').className).toContain('line-clamp-3');
  expect(screen.getByText('Pregunta larga').className).toContain('line-clamp-3');
  expect(screen.getByText('Siniestro sin datos').className).toContain('line-clamp-3');
});
