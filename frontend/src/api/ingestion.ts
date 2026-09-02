import { env } from '@/env';

export type IngestionStage =
  | 'verifying_manual'
  | 'extracting_evidence'
  | 'publishing_index'
  | 'published_index';
export type IngestionStatus = 'running' | 'succeeded' | 'failed';

export interface IngestionEvent {
  event_id: string;
  job_id: string;
  timestamp: string;
  stage: IngestionStage;
  status: IngestionStatus;
  data: Record<string, string | number | null>;
}

export interface IngestionJob {
  job_id: string;
  status: IngestionStatus;
  stage: IngestionStage;
  started_at: string;
  finished_at: string | null;
  document_hash: string | null;
  parser: string | null;
  pages: number | null;
  chunks: number | null;
  collection: string | null;
  error: string | null;
  events: IngestionEvent[];
}

export interface IngestionSnapshot {
  active_job: IngestionJob | null;
  last_job: IngestionJob | null;
}

export interface IngestionExtraction {
  evidence_id: string;
  document_hash: string;
  pdf_page: number;
  printed_label: string | null;
  text_preview: string;
  regions_available: boolean;
  pdf_url: string;
}

const endpoint = `${env.VITE_API_BASE_URL}/api/v1/admin/ingestion`;

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) throw new Error(`La API respondió ${response.status}`);
  return (await response.json()) as T;
}

export function getIngestionSnapshot(): Promise<IngestionSnapshot> {
  return request<IngestionSnapshot>(endpoint);
}

export function startIngestion(): Promise<IngestionJob> {
  return request<IngestionJob>(endpoint, { method: 'POST' });
}

export function getIngestionExtractions(offset = 0, limit = 20): Promise<{ total: number; items: IngestionExtraction[] }> {
  return request<{ total: number; items: IngestionExtraction[] }>(`${endpoint}/extractions?offset=${offset}&limit=${limit}`);
}

export function subscribeToIngestion(
  onEvent: (event: IngestionEvent) => void,
  onError: () => void,
): () => void {
  const source = new EventSource(`${endpoint}/events`);
  source.addEventListener('ingestion', (message) => {
    try {
      onEvent(JSON.parse((message as MessageEvent<string>).data) as IngestionEvent);
    } catch {
      onError();
    }
  });
  source.onerror = onError;
  return () => source.close();
}
