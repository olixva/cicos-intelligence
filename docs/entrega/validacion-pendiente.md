# Validación pendiente antes de entregar

Lista de lo que hay que ejecutar con credenciales y servicios reales, y de dónde
va cada resultado en la [memoria](memoria.md). Las pruebas locales se ejecutan
en cada cambio; las comprobaciones contra proveedores y servicios reales siguen
pendientes.

## 0. Modelos seleccionados y acceso real

Los defaults propuestos son `gpt-6.1-sol` para respuesta y extracción y
`gpt-6-luna` para el router OpenAI. Estos IDs figuran en el
[catálogo oficial](https://developers.openai.com/api/docs/models), pero la
cuenta del proyecto todavía debe probarlos con la Responses API y salida
estructurada. La extracción se mantiene en Sol hasta cerrar la comparación del
paso 4.

Con la clave sólo en el entorno:

```bash
export OPENAI_API_KEY=...        # sin commitear
curl -s https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY" \
  | python3 -c "import sys,json; print('\n'.join(sorted(m['id'] for m in json.load(sys.stdin)['data'])))"
```

Comprobar acceso y enviar una petición sintética de cada etapa. Si se cambian
los identificadores, actualizar **todos** estos sitios:

| Fichero | Qué |
|---|---|
| `.env.example` | `OPENAI_ANSWER_MODEL`, `OPENAI_CLAIM_EXTRACTION_MODEL`, `ALLIANZ_ROUTER_MODEL` |
| `backend/src/bootstrap.py` | configuración centralizada de los tres defaults |
| `backend/src/infrastructure/adapters/outbound/query_workflow/langgraph_workflow.py` | valor por defecto del router |
| `backend/src/application/services/routing.py`, `claim_heuristics.py` | comentarios que citan el router |
| `docs/operacion.md`, `docs/evaluacion.md` | reparto de modelos y corrida de referencia |
| `docs/entrega/memoria.md` §2.1 y §3.4 | tabla de modelos y modelo de la corrida |

Buscar referencias antiguas con `rg -n 'gpt-5\.[0-9]'`; las que describen
corridas históricas deben seguir etiquetadas como históricas. El modelo de
embeddings (`text-embedding-3-small`, 1536 dimensiones) va en
`backend/configs/*.yaml`; cambiarlo cambia la firma del índice y obliga a
reindexar.

**Estado de esta ejecución:** el smoke de Responses API y la comparación
Sol/Luna no se han podido ejecutar porque no hay clave configurada ni un backend
local disponible. No hay manifiestos ni resultados A/B; el default de extracción
se mantiene en `gpt-6.1-sol`. Repetir esta puerta cuando estén listos la clave,
Qdrant, Langfuse, el índice y el backend.

## 1. Entorno

```bash
cp .env.example .env     # rellenar OPENAI_API_KEY, LANGFUSE_* y los modelos del paso 0
make local-services-up   # Qdrant + Langfuse (crear proyecto y claves en :3000)
make index-baseline      # indexa el perfil baseline
make serve-backend       # API en :8000 (aprovisiona los prompts en Langfuse)
make serve-frontend      # opcional, :5173
```

Comprobar: `curl -s localhost:8000/health/ready` devuelve `ready`.

## 2. Puertas de calidad completas

```bash
make check-all
```

Con Qdrant levantado deben pasar también los 14 tests de `backend/tests/integration/`.
Resultado esperado: todo en verde salvo, posiblemente,
`test_cli.py::test_compare_parsers_writes_a_report_with_timings`, que **falla
también en un checkout limpio** si no está preparado el bundle de modelos de
Docling (`allianz prepare-ingestion-models`, ver `docs/ingesta-y-recuperacion.md`, o `ALLIANZ_DOCLING_ARTIFACTS`). Si falla,
resolverlo o dejarlo documentado.

## 3. Re-medir la evaluación del RAG → memoria §3.4

```bash
cd backend
uv run --no-sync python scripts/run_baseline.py --limit 5 --output /tmp/baseline-smoke   # humo
uv run --no-sync python scripts/run_baseline.py \
  --output ../data/evaluation/results/$(date +%F)-baseline --label baseline --concurrency 4
```

Sustituir la tabla de la memoria §3.4 por `metrics.json` de la nueva corrida y
actualizar fecha, commit y modelos. **Comparar con la corrida anterior**
(`convention_accuracy` 0,12; `claim_decision_accuracy` 0,31 antes de corregir el
ruleset): si siguen bajas, la explicación de la memoria («la causa fue el
ruleset») no se sostiene y hay que cambiarla. Comprobar
`over_resolution_rate_against_reference` junto a `n_total`, `n_scored`,
`n_missing` y `n_error`; no tratar errores como casos resueltos correctamente.

`data/evaluation/results/` está ignorado por git: conservar los resultados fuera
del repositorio o decidir qué se adjunta a la entrega.

## 4. Campaña de red-teaming → memoria §7.1

```bash
cd backend
uv run --no-sync python scripts/run_redteam.py --output ../data/evaluation/results/redteam-$(date +%F)
```

Sale con código 1 si algún ataque tiene éxito. Registrar en la memoria la tasa de
éxito del atacante, el desglose por categoría y el sobre-rechazo. Revisar a mano
`per-case/*.json` de cualquier fallo y de **una muestra de los que pasan**: los
criterios son de cadena y de estado, y un «pass» no prueba que la respuesta sea
buena. Si un ataque tiene éxito: o se corrige la defensa y se repite, o se
documenta como hallazgo abierto; no se edita el caso para que pase.

## 5. Jev, el modelo de decisiones → memoria §2.1.1

Jev está integrado como **opción apagada por defecto** y nunca se ha ejecutado
contra el servicio real. El contrato se tomó del OpenAPI del SDK oficial
(`POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer`,
`{model, state, questions}` → `{model, answers, usage}`).

**Red.** Desde un equipo con proxy corporativo, `api.typesafe.ai` queda bloqueado
(Zscaler devuelve 403). Ejecutar desde la VM propia, no desde la red de Allianz.

**Datos.** TypeSafe no publica (que yo haya podido leer) su política de retención.
Antes de enviarle nada, confirmarla; con el golden y las suites sintéticas no hay
datos personales, pero con relatos reales sí.

```bash
export TYPESAFE_API_KEY=...      # clave de https://console.typesafe.ai (acceso anticipado)
```

1. **Humo del cliente.** Un `decide` real con una pregunta `noul` y otra `choice`;
   comprobar que la respuesta cumple el contrato (si no, el único fichero a
   ajustar es `decision_model/jev_client.py`) y fijar el modelo concreto en
   `TYPESAFE_DEFAULT_MODEL` si se prefiere una versión a `jev-latest`.
2. **Router, A/B con el golden.** Levantar el backend dos veces y ejecutar el
   modo automático con cada uno:
   ```bash
   ALLIANZ_ROUTER_BACKEND=openai make serve-backend   # y en otra terminal:
   cd backend && uv run --no-sync python scripts/run_baseline.py --modes auto \
     --output ../data/evaluation/results/router-openai --label router-openai
   # repetir con ALLIANZ_ROUTER_BACKEND=jev -> router-jev
   ```
   Comparar `router_match` y la matriz de confusión, y la latencia por caso
   (`per-case/*.json`). Barrer `ALLIANZ_JEV_ROUTER_MIN_CONFIDENCE` (0,4 / 0,6 / 0,8)
   con la corrida de Jev. **Si Jev iguala o supera a OpenAI, eliminar el router de
   OpenAI sin dejar rastro** (adaptador, prompt `auto-router`, variables, tests y
   documentación). Si no, dejar Jev como opción documentada o retirarlo.
3. **Guardarraíl, con la suite de red-teaming.** Ejecutar el paso 4 con
   `ALLIANZ_INPUT_GUARD=off` y con `jev`; comparar tasa de éxito del atacante y
   sobre-rechazo de los controles. Ajustar `ALLIANZ_JEV_GUARD_INJECTION` y
   `ALLIANZ_JEV_GUARD_OFF_TOPIC`. Con el guarda activo, un ataque bloqueado
   responde `kind=clarification` con `metadata.guardrail_source=decision_model`.
4. **Juez, con calibración.** `run_baseline.py --modes question --judge jev`.
   Etiquetar a mano ~30 pares (pregunta, página) y ~30 (bloque, páginas citadas)
   y medir el acuerdo con las probabilidades de Jev. **No citar las cifras en la
   memoria sin ese acuerdo.**
5. Anotar en la memoria §2.1.1 los resultados y quitar la etiqueta «sin medir».

## 6. Trazabilidad (comprobación manual) → memoria §5.1

- Lanzar una consulta y abrir el `langfuse_url` de la respuesta: debe verse la
  traza con spans por nodo y la generación con tokens y coste.
- Si el coste no aparece, configurar los precios del modelo elegido en Langfuse
  (Settings → Models); la propuesta de alertas de coste (§5.2) depende de ello.

## 7. Contenedores (comprobación manual) → `docs/operacion.md`

```bash
docker build -t allianz-backend -f backend/Dockerfile .
docker run --rm -p 8000:8000 --env-file .env \
  -e QDRANT_URL=http://host.docker.internal:6333 -e ALLIANZ_QDRANT_URL=http://host.docker.internal:6333 \
  -e LANGFUSE_BASE_URL=http://host.docker.internal:3000 \
  -v "$PWD/data:/app/backend/data" allianz-backend
curl -s localhost:8000/health/ready
```

El Dockerfile se corrigió leyendo el código (`--factory`, `configs/`), sin
construir la imagen. Si no arranca, es el primer sitio donde mirar.

## 8. Antes de entregar

- [ ] Sin marcadores `_[insertar aquí]_` ni `_[pendiente…]_` en `memoria.md`
      (`grep -n "insertar\|pendiente" docs/entrega/memoria.md`).
- [ ] Revisar la memoria §8 (proceso con copilotos/SDD): es el relato de cómo se
      trabajó y solo la persona autora puede confirmarlo.
- [ ] Cifras de tests y de commits de la memoria coherentes con la última
      ejecución.
- [ ] Ningún secreto en el árbol: `git grep -n "sk-"` (solo debe salir el marcador `sk-lf-replace-with-local-value` de `ops/local.env.example`) y `.env` sin commitear.
- [ ] Exportar la memoria a PDF/Word si la entrega lo pide.
