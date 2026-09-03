import { CheckCircle2, XCircle, CircleDashed, FileText, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * ClaimAnalysisPanel — vista estructurada de un `ClaimResult` del backend.
 *
 * El backend envía el envelope con `result.kind === "claim"` y dentro
 * los campos `applicability`, `convention`, `decision`, `facts`,
 * `rules_evaluated`, etc. La burbuja del assistant ya pinta los
 * `blocks` (texto markdown). Este panel añade lo demás en formato
 * escaneable: badges arriba (3 etiquetas grandes), lista de reglas
 * evaluadas con su status, y lista de hechos extraídos.
 *
 * El render de las reglas sigue el lenguaje del ruleset: cada status
 * (`matched` / `not_matched` / `insufficient_data`) tiene icono y
 * color. El `rationale` se muestra truncado porque suele ser largo.
 */

// Tipos basados en la forma serializada en `api.gen.ts` (ClaimResult).
// `rules_evaluated` está tipado como `Record<string, unknown>[]` en el
// gen — tipamos aquí la forma real que viene del backend.
export interface ClaimRuleEvaluation {
  rule_id: string;
  inputs?: ReadonlyArray<readonly [string, string] | Record<string, string>>;
  result: 'matched' | 'not_matched' | 'insufficient_data';
  evidence_ids?: ReadonlyArray<string>;
  rationale: string;
}

export interface ClaimFact {
  name: string;
  value: string | null;
  asserted_by: string | null;
  source_text: string;
}

export interface ClaimAnalysis {
  applicability: 'applicable' | 'not_applicable' | 'undetermined';
  convention: 'CIDE' | 'ASCIDE' | null;
  decision: 'resolved' | 'conditional' | 'undetermined' | 'not_assessed';
  facts?: ReadonlyArray<ClaimFact>;
  rules_evaluated?: ReadonlyArray<ClaimRuleEvaluation>;
  conditions?: ReadonlyArray<string>;
  contradictions?: ReadonlyArray<unknown>;
  party_ids?: ReadonlyArray<string>;
  missing_information?: ReadonlyArray<string>;
}

const APPLICABILITY_LABEL: Record<ClaimAnalysis['applicability'], string> = {
  applicable: 'Convenio aplicable',
  not_applicable: 'Convenio no aplicable',
  undetermined: 'Convenio indeterminado',
};

const APPLICABILITY_TONE: Record<ClaimAnalysis['applicability'], string> = {
  applicable: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30',
  not_applicable: 'bg-muted text-muted-foreground border-border',
  undetermined: 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30',
};

const DECISION_LABEL: Record<ClaimAnalysis['decision'], string> = {
  resolved: 'Culpabilidad determinada',
  conditional: 'Culpabilidad con condiciones',
  undetermined: 'Culpabilidad indeterminada',
  not_assessed: 'Convenio no evaluado',
};

const DECISION_TONE: Record<ClaimAnalysis['decision'], string> = {
  resolved: 'bg-emerald-600 text-white border-emerald-700',
  conditional: 'bg-amber-500 text-white border-amber-600',
  undetermined: 'bg-zinc-500 text-white border-zinc-600',
  not_assessed: 'bg-zinc-400 text-white border-zinc-500',
};

const RULE_STATUS_META: Record<ClaimRuleEvaluation['result'], {
  label: string;
  icon: typeof CheckCircle2;
  tone: string;
}> = {
  matched: {
    label: 'Disparada',
    icon: CheckCircle2,
    tone: 'text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  },
  not_matched: {
    label: 'No disparada',
    icon: XCircle,
    tone: 'text-zinc-500 dark:text-zinc-400 bg-zinc-500/10 border-zinc-500/30',
  },
  insufficient_data: {
    label: 'Datos insuficientes',
    icon: CircleDashed,
    tone: 'text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/30',
  },
};

function _badgeClass(tone: string): string {
  return cn(
    'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium leading-none',
    tone,
  );
}

function _formatValue(value: string | null): string {
  if (value === null) return '—';
  // Boolean-like: mostrar como ✓/✗ para los booleanos canónicos del ruleset.
  if (value === 'true') return '✓';
  if (value === 'false') return '✗';
  return value;
}

function _safeMap<T, U>(arr: ReadonlyArray<T> | null | undefined, fn: (item: T, idx: number) => U): U[] {
  // El cliente de streaming puede entregar listas como `null` o `undefined`
  // (p. ej. `missing_information: null` en vez de `[]`). `.map()` sobre un
  // valor no iterable lanza el V8 "object is not iterable". Este helper
  // blinda el render contra esos casos sin tocar el contrato del schema.
  if (!Array.isArray(arr)) return [];
  return arr.map(fn);
}

function _safeJoinInputs(inputs: unknown): string {
  // La API puede devolver `inputs` como tupla `["k", "v"]` (lo que
  // produce el backend hoy) o como objeto `{key, value}` (lo que
  // produce el generador de tipos en algunos casos). Destructurar
  // `[k, v] = obj` sobre un objeto lanza "object is not iterable", así
  // que aquí aceptamos ambas formas.
  return _safeMap(inputs as ReadonlyArray<unknown>, (item) => {
    if (Array.isArray(item)) {
      const arr = item as readonly unknown[];
      const k = String(arr[0] ?? '');
      const v = String(arr[1] ?? '');
      return `${k}=${_formatValue(v)}`;
    }
    const obj = item as Record<string, unknown>;
    const k = String(obj.key ?? obj.name ?? '');
    const v = String(obj.value ?? '');
    return `${k}=${_formatValue(v)}`;
  }).join(' · ');
}

export function ClaimAnalysisPanel({ analysis }: { analysis: ClaimAnalysis }) {
  const matchedRules = analysis.rules_evaluated?.filter((r) => r.result === 'matched') ?? [];
  const otherRules = analysis.rules_evaluated?.filter((r) => r.result !== 'matched') ?? [];
  const facts = analysis.facts ?? [];
  const conditions = analysis.conditions ?? [];

  return (
    <div className="flex flex-col gap-3" data-component="claim-analysis-panel">
      <div className="flex flex-wrap items-center gap-2">
        <span className={_badgeClass(APPLICABILITY_TONE[analysis.applicability])}>
          {APPLICABILITY_LABEL[analysis.applicability]}
        </span>
        {analysis.convention && (
          <span className="inline-flex items-center gap-1 rounded-full border bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium leading-none text-blue-700 dark:text-blue-300 border-blue-500/30">
            {analysis.convention}
          </span>
        )}
        <span className={_badgeClass(DECISION_TONE[analysis.decision])}>
          {DECISION_LABEL[analysis.decision]}
        </span>
        {analysis.party_ids && analysis.party_ids.length > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full border bg-muted px-2 py-0.5 text-[10px] font-medium leading-none text-muted-foreground border-border">
            {analysis.party_ids.join(' · ')}
          </span>
        )}
      </div>

      {conditions.length > 0 && (
        <div className="rounded-md border bg-amber-500/5 p-2 text-xs">
          <p className="mb-1 font-medium text-amber-700 dark:text-amber-300">Condiciones</p>
          <ul className="list-disc space-y-0.5 pl-4 text-amber-700/90 dark:text-amber-300/90">
            {conditions.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {matchedRules.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Reglas disparadas
          </p>
          {_safeMap(matchedRules, (r) => {
            const meta = RULE_STATUS_META[r.result];
            const Icon = meta.icon;
            return (
              <div
                key={r.rule_id}
                className={cn('rounded-md border p-2 text-xs', meta.tone)}
              >
                <div className="flex items-start gap-2">
                  <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <div className="flex-1 space-y-0.5">
                    <p className="font-medium">
                      {r.rule_id}
                      <span className="ml-1 text-[10px] opacity-70">· {meta.label}</span>
                    </p>
                    <p className="text-[11px] opacity-90">{r.rationale}</p>
                    <p className="text-[10px] opacity-70">
                      {_safeJoinInputs(r.inputs)}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {otherRules.length > 0 && (
        <details className="rounded-md border bg-muted/30">
          <summary className="cursor-pointer p-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground">
            Reglas no disparadas ({otherRules.length})
          </summary>
          <ul className="space-y-0.5 p-2 pt-0 text-[11px] text-muted-foreground">
            {_safeMap(otherRules, (r) => {
              const meta = RULE_STATUS_META[r.result];
              return (
                <li key={r.rule_id} className="flex items-center gap-1.5">
                  <span className={cn('rounded-full border px-1.5 py-0 text-[9px]', meta.tone)}>
                    {meta.label}
                  </span>
                  <code className="font-mono text-[10px]">{r.rule_id}</code>
                </li>
              );
            })}
          </ul>
        </details>
      )}

      {facts.length > 0 && (
        <details className="rounded-md border bg-muted/30">
          <summary className="cursor-pointer p-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground">
            Hechos extraídos ({facts.length})
          </summary>
          <ul className="space-y-0.5 p-2 pt-0 text-[11px]">
            {_safeMap(facts, (f, i) => (
              <li key={i} className="flex items-baseline gap-2">
                <code className="font-mono text-[10px] text-muted-foreground">
                  {f.name}
                </code>
                <span className="text-foreground">{_formatValue(f.value)}</span>
                {f.asserted_by && (
                  <span className="text-[9px] text-muted-foreground">
                    ({f.asserted_by})
                  </span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}

      {(_safeMap(analysis.missing_information, (m) => m)).length > 0 && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-xs">
          <p className="mb-1 flex items-center gap-1 font-medium text-amber-700 dark:text-amber-300">
            <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
            Datos que faltan
          </p>
          <ul className="list-disc space-y-0.5 pl-4 text-amber-700/90 dark:text-amber-300/90">
            {_safeMap(analysis.missing_information, (m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {matchedRules.length === 0 && otherRules.length === 0 && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <FileText className="h-3.5 w-3.5" aria-hidden="true" />
          El ruleset no disparó ninguna regla específica para este caso.
        </p>
      )}
    </div>
  );
}
