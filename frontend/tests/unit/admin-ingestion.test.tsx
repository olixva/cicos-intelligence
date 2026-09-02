import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { IngestionPanel } from '@/components/admin/ingestion-panel';
import type { IngestionSnapshot } from '@/api/ingestion';

const snapshot: IngestionSnapshot = {
  active_job: null,
  last_job: {
    job_id: 'job-1',
    status: 'succeeded',
    stage: 'published_index',
    started_at: '2026-09-02T00:00:00Z',
    finished_at: '2026-09-02T00:01:00Z',
    document_hash: 'b'.repeat(64),
    parser: 'pypdf-6.16.2',
    pages: 111,
    chunks: 118,
    collection: 'allianz-test',
    error: null,
    events: [],
  },
};

describe('IngestionPanel', () => {
  it('shows the verified manual status without a return button in the panel', () => {
    render(<IngestionPanel snapshot={snapshot} extractions={[{ evidence_id: 'e1', document_hash: 'b'.repeat(64), pdf_page: 1, printed_label: '1', text_preview: 'Texto extraído visible', regions_available: false, pdf_url: '#' }]} totalExtractions={45} offset={0} pageSize={20} onPageChange={vi.fn()} onStart={vi.fn()} />);

    expect(screen.getByRole('heading', { name: 'Ingesta del manual' })).toBeInTheDocument();
    expect(screen.getByText(/Índice disponible/)).toBeInTheDocument();
    expect(screen.getByText('111')).toBeInTheDocument();
    expect(screen.getByText('Texto extraído visible')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Volver al chat/ })).not.toBeInTheDocument();
    const publishedIcon = screen.getByText('Índice publicado').parentElement?.querySelector('svg');
    expect(publishedIcon).not.toHaveClass('animate-spin');
    expect(screen.getByText('Mostrando 1–1 de 45')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeInTheDocument();
  });

  it('offers reingestion and displays backend stages', async () => {
    const onStart = vi.fn();
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    const active = {
      ...snapshot,
      active_job: { ...snapshot.last_job!, status: 'succeeded' as const, stage: 'extracting_evidence' as const },
    };
    render(<IngestionPanel snapshot={active} extractions={[{ evidence_id: 'e1', document_hash: 'b'.repeat(64), pdf_page: 1, printed_label: '1', text_preview: 'x', regions_available: false, pdf_url: '#' }]} totalExtractions={45} offset={0} pageSize={20} onPageChange={onPageChange} onStart={onStart} />);

    expect(screen.getByText('Extrayendo evidencia')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reingestar manual' }));
    expect(onStart).toHaveBeenCalledOnce();
    await user.click(screen.getByRole('button', { name: 'Siguiente' }));
    expect(onPageChange).toHaveBeenCalledWith(20);
  });
});
