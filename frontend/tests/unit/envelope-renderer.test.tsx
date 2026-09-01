import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EnvelopeRenderer } from '@/components/envelope-renderer';
import type { EnvelopeResponse } from '@/api/queries';

// Mockeamos el context de evidencia para que EvidenceChip no falle.
vi.mock('@/features/evidence/evidence-context', () => ({
  useEvidence: () => ({
    open: null,
    openEvidence: vi.fn(),
    closeEvidence: vi.fn(),
    hasOpen: false,
  }),
}));

const baseEnvelope: Pick<EnvelopeResponse, 'request_id' | 'requested_mode' | 'resolved_mode'> = {
  request_id: 'req-test',
  requested_mode: 'auto',
  resolved_mode: 'question',
};

describe('EnvelopeRenderer', () => {
  it('rama question muestra bloques y estado', () => {
    const response = {
      ...baseEnvelope,
      evidence: [
        { evidence_id: 'ev-1', document_hash: 'hash', pdf_page: 7, delivery: 'text' as const },
      ],
      metadata: {},
      result: {
        kind: 'question' as const,
        status: 'answered' as const,
        blocks: [{ text: 'Párrafo 1', evidence_ids: ['ev-1'] }],
        trace_id: 'trace-1',
      },
    };
    render(<EnvelopeRenderer response={response} />);
    expect(screen.getByText(/Párrafo 1/)).toBeInTheDocument();
    expect(screen.getByText(/Respondida/)).toBeInTheDocument();
  });

  it('rama claim muestra aplicabilidad, convention y decision', () => {
    const response = {
      ...baseEnvelope,
      requested_mode: 'claim' as const,
      resolved_mode: 'claim' as const,
      evidence: [],
      metadata: {},
      result: {
        kind: 'claim' as const,
        applicability: 'applicable' as const,
        decision: 'resolved' as const,
        convention: 'CIDE' as const,
        trace_id: 'trace-claim',
      },
    };
    render(<EnvelopeRenderer response={response} />);
    expect(screen.getByText(/Convenio: CIDE/)).toBeInTheDocument();
    expect(screen.getByText(/Aplicable/)).toBeInTheDocument();
    expect(screen.getByText(/Resuelto/)).toBeInTheDocument();
  });

  it('rama clarification muestra mensaje y missing_fields', () => {
    const response = {
      ...baseEnvelope,
      resolved_mode: 'clarification' as const,
      evidence: [],
      metadata: {},
      result: {
        kind: 'clarification' as const,
        message: 'Faltan datos del vehículo B',
        missing_fields: ['matricula_b', 'velocidad_b'],
      },
    };
    render(<EnvelopeRenderer response={response} />);
    expect(screen.getByText(/Faltan datos del vehículo B/)).toBeInTheDocument();
    expect(screen.getByText(/matricula_b/)).toBeInTheDocument();
  });

  it('caso unknown: kind forzado a never rompe el switch y muestra fallback', () => {
    // Forzamos un `kind` que no existe en el union para verificar que el
    // `satisfies never` compila pero el render defensivo se ejecuta.
    // Esto NO es un error TS porque usamos `as never` en el mock.
    const fakeResult = { kind: 'unknown' as never } as unknown as EnvelopeResponse['result'];
    const response = {
      ...baseEnvelope,
      evidence: [],
      metadata: {},
      result: fakeResult,
    };
    render(<EnvelopeRenderer response={response} />);
    expect(screen.getByText(/Tipo de resultado desconocido/)).toBeInTheDocument();
  });
});
