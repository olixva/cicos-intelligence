# Validación pendiente antes de entregar

Lista de lo que hay que ejecutar con credenciales y servicios reales, y de dónde
va cada resultado en la [memoria](memoria.md). Las pruebas locales se ejecutan
en cada cambio; los humos sintéticos completados y las puertas aún pendientes
se detallan por separado.

## 0. Modelos seleccionados y acceso real

Los defaults versionados son `gpt-6.1-sol` para respuesta y extracción y
`gpt-6-luna` para el router OpenAI. Estos IDs figuran en el
[catálogo oficial](https://developers.openai.com/api/docs/models). Para la
campaña actual, los overrides locales del `.env` ponen **todas las llamadas de
prueba a OpenAI en `gpt-6-luna`**, según la decisión del usuario; no se llama a
Sol.

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

**Estado de esta ejecución:** los adaptadores de respuesta, extracción de
hechos y router completaron llamadas sintéticas con salida estructurada usando
`gpt-6-luna`. No se llamó a `gpt-6.1-sol` ni se ejecutó el golden completo. La
exportación de trazas a Langfuse no conectó con `127.0.0.1:3000`, aunque las tres
respuestas de OpenAI fueron satisfactorias. Sigue pendiente la comparación
Sol/Luna, que no se ejecutará mientras la campaña esté limitada a Luna, además
de Qdrant, Langfuse, el índice y el backend local. El default versionado de
respuesta/extracción permanece en `gpt-6.1-sol`.

## 1. Entorno

```bash
test -f .env || cp .env.example .env  # no sobrescribir credenciales/configuración existente
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

El runner registra en `manifest.json` el proveedor/modelo del router y el
backend y umbrales configurados para el guardarraíl; usa carpetas de salida
nuevas para que cada comparación sea reproducible. En esta ejecución no hay
backend local ni clave Jev, así que no se han generado resultados live.

```bash
# Terminal 1, desde la raíz: levantar el backend con el guard deseado.
ALLIANZ_INPUT_GUARD=off make serve-backend
# Terminal 2, también desde la raíz: el runner debe heredar la misma configuración.
cd backend
ALLIANZ_INPUT_GUARD=off uv run --no-sync python scripts/run_redteam.py \
  --output ../data/evaluation/results/redteam-off-$(date +%F)
# Detener y reiniciar Terminal 1 con ALLIANZ_INPUT_GUARD=jev; después repetir:
ALLIANZ_INPUT_GUARD=jev ALLIANZ_JEV_GUARD_INJECTION=0.9 \
  ALLIANZ_JEV_GUARD_OFF_TOPIC=0.95 make serve-backend
# En Terminal 2, registrar el mismo backend y los mismos umbrales en el manifiesto:
ALLIANZ_INPUT_GUARD=jev ALLIANZ_JEV_GUARD_INJECTION=0.9 \
  ALLIANZ_JEV_GUARD_OFF_TOPIC=0.95 uv run --no-sync python scripts/run_redteam.py \
  --output ../data/evaluation/results/redteam-jev-$(date +%F)
```

Sale con código 1 si algún ataque tiene éxito. Registrar en la memoria la tasa de
éxito del atacante, el desglose por categoría y el sobre-rechazo. Revisar a mano
`per-case/*.json` de cualquier fallo y de **una muestra de los que pasan**: los
criterios son de cadena y de estado, y un «pass» no prueba que la respuesta sea
buena. Si un ataque tiene éxito: o se corrige la defensa y se repite, o se
documenta como hallazgo abierto; no se edita el caso para que pase.
Comparar el mismo commit y la misma suite completa: Jev sólo se promueve si no
hay ataques exitosos y `over_refusal_rate` no supera el valor de `off`. Mantener
`ALLIANZ_INPUT_GUARD=off` como default mientras esta puerta esté pendiente.

## 5. Jev, el modelo de decisiones → memoria §2.1.1

Jev está integrado como **opción apagada por defecto** y nunca se ha ejecutado
contra el servicio real. El contrato se tomó del OpenAPI del SDK oficial
(`POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer`,
`{model, state, questions}` → `{model, answers, usage}`).

**Estado de esta ejecución:** no hay `TYPESAFE_API_KEY` configurada ni backend
local activo. No se ha enviado ninguna llamada ni se han generado resultados
A/B. El router predeterminado se mantiene en `openai`.

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
   Mismo commit, golden, índice, prompts y concurrencia en ambos procesos.
   Comparar exactitud sobre todos los casos, matriz por clase, errores técnicos,
   latencia y uso/coste disponible; los errores cuentan como fallos y permanecen
   en `n_total`. Barrer `ALLIANZ_JEV_ROUTER_MIN_CONFIDENCE` (0,4 / 0,6 / 0,8)
   en directorios nuevos. Sólo promover Jev si iguala o supera la exactitud de
   OpenAI; mantener OpenAI como referencia seleccionable y no añadir fallback
   silencioso.
3. **Guardarraíl, con la suite de red-teaming.** Ejecutar el paso 4 con
   `ALLIANZ_INPUT_GUARD=off` y con `jev`; comparar tasa de éxito del atacante y
   sobre-rechazo de los controles. Ajustar `ALLIANZ_JEV_GUARD_INJECTION` y
   `ALLIANZ_JEV_GUARD_OFF_TOPIC`. Guardar los manifiestos con cada umbral. Con el
   guard activo, un ataque bloqueado responde `kind=clarification` con
   `metadata.guardrail_source=decision_model`.
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
