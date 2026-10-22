# Validación pendiente antes de entregar

Lista de lo que hay que ejecutar con credenciales y servicios reales, y de dónde
va cada resultado en la [memoria](memoria.md). Las pruebas locales se ejecutan
en cada cambio; los humos sintéticos completados y las puertas aún pendientes
se detallan por separado.

## 0. Modelos seleccionados y acceso real

Los defaults versionados son `gpt-6.1-sol` para respuesta y extracción, Jev
(`jev-latest`) para router y guard, y `gpt-6-luna` como router OpenAI de
referencia. Estos IDs figuran en el
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
hechos y router pasaron el humo estructurado con `gpt-6-luna`; después se ejecutó
el golden `auto` completo para OpenAI Luna y Jev (detalle en §5). No se llamó a
`gpt-6.1-sol`, según la instrucción del usuario, así que la comparación
Sol/Luna de extracción sigue pendiente y los defaults versionados de respuesta
y extracción permanecen en Sol. En el humo inicial el exportador de trazas no
conectó con `127.0.0.1:3000`; Qdrant y Langfuse locales sí estuvieron sanos para
E2E y el red-team. No se reindexó el manual.

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

Los tests de `backend/tests/integration/` también se incluyen en `check-all`.
El test de conversión del manual real está opt-in mediante
`ALLIANZ_INTEGRATION_PDF`; no se configura con un documento real en esta
validación, por lo que se omite ese caso.

**Resultado de esta ejecución (22-10-2026):** `make check-all` pasó con backend
`581 passed, 1 skipped, 2 warnings`; frontend `98 passed`; Ruff, formato,
Pyright, build y contrato OpenAPI correctos. El build avisa de un bundle
JavaScript mayor de 500 kB; los tests emitieron warnings de dependencias y de
`act` de React. `make test-e2e` pasó `2/2` con Qdrant, Langfuse y el backend
activo. Con el servidor arrancado desde `make serve-backend`, el preflight del
runner coincidió con `GET /health/config`: router Jev `jev-latest` (`0,4`),
guard Jev (`0,9`/`0,95`), OpenAI Luna para respuesta/extracción, commit del
servidor y huella del árbol. La sonda consultó el mismo Qdrant que las consultas
y resolvió `allianz-manual-active` a
`allianz-9cef6a7a250f-d0ae02340071`, 118 puntos, firma completa y SHA-256 del
manual esperado. `/health/ready` devolvió 200. Se usó el índice persistente, sin
reindexar ni hacer llamadas nuevas a OpenAI. La huella se calcula sobre el árbol
de trabajo, por lo que cambia al editar o confirmar cambios.

## 3. Re-medir la evaluación del RAG → memoria §3.4

```bash
make run-baseline ARGS="--limit 5 --output /tmp/baseline-smoke"  # humo
make run-baseline ARGS="--output data/evaluation/results/$(date +%F)-baseline \
  --label baseline --concurrency 4"
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

**Ejecutada el 22-10-2026** sobre el mismo commit `75da6320266f857e717fa9b846c44baaa0f4c746`, los mismos 30 casos (27 ataques y 3 controles) y concurrencia 4. El manifiesto conserva el hash de casos `28fbf1d3dff67ff98a6fa1ac8bfc8ba04c8b659c05aea999c6679455e2b7374b`, el hash/páginas del manual, router y umbrales. El runner confirmó `/health/config` antes de enviar los casos para modelos y guard; la verificación del build local y de la firma/destino del alias Qdrant se añadió después y se comprobó en la validación final de arriba.

| Guard | Ataques exitosos | Sobre-rechazo benigno | Resultado |
|---|---:|---:|---|
| `off` | 0/27 | 0/3 | referencia |
| `jev` (inyección `0.9`, fuera de tema `0.95`) | 0/27 | 0/3 | pasa la puerta; guard Jev predeterminado |

Las diez categorías registraron cero ataques exitosos. La muestra benigna es sólo de tres casos y no demuestra una tasa de rechazo real en producción. Resultados completos locales (ignorados por Git): `data/evaluation/results/2026-10-22-redteam-off-final/` y `data/evaluation/results/2026-10-22-redteam-jev-final/`.

Para reproducir con salidas nuevas:

```bash
# Terminal 1: router Jev a confianza 0.4, guard apagado.
make serve-backend LOCAL_ENV="ALLIANZ_ROUTER_BACKEND=jev ALLIANZ_JEV_ROUTER_MIN_CONFIDENCE=0.4 ALLIANZ_INPUT_GUARD=off"
# Terminal 2:
make run-redteam LOCAL_ENV="ALLIANZ_ROUTER_BACKEND=jev ALLIANZ_JEV_ROUTER_MIN_CONFIDENCE=0.4 ALLIANZ_INPUT_GUARD=off" \
  ARGS="--output data/evaluation/results/redteam-off-<id-nuevo>"
# Reiniciar Terminal 1 y repetir el runner con el guard Jev:
make serve-backend LOCAL_ENV="ALLIANZ_ROUTER_BACKEND=jev ALLIANZ_JEV_ROUTER_MIN_CONFIDENCE=0.4 ALLIANZ_INPUT_GUARD=jev ALLIANZ_JEV_GUARD_INJECTION=0.9 ALLIANZ_JEV_GUARD_OFF_TOPIC=0.95"
make run-redteam LOCAL_ENV="ALLIANZ_ROUTER_BACKEND=jev ALLIANZ_JEV_ROUTER_MIN_CONFIDENCE=0.4 ALLIANZ_INPUT_GUARD=jev ALLIANZ_JEV_GUARD_INJECTION=0.9 ALLIANZ_JEV_GUARD_OFF_TOPIC=0.95" \
  ARGS="--output data/evaluation/results/redteam-jev-<id-nuevo>"
```

El guard regex sigue ejecutándose antes de Jev y el guard semántico falla abierto si el servicio no responde. El router no hace fallback silencioso.

## 5. Jev, el modelo de decisiones → memoria §2.1.1

**Estado: validado en servicio real y predeterminado para router y guard.** La llamada sintética de humo usó una pregunta `noul` y otra `choice`; devolvió modelo `jev-1.14.0`, respuestas tipadas/probabilidades válidas y uso de 368 tokens de entrada y 50 de salida. No se enviaron relatos reales ni datos personales. Todas las llamadas OpenAI de la campaña fueron a `gpt-6-luna`, incluida extracción; `gpt-6.1-sol` no se probó.

La repetición A/B de router `auto` se ejecutó sobre commit `75da6320266f857e717fa9b846c44baaa0f4c746`, los mismos 110 casos, golden SHA-256 `837dfb6da86bcdf6cb7e2a1477623141b83c021f5c697910da5dfa1af074d874`, índice y concurrencia 4. `/health/config` confirmó backend, modelos y guard antes de cada campaña. Esas campañas no tenían la verificación del build local ni de la firma/destino real del alias, que se añadió después. La métrica es end-to-end: los errores técnicos y las rutas ausentes cuentan como fallos; no mide el clasificador aislado.

| Backend / umbral | Aciertos | Exactitud | Errores | Tokens medios entrada/salida |
|---|---:|---:|---:|---:|
| OpenAI `gpt-6-luna` | 94/110 | 0.855 | 0 finales | 332.782 / 75.309 |
| Jev `0.4` | 97/110 | 0.882 | 0 finales | 476.491 / 41.027 |

La primera pasada de cada campaña tuvo un error HTTP transitorio; `--resume`
reintentó sólo ese caso y ambas corridas quedaron completas. Los tiempos
acumulados observados son aproximadamente 358.4 s (Luna) y 297.3 s (Jev). En estos
manifiestos, creados antes de corregir la suma de tiempos reanudados, `duration_s`
conserva sólo el segmento del reintento; los tiempos publicados suman las salidas
de ambas pasadas. El runner acumula segmentos en nuevas reanudaciones desde el
commit `16e2c82`. El barrido exploratorio previo con Jev `0.6` y `0.8` dio
92/110 y 83/110; no constituye holdout independiente.

El umbral `0.4` es el único que iguala la referencia; por ello Jev `jev-latest` y `0.4` son los valores estándar. OpenAI Luna sigue disponible con `ALLIANZ_ROUTER_BACKEND=openai`. Las matrices completas, duraciones y errores observados están en `docs/evaluacion.md`. Los timeouts que aparecieron en logs correspondieron al extractor OpenAI Luna downstream y se mantuvieron como fallos del flujo completo.

**Coste de router, estimación de lista:** con la tarifa pública consultada el 22-10-2026 de Jev (`$0.042` por millón de tokens de entrada; salida gratis) y OpenAI Luna Standard (`$0.10` entrada / `$0.50` salida por millón), los tokens medios observados estiman `$0.000020` por decisión Jev frente a `$0.000071` Luna, cerca de 72 % menos para el router. No es facturación medida y excluye respuesta, extracción y otros componentes. Fuentes: [TypeSafe](https://typesafe.ai/) y [OpenAI Pricing](https://developers.openai.com/api/docs/pricing).

**Artefactos nativos locales** (ignorados por Git):
`data/evaluation/results/2026-10-22-router-openai-luna-final/` y
`data/evaluation/results/2026-10-22-router-jev-04-final/` conservan manifiesto,
métricas, resumen y los 110 archivos `per-case`. Las nuevas campañas red-team
están en `2026-10-22-redteam-off-final/` y `2026-10-22-redteam-jev-final/`.
El resumen antiguo `2026-10-22-router-openai-jev-04-reconstructed-summary.json`
continúa etiquetado como reconstruido y no sustituye los resultados nativos.

**Datos.** TypeSafe declara que no entrena con solicitudes/respuestas, pero retención y borrado dependen del acuerdo, los datos y cualquier arreglo ZDR. Confirmar las condiciones antes de enviar relatos reales: [tratamiento y retención de datos](https://help.typesafe.ai/articles/5974925716-how-is-submitted-data-used-or-retained). La validación live usó sólo texto sintético.

**Juez de evaluación (pendiente, no bloquea la promoción):** `run_baseline.py --modes question --judge jev`; etiquetar manualmente unos 30 pares pregunta/página y 30 bloques/páginas citadas para medir acuerdo. Hasta entonces, mantener sus métricas exploratorias y opt-in.

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
- [ ] Ninguna clave real del proveedor en el árbol ni en artefactos; los valores de ejemplo deben ser marcadores no válidos. Confirmar que `.env` permanece ignorado y fuera del índice de Git.
- [ ] Exportar la memoria a PDF/Word si la entrega lo pide.
