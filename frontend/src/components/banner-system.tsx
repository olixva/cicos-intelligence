import { useState } from 'react';
import { Banner } from '@/components/ui/banner';
import { useHealthLive, useHealthReady } from '@/api/health';

/**
 * BannerSystem — expone banners derivados del estado del backend.
 *
 * Estados que cubre (en orden de severidad):
 *
 *   1. /health/live falla o responde 5xx → banner destructive
 *      (servicio caído, contactar ops).
 *   2. /health/ready falla con error de red → banner destructive
 *      (no se puede conectar al backend; puede ser backend caído o
 *      proxy de dev mal configurado).
 *   3. /health/ready responde 503 → banner warning con la razón.
 *      El proceso está vivo pero el índice no está listo.
 *   4. ambos OK → no muestra nada.
 *
 * Cada banner es dismissable; el estado dismissed vive en memoria de la
 * sesión (no se persiste) porque la próxima vez que `/health` se refresque
 * el banner reaparecerá si el problema persiste.
 */
export function BannerSystem() {
  const live = useHealthLive();
  const ready = useHealthReady();
  const [dismissedLive, setDismissedLive] = useState(false);
  const [dismissedNetwork, setDismissedNetwork] = useState(false);
  const [dismissedReady, setDismissedReady] = useState(false);

  // 1) Live caído o 5xx → contactar ops.
  if (live.isError && !dismissedLive) {
    return (
      <Banner variant="destructive" onDismiss={() => setDismissedLive(true)}>
        El servicio no responde. Si persiste, contacta con operaciones.
      </Banner>
    );
  }

  // 2) Error de red en /health/ready (CORS, proxy, backend no alcanzable).
  //    Distinguimos este caso del 503 de ready: aquí no hubo respuesta,
  //    solo falló la conexión. Severidad alta porque el frontend no puede
  //    hacer nada hasta que se restaure la conectividad.
  if (ready.isError && !ready.isLoading && !dismissedNetwork) {
    return (
      <Banner
        variant="destructive"
        onDismiss={() => setDismissedNetwork(true)}
      >
        No se puede conectar con el backend. Reintentaremos automáticamente.
      </Banner>
    );
  }

  // 3) Ready 503 → índice no publicado todavía.
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
