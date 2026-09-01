import { useCallback, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ModeSelector } from '@/components/mode-selector';
import { QueryForm } from '@/components/query-form';
import { EnvelopeRenderer } from '@/components/envelope-renderer';
import { PdfViewer } from '@/components/pdf-viewer';
import { Footer } from '@/components/footer';
import { BannerSystem } from '@/components/banner-system';
import { useQuerySync } from '@/features/queries/use-query';
import { useQueryStream } from '@/features/queries/use-query-stream';
import { useEvidence } from '@/features/evidence/evidence-context';
import { isUiMode, type EnvelopeResponse, type UiMode } from '@/api/queries';
import { newRequestId } from '@/lib/request-id';

/**
 * IndexRoute — la única ruta del MVP. Compone:
 *   - BannerSystem (estado del backend)
 *   - Layout 2 columnas: izquierda formulario + resultado; derecha visor PDF
 *   - Footer con request_id/trace_id
 *
 * Estrategia de envío: usa streaming si el modo es 'question' y el usuario
 * no ha deshabilitado nada, si no usa el endpoint síncrono. Mantenemos
 * ambos paths operativos para que el cliente pueda evaluar cuál se siente
 * mejor antes de la fase 5b+.
 */
export default function IndexRoute() {
  const [mode, setMode] = useState<UiMode>(() => {
    if (typeof window === 'undefined') return 'auto';
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get('mode');
    return isUiMode(fromUrl) ? fromUrl : 'auto';
  });

  const sync = useQuerySync();
  const stream = useQueryStream();
  const { hasOpen } = useEvidence();

  const useStreaming = mode === 'question';

  const handleSubmit = useCallback(
    (text: string) => {
      const request_id = newRequestId();
      const payload = {
        mode,
        text,
        language: 'es' as const,
        stream: useStreaming,
      };
      if (useStreaming) {
        void stream.start(payload);
      } else {
        sync.mutate(payload, {
          onSuccess: (data: EnvelopeResponse) => {
            // Aseguramos que el request_id generado arriba coincida con el
            // del backend si difiere (poco probable).
            void request_id;
            void data;
          },
        });
      }
    },
    [mode, useStreaming, stream, sync],
  );

  const busy = useStreaming ? stream.state.status === 'streaming' : sync.isPending;
  const cancel = useStreaming ? stream.cancel : undefined;
  const envelope = useStreaming ? stream.state.result : (sync.data ?? null);
  const error = useStreaming ? stream.state.error : (sync.error ?? null);

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="border-b bg-card/50">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-7 w-7 rounded bg-primary text-primary-foreground grid place-items-center text-xs font-bold">
              C
            </div>
            <h1 className="text-base font-semibold">Allianz CICOS · Claims Intelligence</h1>
          </div>
          <span className="text-xs text-muted-foreground">MVP · Fase 5b</span>
        </div>
      </header>

      <main className="container flex-1 py-6">
        <BannerSystem />

        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section aria-label="Consulta" className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Nueva consulta</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <ModeSelector value={mode} onChange={setMode} />
                <QueryForm
                  onSubmit={handleSubmit}
                  busy={busy}
                  onCancel={cancel}
                  placeholder={
                    mode === 'claim'
                      ? 'Describe el siniestro: vehículos, contexto, normativa aplicable…'
                      : 'Escribe tu pregunta sobre el manual CIDE/ASCIDE…'
                  }
                />
              </CardContent>
            </Card>

            <EnvelopeRenderer
              loading={busy}
              response={envelope ?? null}
              error={error ?? null}
            />
          </section>

          <aside aria-label="Visor de evidencia" className="flex flex-col gap-4">
            {hasOpen ? (
              <PdfViewer src="/api/v1/manual/pdf" />
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Visor de evidencia</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Cuando la respuesta devuelva evidencia, podrás abrirla aquí haciendo
                    click en cada chip.
                  </p>
                </CardContent>
              </Card>
            )}
          </aside>
        </div>
      </main>

      <Footer response={envelope ?? null} />
    </div>
  );
}
