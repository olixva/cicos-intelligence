/**
 * El modo Automático y los modos explícitos tienen que enseñar lo mismo.
 *
 * Regresión real: existían dos constructores de payload. El de los modos
 * explícitos pasaba hechos y reglas evaluadas; el del reducer (usado en
 * Automático) devolvía `{ convention, rules: [] }`, y `rules` ni siquiera es
 * el campo que lee la tarjeta. Resultado: en Automático la tarjeta "Reglas
 * evaluadas" salía vacía aunque el backend enviaba las 14 reglas.
 */

import { describe, expect, it } from 'vitest';
import { derivePayloadForKind } from '@/lib/tool-call-payload';
import { threadReducer, initialState, type ThreadState } from '@/lib/thread-state';
import type { EnvelopeResponse } from '@/api/queries';

const claimEnvelope = {
  request_id: 'req-1',
  requested_mode: 'auto',
  resolved_mode: 'claim',
  evidence: [],
  metadata: {},
  result: {
    kind: 'claim',
    applicability: 'applicable',
    convention: null,
    decision: 'undetermined',
    party_ids: ['A', 'B'],
    facts: [{ name: 'vehicle_count', value: '2', asserted_by: 'narrator', source_text: 'A y B' }],
    contradictions: [],
    conditions: [],
    missing_information: ['Las casillas del apartado 12 de la D.A.A.'],
    blocks: [],
    rules_evaluated: [
      {
        rule_id: 'cide-requires-two-vehicles',
        result: 'not_matched',
        inputs: [{ name: 'vehicle_count', value: '2' }],
        evidence_ids: [],
        rationale: 'Intervienen dos vehículos.',
      },
      {
        rule_id: 'ascide-b10-lane-change',
        result: 'insufficient_data',
        inputs: [],
        evidence_ids: [],
        rationale: 'Faltan hechos para evaluarla.',
      },
    ],
  },
} as unknown as EnvelopeResponse;

describe('derivePayloadForKind', () => {
  it('lleva a check_rules los hechos, las reglas evaluadas y lo que falta', () => {
    const payload = derivePayloadForKind('check_rules', claimEnvelope) as {
      facts: unknown[];
      rules_evaluated: unknown[];
      missing_information: unknown[];
      applicability: string;
    };

    expect(payload.facts).toHaveLength(1);
    expect(payload.rules_evaluated).toHaveLength(2);
    expect(payload.missing_information).toHaveLength(1);
    expect(payload.applicability).toBe('applicable');
  });

  it('no inventa nada cuando el resultado no es de siniestro', () => {
    const payload = derivePayloadForKind('check_rules', {
      ...claimEnvelope,
      result: { kind: 'question' },
    } as unknown as EnvelopeResponse) as { rules_evaluated: unknown[]; convention: null };

    expect(payload.rules_evaluated).toHaveLength(0);
    expect(payload.convention).toBeNull();
  });
});

describe('RESOLVE_TOOL_PLAN (modo Automático)', () => {
  it('cierra check_rules con el mismo payload que el modo explícito', () => {
    // Estado mínimo: un assistant activo con el classify pendiente, tal y como
    // queda tras SUBMIT en modo auto.
    const assistantId = 'assistant-1';
    const base: ThreadState = {
      ...initialState('auto'),
      activeAssistantId: assistantId,
      messages: [
        {
          id: assistantId,
          role: 'assistant',
          status: 'streaming',
          streamedText: '',
          toolCalls: [
            {
              id: 'tc-classify',
              kind: 'classify',
              label: 'Clasificando…',
              status: 'pending',
              startedAt: 0,
            },
          ],
          citations: [],
          createdAt: 0,
        },
      ],
    };

    const next = threadReducer(base, {
      type: 'RESOLVE_TOOL_PLAN',
      envelope: claimEnvelope,
      requested_mode: 'auto',
    });

    const assistant = next.messages.find((m) => m.id === assistantId);
    if (!assistant || assistant.role !== 'assistant') throw new Error('assistant no encontrado');
    const checkRules = assistant.toolCalls.find((tc) => tc.kind === 'check_rules');
    expect(checkRules).toBeDefined();
    expect(checkRules?.status).toBe('done');

    const payload = checkRules?.payload as { rules_evaluated: unknown[]; facts: unknown[] };
    expect(payload.rules_evaluated).toHaveLength(2);
    expect(payload.facts).toHaveLength(1);
    expect(payload).toEqual(derivePayloadForKind('check_rules', claimEnvelope));
  });
});
