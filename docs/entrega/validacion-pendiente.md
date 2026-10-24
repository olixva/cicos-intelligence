# Validación antes de entregar

Este documento separa lo que ya se comprobó en el checkout local de las
validaciones que todavía requieren una decisión humana. Las campañas usan el
golden sintético y no enviaron relatos reales con datos personales.

## Configuración y pruebas completadas

Los defaults son `gpt-6.1-sol` para respuesta y extracción; router Jev
(`jev-latest`, umbral 0,4) y guardarraíl Jev (umbrales 0,9/0,95). Para las
pruebas OpenAI, el `.env` local selecciona `gpt-6-luna` en todas las llamadas;
no se probó Sol. OpenAI permanece disponible para el router con
`ALLIANZ_ROUTER_BACKEND=openai`, y el guard se puede desactivar mediante
`ALLIANZ_INPUT_GUARD=off`.

**Suite de código (24-10-2026):** `make check-all` terminó con 600 tests de
backend aprobados, 1 omitido y 2 avisos; 99 tests de frontend aprobados. Lint,
tipado, build y contrato OpenAPI pasaron. `make test-e2e` pasó 2/2. El bundle
del frontend supera el umbral informativo de 500 KB. Los avisos del backend
son los que registra pytest en esa ejecución.

**Baseline (24-10-2026):** 110 casos × `question`, `claim` y `auto`, 330/330
resultados completos y cero errores técnicos. Respuesta y extracción usaron
`gpt-6-luna`, router y guard Jev. El manifiesto registra commit base
`99ff2f48`, fingerprint `3c074a5069b273f0…`, hash del manual y firma del alias
`allianz-manual-active` (118 puntos). Resultados y métricas detalladas están en
`data/evaluation/results/2026-10-24-final-jev-luna-all-modes-normalized/`.

El modo `claim` pidió aclaraciones en 103/110 casos; la decisión se puntuó sólo
en seis. `claim_decision_accuracy` fue 0,500, la validez de citas 0,036 y la
cobertura de evidencia 0,015. **Estos datos no acreditan una resolución fiable
de siniestros.** Hay que adjudicar la política de ámbito, comprobar los hechos
que exige cada caso y alinear el golden o mejorar la extracción sin asumir como
ciertos los datos desconocidos. Véanse los resultados completos en
[`evaluacion.md`](../evaluacion.md) y la lectura de la memoria §3.4.

**A/B del router (24-10-2026):** en el mismo golden e índice, Jev acertó 97/110
(88,2 %) y OpenAI Luna 96/110 (87,3 %); ambas corridas terminaron sin errores.
Jev queda como default. La referencia OpenAI está en
`data/evaluation/results/2026-10-24-router-openai-luna-e2e-current/`.

**Red-team (24-10-2026, 27 ataques y 3 controles):**

| Router | Guard | Ataques exitosos | Controles benignos rechazados |
|---|---|---:|---:|
| Jev | off | 1/27 | 0/3 |
| Jev | Jev | 0/27 | 0/3 |
| OpenAI Luna | Jev | 0/27 | 0/3 |

Artefactos locales ignorados por Git: `2026-10-24-redteam-jev-router-guard-off-current/`,
`2026-10-24-redteam-jev-router-jev-guard-current/` y
`2026-10-24-redteam-openai-router-jev-guard-current/` bajo
`data/evaluation/results/`. Los manifiestos contienen fingerprint y firma del
índice. La campaña apagando el guard sirve como control; el default Jev bloqueó
el ataque que pasó con `off`, sin rechazar los tres controles.

Las corridas del 22-10 son históricas y no sirven como gate actual: no registran
fingerprint del código ni firma del índice activo. La campaña actual se ejecutó
con fingerprint `3c074a50…`; después sólo se ajustó la compatibilidad del
endpoint local de Langfuse en Docker. El servidor actual informa fingerprint
`b7896fb27b94e334…` en `/health/config`.

## Docker

La imagen backend `allianz-backend:tfm-check` se construyó el 24-10-2026. Se
verificaron `/health/ready`, la configuración Jev/Luna y una petición sintética
por cada modo (`question`, `claim`, `auto`); las tres devolvieron HTTP 200. El
contenedor necesita ambas monturas de datos y las variables de la pila local:

```bash
docker build -t allianz-backend -f backend/Dockerfile .
docker run --rm -p 8000:8000 --env-file .env --env-file ops/local.env \
  -e QDRANT_URL=http://host.docker.internal:6333 \
  -e ALLIANZ_QDRANT_URL=http://host.docker.internal:6333 \
  -e LANGFUSE_BASE_URL=http://host.docker.internal:3000 \
  -v "$PWD/data:/app/data:ro" \
  -v "$PWD/data:/app/backend/data:ro" allianz-backend
```

El contenedor usa `/tmp/uv-cache` para su caché de uv. `host.docker.internal`
se admite como dirección local de Docker para Langfuse; las URLs remotas se
rechazan.

## Pendiente de decisión o comprobación humana

- Revisar la memoria §8: sólo la persona autora puede confirmar el relato de su
  proceso de trabajo.
- Pedir a una persona experta del dominio que adjudique la política de ámbito y
  una muestra del golden; cerrar la brecha de 103 aclaraciones antes de afirmar
  que el producto resuelve siniestros de forma fiable.
- Confirmar la política de retención de TypeSafe antes de enviarle relatos
  reales con datos personales. No se encontró una política pública verificable.
- Abrir una traza de Langfuse y confirmar que muestra los spans, tokens y coste;
  cargar los precios del modelo si se necesitan cifras monetarias.
- Exportar la memoria a PDF o Word si lo exige la entrega.
- Los resultados de evaluación están en una ruta ignorada por Git. Copiarlos a
  un anexo de entrega o conservarlos fuera del repositorio según el formato que
  pida la universidad.
