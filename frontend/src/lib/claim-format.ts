/**
 * Traducción y redacción del resultado de siniestro.
 *
 * El backend devuelve enums (`not_applicable`, `conditional`, …) porque son
 * un contrato estable; la interfaz no debe mostrarlos tal cual. Este módulo
 * los convierte en castellano y compone un texto que dice qué se estableció,
 * qué falta y qué contradicciones quedaron sin resolver.
 *
 * Regla que no se rompe: una indeterminación nunca se presenta como éxito.
 */

export type Applicability = 'applicable' | 'not_applicable' | 'undetermined';
export type Decision = 'resolved' | 'conditional' | 'undetermined' | 'not_assessed';

export interface ClaimFactView {
  name: string;
  value?: string | null;
  asserted_by?: string | null;
  source_text?: string;
}

export interface ClaimResultView {
  kind: 'claim';
  applicability: Applicability;
  convention: 'CIDE' | 'ASCIDE' | null;
  decision: Decision;
  party_ids?: readonly string[];
  facts?: readonly ClaimFactView[];
  contradictions?: readonly { fact_name: string; statements: readonly ClaimFactView[] }[];
  conditions?: readonly string[];
  missing_information?: readonly string[];
  blocks?: readonly { text?: string }[];
}

const APPLICABILITY: Record<Applicability, string> = {
  applicable: 'El Convenio es aplicable',
  not_applicable: 'El Convenio no es aplicable',
  undetermined: 'Aplicabilidad sin determinar',
};

const DECISION: Record<Decision, string> = {
  resolved: 'Resuelto',
  conditional: 'Condicionado a más información',
  undetermined: 'Sin determinar',
  not_assessed: 'No procede valorar',
};

export function applicabilityLabel(value: Applicability): string {
  return APPLICABILITY[value];
}

export function decisionLabel(value: Decision): string {
  return DECISION[value];
}

/** ¿Debe presentarse este resultado como conclusión firme? */
export function isConclusive(decision: Decision): boolean {
  return decision === 'resolved';
}

/**
 * Titular del resultado cuando el backend no ha citado ningún bloque.
 *
 * Separa los dos planos que el manual distingue: si el Convenio se aplica
 * (ámbito) y si puede atribuirse la responsabilidad (culpabilidad). Que el
 * Convenio sea aplicable y la culpa quede sin determinar no es contradictorio;
 * es el resultado correcto cuando faltan las circunstancias de la D.A.A.
 */
function headline(
  applicability: Applicability,
  decision: Decision,
  convention: string,
): string {
  if (applicability === 'applicable' && decision === 'undetermined') {
    return `El Convenio es aplicable${convention}, pero la culpabilidad no puede determinarse con los datos aportados.`;
  }
  if (applicability === 'applicable' && decision === 'conditional') {
    return `El Convenio es aplicable${convention}, con una conclusión condicionada a la información que falta.`;
  }
  if (applicability === 'not_applicable') {
    return `${APPLICABILITY.not_applicable}: no procede tramitar el siniestro por esta vía.`;
  }
  if (applicability === 'undetermined') {
    return `${APPLICABILITY.undetermined}: faltan datos para saber si el Convenio entra en juego.`;
  }
  return `${APPLICABILITY[applicability]}${convention}. **${DECISION[decision]}.**`;
}

/**
 * Redacta el resultado en prosa. Prioriza los bloques explicativos que el
 * backend ya cita contra el manual; sólo si no hay ninguno recurre a la
 * etiqueta de aplicabilidad.
 */
export function claimSummaryText(result: ClaimResultView): string {
  const parts: string[] = [];

  const blocks = (result.blocks ?? []).map((b) => b.text?.trim()).filter(Boolean) as string[];
  if (blocks.length > 0) {
    parts.push(blocks.join('\n\n'));
    if (!isConclusive(result.decision)) {
      parts.push(`**${DECISION[result.decision]}.**`);
    }
  } else {
    // Una frase, no dos fragmentos sueltos: «El Convenio es aplicable.» seguido
    // de «Sin determinar.» se leía como una contradicción. Aplicabilidad y
    // culpabilidad son dos planos distintos y el texto tiene que decirlo.
    const convention = result.convention ? ` (${result.convention})` : '';
    parts.push(headline(result.applicability, result.decision, convention));
  }

  const conditions = result.conditions ?? [];
  if (conditions.length > 0) {
    parts.push(
      ['Para poder concluir hace falta:', ...conditions.map((c) => `- ${c}`)].join('\n'),
    );
  }

  const missing = result.missing_information ?? [];
  if (missing.length > 0) {
    parts.push(['Datos que faltan:', ...missing.map((m) => `- ${m}`)].join('\n'));
  }

  const contradictions = result.contradictions ?? [];
  if (contradictions.length > 0) {
    const lines = contradictions.map((c) => {
      const versions = c.statements
        .map((s) => `${s.asserted_by ?? 'una parte'} dice «${s.value ?? s.source_text ?? ''}»`)
        .join('; ');
      return `- ${c.fact_name}: ${versions}`;
    });
    parts.push(
      [
        'Las versiones son contradictorias y no se resuelven por cuenta propia:',
        ...lines,
      ].join('\n'),
    );
  }

  return parts.join('\n\n');
}
