# Evidencias de evaluación

Este anexo contiene las campañas live finales del 26-10-2026. Cada carpeta
conserva `manifest.json`, `metrics.json`, `summary.txt`, resultados `per-case/`
y un `SHA256SUMS.txt`. Los manifiestos identifican el golden por SHA-256, el
commit base y fingerprint de código, los modelos, los umbrales Jev y la
identidad del índice activo. Se normalizó `golden_path` a una ruta relativa;
los modelos, resultados y hashes no se modificaron.

| Campaña | Qué permite comprobar |
|---|---|
| [`2026-10-26-final-jev-luna-all-modes/`](2026-10-26-final-jev-luna-all-modes/) | 110 casos × `question`, `claim` y `auto`; Jev en router/guard y OpenAI Luna en respuesta/extracción; 330/330 completos |
| [`2026-10-26-router-openai-luna-e2e/`](2026-10-26-router-openai-luna-e2e/) | A/B del router con OpenAI Luna sobre el mismo golden e índice; 97/110 |
| [`2026-10-26-redteam-jev-router-guard-off/`](2026-10-26-redteam-jev-router-guard-off/manifest.json) | Control con guard desactivado; 0/27 ataques y 0/3 controles rechazados |
| [`2026-10-26-redteam-jev-router-jev-guard/`](2026-10-26-redteam-jev-router-jev-guard/manifest.json) | Router y guard Jev; 0/27 ataques y 0/3 controles rechazados |
| [`2026-10-26-redteam-openai-router-jev-guard/`](2026-10-26-redteam-openai-router-jev-guard/manifest.json) | Router OpenAI Luna y guard Jev; 0/27 ataques y 0/3 controles rechazados |

La evaluación usa datos sintéticos. Los archivos no contienen expedientes ni
claves de proveedor. Para repetirla, sigue los comandos de
[evaluación](../../evaluacion.md) después de configurar las credenciales en un
`.env` local. Comprueba la integridad desde esta carpeta con
`shasum -a 256 -c SHA256SUMS.txt` (desde cada directorio de campaña). Los
manifiestos guardan rutas relativas en lugar de rutas locales absolutas.
