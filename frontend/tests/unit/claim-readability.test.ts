/**
 * La respuesta de siniestro tiene que leerse, no descifrarse.
 *
 * Antes producía "Aplicabilidad: undetermined. Decisión: conditional." —
 * jerga en inglés, sin decir qué se estableció, qué falta ni por qué.
 */
import { describe, expect, it } from 'vitest';
import { claimSummaryText, decisionLabel, applicabilityLabel } from '@/lib/claim-format';
import type { ClaimResultView } from '@/lib/claim-format';

const base: ClaimResultView = {
  kind: 'claim',
  applicability: 'not_applicable',
  convention: null,
  decision: 'not_assessed',
  party_ids: [],
  facts: [],
  contradictions: [],
  conditions: [],
  missing_information: [],
  blocks: [],
};

describe('etiquetas en castellano', () => {
  it('traduce cada valor de aplicabilidad', () => {
    expect(applicabilityLabel('applicable')).toBe('El Convenio es aplicable');
    expect(applicabilityLabel('not_applicable')).toBe('El Convenio no es aplicable');
    expect(applicabilityLabel('undetermined')).toBe('Aplicabilidad sin determinar');
  });

  it('traduce cada valor de decisión sin presentar la indeterminación como éxito', () => {
    expect(decisionLabel('resolved')).toBe('Resuelto');
    expect(decisionLabel('conditional')).toBe('Condicionado a más información');
    expect(decisionLabel('undetermined')).toBe('Sin determinar');
    expect(decisionLabel('not_assessed')).toBe('No procede valorar');
  });
});

describe('el resumen explica, no enumera enums', () => {
  it('no filtra identificadores internos al texto visible', () => {
    const text = claimSummaryText(base);
    for (const jargon of ['not_applicable', 'not_assessed', 'undetermined', 'conditional']) {
      expect(text).not.toContain(jargon);
    }
  });

  it('usa los bloques explicativos del backend cuando existen', () => {
    const text = claimSummaryText({
      ...base,
      blocks: [{ text: 'Los Convenios exigen la intervención de sólo dos vehículos.' }],
    });
    expect(text).toContain('sólo dos vehículos');
  });

  it('enumera lo que falta cuando la decisión está condicionada', () => {
    const text = claimSummaryText({
      ...base,
      applicability: 'undetermined',
      decision: 'conditional',
      conditions: ['Confirmar cuántos vehículos intervinieron.'],
      missing_information: ['Número de vehículos implicados.'],
    });
    expect(text).toContain('Confirmar cuántos vehículos intervinieron.');
    expect(text).toContain('Número de vehículos implicados.');
  });

  it('muestra las contradicciones sin resolverlas por su cuenta', () => {
    const text = claimSummaryText({
      ...base,
      contradictions: [
        {
          fact_name: 'vehicle_count',
          statements: [
            { name: 'vehicle_count', value: '2', asserted_by: 'A', source_text: 'Dos coches.' },
            { name: 'vehicle_count', value: '3', asserted_by: 'B', source_text: 'Tres coches.' },
          ],
        },
      ],
    });
    expect(text).toContain('A');
    expect(text).toContain('B');
    expect(text.toLowerCase()).toContain('contradic');
  });
});
