# Validación pendiente antes de entregar

Lista de lo que hay que ejecutar con credenciales y servicios reales, y de dónde
va cada resultado en la [memoria](memoria.md). Nada de esto se ha ejecutado aún:
las cifras de la memoria marcadas como _[insertar aquí]_ salen de estos pasos.

## 0. Elegir los modelos (hacer primero)

Los identificadores actuales (`gpt-5.6-sol` / `terra` / `luna`) están en el
repositorio pero **no se han verificado contra la API** y pueden estar
superados. Con la clave en el entorno:

```bash
export OPENAI_API_KEY=...        # sin commitear
curl -s https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY" \
  | python3 -c "import sys,json; print('\n'.join(sorted(m['id'] for m in json.load(sys.stdin)['data'])))"
```

Elegir un modelo por etapa con el criterio de la memoria §2.1 (coste del error
por etapa) y comprobar que soportan la Responses API con salida estructurada.
Si se cambian los identificadores, actualizar **todos** estos sitios:

| Fichero | Qué |
|---|---|
| `.env.example` | `OPENAI_ANSWER_MODEL`, `OPENAI_CLAIM_EXTRACTION_MODEL`, `ALLIANZ_ROUTER_MODEL` |
| `backend/src/bootstrap.py` | valores por defecto (3 sitios) |
| `backend/src/infrastructure/adapters/outbound/query_workflow/langgraph_workflow.py` | valor por defecto del router |
| `backend/src/application/services/routing.py`, `claim_heuristics.py` | comentarios que citan el router |
| `docs/operacion.md`, `docs/evaluacion.md` | reparto de modelos y corrida de referencia |
| `docs/entrega/memoria.md` §2.1 y §3.4 | tabla de modelos y modelo de la corrida |

Comprobar con `grep -rn "gpt-5\.[0-9]" --exclude-dir=node_modules --exclude-dir=.venv .`
que no queda ninguno antiguo. El modelo de embeddings (`text-embedding-3-small`,
1536 dimensiones) va en `backend/configs/*.yaml`; cambiarlo cambia la firma del
índice y obliga a reindexar.

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
ruleset») no se sostiene y hay que cambiarla. Comprobar que
`unjustified_resolution_rate` sigue en 0.

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

## 5. Trazabilidad (comprobación manual) → memoria §5.1

- Lanzar una consulta y abrir el `langfuse_url` de la respuesta: debe verse la
  traza con spans por nodo y la generación con tokens y coste.
- Si el coste no aparece, configurar los precios del modelo elegido en Langfuse
  (Settings → Models); la propuesta de alertas de coste (§5.2) depende de ello.

## 6. Contenedores (comprobación manual) → `docs/operacion.md`

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

## 7. Antes de entregar

- [ ] Sin marcadores `_[insertar aquí]_` ni `_[pendiente…]_` en `memoria.md`
      (`grep -n "insertar\|pendiente" docs/entrega/memoria.md`).
- [ ] Revisar la memoria §8 (proceso con copilotos/SDD): es el relato de cómo se
      trabajó y solo la persona autora puede confirmarlo.
- [ ] Cifras de tests y de commits de la memoria coherentes con la última
      ejecución.
- [ ] Ningún secreto en el árbol: `git grep -n "sk-"` (solo debe salir el marcador `sk-lf-replace-with-local-value` de `ops/local.env.example`) y `.env` sin commitear.
- [ ] Exportar la memoria a PDF/Word si la entrega lo pide.
