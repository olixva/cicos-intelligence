/**
 * Persistencia con fallback URL state.
 *
 * Estrategia:
 * 1. Intenta localStorage (clave versionada, p.ej. `cicos.mode.v1`).
 * 2. Si localStorage falla (modo privado, cuota llena, sandbox restrictivo),
 *    cae a `?key=value` en la URL via history.replaceState.
 * 3. Si tampoco puede tocar la URL, devuelve null y el caller decide el
 *    default. Nunca lanza.
 *
 * El fallback a URL es útil para entornos donde localStorage está bloqueado
 * (algunos iframes embebidos, context.isolated Web Extensions) y para poder
 * compartir un estado vía link.
 */

const URL_PARAM = 'cicos_state';

type Stored = Record<string, string>;

function readFromLocalStorage(): Stored | null {
  try {
    const raw = window.localStorage.getItem(URL_PARAM);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Stored;
    }
    return null;
  } catch {
    return null;
  }
}

function writeToLocalStorage(value: Stored): boolean {
  try {
    window.localStorage.setItem(URL_PARAM, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

function readFromUrl(): Stored {
  const result: Stored = {};
  try {
    const url = new URL(window.location.href);
    for (const [key, value] of url.searchParams.entries()) {
      if (key.startsWith('cicos.')) {
        result[key] = value;
      }
    }
  } catch {
    /* ignore */
  }
  return result;
}

function writeToUrl(value: Stored): boolean {
  try {
    const url = new URL(window.location.href);
    // Limpiamos claves previas que empiecen por cicos. para no acumular
    for (const key of Array.from(url.searchParams.keys())) {
      if (key.startsWith('cicos.')) url.searchParams.delete(key);
    }
    for (const [k, v] of Object.entries(value)) {
      url.searchParams.set(k, v);
    }
    window.history.replaceState({}, '', url.toString());
    return true;
  } catch {
    return false;
  }
}

/** Lee una clave versionada, probando localStorage → URL → null. */
export function loadKey(key: string): string | null {
  if (typeof window === 'undefined') return null;
  const fromLs = readFromLocalStorage();
  if (fromLs && key in fromLs) return fromLs[key] ?? null;
  const fromUrl = readFromUrl();
  if (key in fromUrl) return fromUrl[key] ?? null;
  return null;
}

/** Persiste una clave, intentando localStorage → URL. Devuelve éxito. */
export function saveKey(key: string, value: string): boolean {
  if (typeof window === 'undefined') return false;
  const current: Stored = {
    ...readFromLocalStorage(),
    ...readFromUrl(),
    [key]: value,
  };
  // Priorizamos LS; si falla, caemos a URL.
  return writeToLocalStorage(current) || writeToUrl(current);
}

/** Elimina una clave de ambos almacenamientos. */
export function clearKey(key: string): void {
  if (typeof window === 'undefined') return;
  const fromLs = readFromLocalStorage();
  if (fromLs && key in fromLs) {
    delete fromLs[key];
    writeToLocalStorage(fromLs);
  }
  const fromUrl = readFromUrl();
  if (key in fromUrl) {
    delete fromUrl[key];
    writeToUrl(fromUrl);
  }
}
