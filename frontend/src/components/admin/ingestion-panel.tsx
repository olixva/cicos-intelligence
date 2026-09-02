import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { IngestionExtraction, IngestionSnapshot, IngestionStage } from '@/api/ingestion';

export interface IngestionPanelProps {
  snapshot: IngestionSnapshot;
  extractions: IngestionExtraction[];
  totalExtractions: number;
  offset: number;
  pageSize: number;
  onPageChange: (offset: number) => void;
  onStart: () => void;
}

const stages: Array<{ key: IngestionStage; label: string }> = [
  { key: 'verifying_manual', label: 'Verificando manual' },
  { key: 'extracting_evidence', label: 'Extrayendo evidencia' },
  { key: 'publishing_index', label: 'Publicando índice' },
  { key: 'published_index', label: 'Índice publicado' },
];

export function IngestionPanel({ snapshot, extractions, totalExtractions, offset, pageSize, onPageChange, onStart }: IngestionPanelProps) {
  const job = snapshot.active_job ?? snapshot.last_job;
  const running = snapshot.active_job?.status === 'running';
  const succeeded = job?.status === 'succeeded';
  return (
    <section className="mx-auto flex h-full w-full max-w-4xl flex-col gap-5 overflow-y-auto p-5 sm:p-8" aria-label="Modo administrador">
      <div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Modo administrador</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight">Ingesta del manual</h2>
          <p className="mt-1 text-sm text-muted-foreground">Manual CIDE/ASCIDE/CICOS · edición de noviembre de 2004</p>
        </div>
      </div>

      <div className="flex items-center justify-between rounded-lg border bg-card px-4 py-3 text-sm">
        <span className="font-medium">Estado del índice</span>
        <span className={succeeded ? 'text-emerald-700' : running ? 'text-blue-700' : 'text-muted-foreground'}>
          {running ? '● En curso' : succeeded ? '● Índice disponible' : 'Sin ingesta registrada'}
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-lg border bg-card p-5">
          <h3 className="text-sm font-semibold">Última publicación</h3>
          <p className="mt-1 text-xs text-muted-foreground">Los datos se muestran sólo cuando los confirma el backend.</p>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <Metric label="Páginas" value={job?.pages} />
            <Metric label="Fragmentos" value={job?.chunks} />
            <Metric label="Parser" value={job?.parser?.replace(/^pypdf-/, 'pypdf ') ?? '—'} />
          </div>
          <div className="mt-4 divide-y border-t">
            {stages.map((stage) => <StageRow key={stage.key} stage={stage} job={job} />)}
          </div>
        </div>
        <div className="rounded-lg border bg-card p-5">
          <h3 className="text-sm font-semibold">Acciones</h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">Sólo se procesa el manual verificado de esta prueba. No se admiten otros documentos.</p>
          <Button type="button" className="mt-4 w-full" onClick={onStart} disabled={running}>Reingestar manual</Button>
          {job?.error && <p role="alert" className="mt-3 flex gap-2 text-xs text-destructive"><XCircle className="h-4 w-4 shrink-0" />{job.error}</p>}
          {job?.document_hash && <p className="mt-4 break-all text-[10px] text-muted-foreground">SHA-256: {job.document_hash}</p>}
        </div>
      </div>
      <details className="rounded-lg border bg-card p-5" open>
        <summary className="cursor-pointer text-sm font-semibold">Extracciones disponibles ({totalExtractions})</summary>
        <p className="mt-1 text-xs text-muted-foreground">Páginas y previsualización producidas por el parser.</p>
        {extractions.length === 0 ? <p className="mt-3 text-xs text-muted-foreground">No hay páginas publicadas.</p> : <>
          <ul className="mt-3 divide-y border-t">{extractions.map((item) => <li key={item.evidence_id} className="flex gap-3 py-3 text-xs"><span className="w-12 shrink-0 font-semibold">p. {item.pdf_page}</span><span className="min-w-0 flex-1 truncate text-muted-foreground">{item.text_preview}</span>{item.regions_available && <span className="text-emerald-700">región</span>}</li>)}</ul>
          <div className="mt-4 flex items-center justify-between gap-3 text-xs text-muted-foreground">
            <span>Mostrando {offset + 1}–{Math.min(offset + extractions.length, totalExtractions)} de {totalExtractions}</span>
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => onPageChange(Math.max(0, offset - pageSize))} disabled={offset === 0}>Anterior</Button>
              <Button type="button" variant="outline" size="sm" onClick={() => onPageChange(offset + pageSize)} disabled={offset + pageSize >= totalExtractions}>Siguiente</Button>
            </div>
          </div>
        </>}
      </details>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number | null | undefined }) {
  return <div className="rounded-md bg-muted/50 p-2"><span className="block text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span><strong className="mt-1 block text-sm">{value ?? '—'}</strong></div>;
}

function StageRow({ stage, job }: { stage: { key: IngestionStage; label: string }; job: IngestionSnapshot['last_job'] }) {
  const current = job?.stage === stage.key;
  const complete = job?.status === 'succeeded' || (current && job.status === 'running' && stage.key === 'verifying_manual');
  const running = job?.status === 'running' && current;
  const Icon = job?.status === 'failed' && current ? XCircle : complete ? CheckCircle2 : current ? Loader2 : Circle;
  return <div className="flex items-center gap-2 py-2 text-xs"><Icon className={`h-4 w-4 ${job?.status === 'failed' && current ? 'text-destructive' : running ? 'animate-spin text-primary' : complete ? 'text-emerald-600' : current ? 'text-primary' : 'text-muted-foreground'}`} /><span>{stage.label}</span></div>;
}
