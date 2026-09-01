import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { EvidenceChip } from '@/components/evidence-chip';
import type { EvidenceItem, EnvelopeResponse } from '@/api/queries';

/**
 * EnvelopeRenderer — switch literal sobre `result.kind`.
 *
 * Decisión D3: NUNCA ramificar por `resolved_mode`. Solo `result.kind`.
 *   - 'question'      → bloques de respuesta con chips de evidencia
 *   - 'claim'         → aplicabilidad + facts + condiciones
 *   - 'clarification' → mensaje del router pidiendo más contexto
 *
 * El `default` usa `satisfies never` para que añadir un `kind` nuevo al
 * union del backend rompa el type-check aquí. Esto está cubierto por el
 * test `envelope-renderer.test.tsx`.
 */

interface QuestionViewProps {
  result: Extract<EnvelopeResponse['result'], { kind: 'question' }>;
  evidence: EvidenceItem[];
}

function QuestionView({ result, evidence }: QuestionViewProps) {
  const evidenceById = new Map(evidence.map((e) => [e.evidence_id, e]));
  const statusLabel: Record<string, string> = {
    answered: 'Respondida',
    partial: 'Parcial',
    insufficient_evidence: 'Sin evidencia suficiente',
    out_of_scope: 'Fuera de alcance',
  };

  // El schema OpenAPI define `blocks` como `additionalProperties: true`, por
  // lo que openapi-typescript los tipa como `unknown`. Para este MVP los
  // consumimos como `{ text: string; evidence_ids?: string[] }`.
  interface RawBlock {
    text?: string;
    evidence_ids?: string[];
  }
  const blocks: RawBlock[] = Array.isArray(result.blocks)
    ? (result.blocks as RawBlock[])
    : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Respuesta</CardTitle>
        <CardDescription>
          Estado: <span className="font-medium">{statusLabel[result.status] ?? result.status}</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {blocks.length > 0 ? (
          blocks.map((block, idx) => (
            <article key={idx} className="flex flex-col gap-2 text-pretty">
              {block.text && <p className="text-sm leading-relaxed">{block.text}</p>}
              {Array.isArray(block.evidence_ids) && block.evidence_ids.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {block.evidence_ids.map((eid) => {
                    const ev = evidenceById.get(eid);
                    return ev ? (
                      <EvidenceChip key={eid} item={ev} snippet={block.text ?? ''} />
                    ) : (
                      <span
                        key={eid}
                        className="rounded-full border border-dashed px-2 py-0.5 text-xs text-muted-foreground"
                        title="Evidencia no devuelta por el backend"
                      >
                        {eid}
                      </span>
                    );
                  })}
                </div>
              )}
            </article>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">Sin bloques de respuesta.</p>
        )}
        {result.trace_id && (
          <p className="text-xs text-muted-foreground">trace_id: {result.trace_id}</p>
        )}
      </CardContent>
    </Card>
  );
}

interface ClaimViewProps {
  result: Extract<EnvelopeResponse['result'], { kind: 'claim' }>;
}

const APPLICABILITY_LABEL: Record<string, string> = {
  applicable: 'Aplicable',
  not_applicable: 'No aplicable',
  undetermined: 'Indeterminado',
};

const DECISION_LABEL: Record<string, string> = {
  resolved: 'Resuelto',
  conditional: 'Condicional',
  undetermined: 'Indeterminado',
  not_assessed: 'No evaluado',
};

function ClaimView({ result }: ClaimViewProps) {
  // El schema `ClaimResult` es un subset intencional: solo expone
  // applicability, convention, decision y trace_id. Los attributed_facts,
  // conditions y contradictions llegan en el `ClaimAnalysisResponse` (no en
  // el envelope síncrono). En este MVP mostramos el resumen; cuando el
  // backend los emita en el envelope, los añadiremos aquí.
  return (
    <Card>
      <CardHeader>
        <CardTitle>Análisis de siniestro</CardTitle>
        <CardDescription>
          {result.convention ? `Convenio: ${result.convention} · ` : ''}
          <span>{APPLICABILITY_LABEL[result.applicability] ?? result.applicability}</span> ·{' '}
          <span>{DECISION_LABEL[result.decision] ?? result.decision}</span>
        </CardDescription>
      </CardHeader>
      {result.trace_id && (
        <CardContent>
          <p className="text-xs text-muted-foreground">trace_id: {result.trace_id}</p>
        </CardContent>
      )}
    </Card>
  );
}

interface ClarificationViewProps {
  result: Extract<EnvelopeResponse['result'], { kind: 'clarification' }>;
}

function ClarificationView({ result }: ClarificationViewProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Necesitamos más contexto</CardTitle>
        <CardDescription>{result.message}</CardDescription>
      </CardHeader>
      {result.missing_fields && result.missing_fields.length > 0 && (
        <CardContent>
          <p className="text-sm text-muted-foreground">Campos que faltan:</p>
          <ul className="mt-2 list-disc pl-5 text-sm">
            {result.missing_fields.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </CardContent>
      )}
    </Card>
  );
}

function LoadingView() {
  return (
    <Card aria-busy="true">
      <CardHeader>
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-4 w-48" />
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-11/12" />
        <Skeleton className="h-4 w-10/12" />
      </CardContent>
    </Card>
  );
}

export interface EnvelopeRendererProps {
  loading?: boolean;
  response?: EnvelopeResponse | null;
  error?: Error | null;
}

export function EnvelopeRenderer({ loading, response, error }: EnvelopeRendererProps) {
  if (loading) return <LoadingView />;
  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Error</CardTitle>
          <CardDescription>{error.message}</CardDescription>
        </CardHeader>
      </Card>
    );
  }
  if (!response) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Sin resultados</CardTitle>
          <CardDescription>
            Envía una consulta para ver la respuesta del backend.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const evidence = response.evidence ?? [];
  const result = response.result;

  // Decisión D3: switch literal sobre result.kind. Si el backend añade un
  // kind nuevo, el `satisfies never` del default rompe type-check aquí.
  switch (result.kind) {
    case 'question':
      return <QuestionView result={result} evidence={evidence} />;
    case 'claim':
      return <ClaimView result={result} />;
    case 'clarification':
      return <ClarificationView result={result} />;
    default: {
      const exhaustive: never = result;
      void exhaustive;
      return (
        <Card>
          <CardHeader>
            <CardTitle>Tipo de resultado desconocido</CardTitle>
            <CardDescription>
              El backend devolvió un `result.kind` no soportado por la UI.
              {process.env.NODE_ENV !== 'production' && (
                <code className="mt-2 block text-xs">{JSON.stringify(result)}</code>
              )}
            </CardDescription>
          </CardHeader>
        </Card>
      );
    }
  }
}
