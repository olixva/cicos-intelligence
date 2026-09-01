import type { components } from '@/types/api.gen';

export type EnvelopeRequest = components['schemas']['EnvelopeRequest'];
export type EnvelopeResponse = components['schemas']['EnvelopeResponse'];
export type EvidenceItem = components['schemas']['EvidenceItem'];

/** Tres ramas del discriminated union `result`. */
export type QuestionResult = Extract<EnvelopeResponse['result'], { kind: 'question' }>;
export type ClaimResult = Extract<EnvelopeResponse['result'], { kind: 'claim' }>;
export type ClarificationResult = Extract<EnvelopeResponse['result'], { kind: 'clarification' }>;

/** Modos de UI (lo que el usuario elige en el ModeSelector). */
export type UiMode = 'question' | 'claim' | 'auto';

export function isUiMode(value: unknown): value is UiMode {
  return value === 'question' || value === 'claim' || value === 'auto';
}
