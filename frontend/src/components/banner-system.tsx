import { useState } from 'react';
import { Banner } from '@/components/ui/banner';
import { useHealthLive, useHealthReady } from '@/api/health';

/**
 * BannerSystem — expone banners derivados del estado del backend.
 *
 *   - /health/live no responde   → banner destructive
 *   - /health/ready responde 503 → banner warning con la razón
 *   - ambos OK                   → no muestra nada
 *
 * Cada banner es dismissable; el estado dismissed vive en memoria de la
 * sesión (no se persiste) porque la próxima vez que `/health` se refresque
 * el banner reaparecerá si el problema persiste.
 */
export function BannerSystem() {
  const live = useHealthLive();
  const ready = useHealthReady();
  const [dismissedLive, setDismissedLive] = useState(false);
  const [dismissedReady, setDismissedReady] = useState(false);

  if (live.isError && !dismissedLive) {
    return (
      <Banner variant="destructive" onDismiss={() => setDismissedLive(true)}>
        El backend no responde. Reintentaremos en unos segundos.
      </Banner>
    );
  }

  if (ready.data && ready.data.status >= 500 && !dismissedReady) {
    return (
      <Banner variant="warning" onDismiss={() => setDismissedReady(true)}>
        El backend aún no está listo
        {ready.data.body?.reason ? `: ${ready.data.body.reason}` : '.'}
      </Banner>
    );
  }

  return null;
}
