/**
 * Payload de cada tarjeta de tool call, derivado del envelope del backend.
 *
 * Existía duplicado: una versión completa en `routes/_index.tsx` (modos
 * explícitos) y otra recortada en `lib/thread-state.ts` (modo Automático),
 * que devolvía `{ convention, rules: [] }`. `rules` ni siquiera es el campo
 * que lee la tarjeta —lee `rules_evaluated`—, así que en Automático la
 * tarjeta "Reglas evaluadas" salía vacía aunque el backend enviaba las 14
 * reglas evaluadas. Una sola implementación compartida evita que los dos
 * caminos vuelvan a divergir.
 */

import type { EnvelopeResponse } from '@/api/queries';

export type ToolCallKind = 'classify' | 'retrieve' | 'check_rules' | 'apply_decision';

export function derivePayloadForKind(kind: ToolCallKind, envelope: EnvelopeResponse): unknown {
  switch (kind) {
    case 'classify':
      return { mode: envelope.resolved_mode };
    case 'retrieve':
      return {
        chunks: (envelope.evidence ?? []).map((e) => ({
          evidenceId: e.evidence_id,
          pdfPage: e.pdf_page,
          preview: '',
          score: undefined,
        })),
      };
    case 'check_rules':
      if (envelope.result && envelope.result.kind === 'claim') {
        // Lo que el backend evaluó de verdad: hechos atribuidos, reglas
        // ejecutadas (incluidas las que no casan y las no comprobables) y
        // qué falta por confirmar.
        return {
          convention: envelope.result.convention,
          applicability: envelope.result.applicability,
          facts: envelope.result.facts ?? [],
          contradictions: envelope.result.contradictions ?? [],
          missing_information: envelope.result.missing_information ?? [],
          rules_evaluated: envelope.result.rules_evaluated ?? [],
        };
      }
      return {
        convention: null,
        facts: [],
        contradictions: [],
        missing_information: [],
        rules_evaluated: [],
      };
    case 'apply_decision':
      if (envelope.result && envelope.result.kind === 'claim') {
        return {
          convention: envelope.result.convention,
          applicability: envelope.result.applicability,
          decision: envelope.result.decision,
          conditions: envelope.result.conditions ?? [],
        };
      }
      if (envelope.result && envelope.result.kind === 'clarification') {
        return {
          convention: null,
          applicability: 'undetermined',
          decision: 'undetermined',
        };
      }
      return { convention: null, applicability: null, decision: null };
    default: {
      const exhaustive: never = kind;
      void exhaustive;
      return null;
    }
  }
}
