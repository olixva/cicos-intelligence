# Guion de demo — Allianz CICOS Claims Intelligence

Actualizado el 2026-09-03 para acompañar a `docs/entrega/presentacion.pptx` (44 láminas) y a
`docs/entrega/arquitectura.md`. Las cuatro paradas de este guion son las cuatro láminas del
bloque **04 · Demo en vivo** del deck; cada lámina lleva además este guion en sus notas de
orador. Todos los comandos son reproducibles en local.

**Reparto de los 45 minutos**: 4 min problema · 4 min plan y riesgos · 12 min arquitectura ·
**12 min demo** · 6 min evaluación y límites · 7 min preguntas.

## 0. Arranque (antes de la sesión)

```bash
make local-services-config && make local-services-up   # Qdrant, Langfuse, postgres, redis, clickhouse, minio
make serve-backend    # API en :8000
make serve-frontend   # cliente en :5173
curl localhost:8000/health/ready                       # {"status": "ready"}
```

Tener abiertas, además del cliente: la interfaz de Langfuse en otra pestaña, `docs/ESTADO.md`,
`data/rules/ruleset.v1.json` y `data/evaluation/golden/development.jsonl`. Si la sala pregunta
por algo, es más rápido enseñarlo que describirlo.

## Demo 1 — Enrutado y consulta documental (3 min)

En **modo Automático**, sin elegir recorrido:

> «¿Qué establece el manual sobre la alcoholemia?»

Qué señalar, en este orden:

1. La etiqueta de modo detectado (**Consulta del manual**) *antes* de leer la respuesta: el
   enrutado nunca es una caja negra.
2. La respuesta llega por bloques y cada bloque trae su cita.
3. Pulsar la cita: se abre el PDF original por la **página 9 de 111**, junto a la respuesta.

Si preguntan por el resaltado: con el índice activo (pypdf) no hay coordenadas verificadas, así
que se abre la página completa en lugar de fingir un resaltado. El perfil Docling sí las tiene
— es la decisión de la lámina de parsers.

## Demo 2 — El siniestro que sí se resuelve (4 min)

Modo **Siniestro**, ejemplo de demo `accident-04-lane-change-es` (no escribirlo a mano: se
ahorran 40 segundos).

Qué señalar:

1. **Hechos extraídos con atribución**: `vehicle_count`, `direct_collision`,
   `lane_change_acknowledged_by_both`, `lane_change_vehicle`, `contradictory_versions` — cada
   uno indica de dónde sale («según relato», «según ambos conductores»).
2. La tarjeta **Reglas evaluadas** desplegada: las 14 reglas del artefacto firmado, las que
   casan y las que declaran `no comprobable con los datos aportados`. Esa ausencia es
   información.
3. **Decisión emitida**: `ASCIDE · El Convenio es aplicable · Resuelto`, culpable el vehículo
   que cambia de carril, citando la norma subsidiaria **b.10** (pág. 75) con su texto literal.

Remate: «El modelo no ha decidido esto. Ha rellenado tres hechos y el motor ha aplicado una
norma firmada que cualquiera puede leer en el artefacto.»

## Demo 3 — Abstenerse con criterio, y pedir el dato exacto (5 min)

La parada más importante de las cuatro. Si hay que recortar tiempo, recortar la 1, no ésta.

1. **Fuera del Convenio con fundamento** — `accident-02-pile-up-es` (colisión múltiple, cinco
   vehículos): se declara `not_applicable` citando la pág. 56 (dos vehículos en colisión
   directa) y la pág. 57 (colisión en cadena). Es el caso que más sorprende: parece el más
   grave y se cae por la puerta de entrada.
2. **La interrupción en directo** — un relato que declara explícitamente las casillas del
   apartado 12 («en el parte marcamos A2 y B4»). El grafo se detiene y pide el hecho de la
   observación impresa bajo la tabla, con su texto literal: *«A2 + B4 ⇒ culpable B, salvo que el
   conductor de A abra la puerta»*.
3. **Las dos ramas de la excepción** — responder primero «abrió la puerta el conductor de B»:
   resuelve a B. Repetir con «la abrió el de A»: la excepción retira la atribución y queda
   indeterminado, sin inventar quién responde.
4. **Fuera de alcance** — la pregunta de demo sobre el baremo de lesiones: el sistema se
   abstiene **sin dar cifras**, en vez de improvisar un baremo que el manual no contiene.

## Demo 4 — Trazabilidad y operación (2 min)

1. Abrir la traza del caso de la demo 2 desde el enlace **«Ver en Langfuse»** de la propia
   respuesta: nodos del grafo, llamadas al modelo, coste y latencia por etapa.
2. El `session_id` agrupando todos los pasos del hilo, incluida la interrupción y su reanudación.
3. **Modo administrador**: hash verificado del documento, 111 páginas, extracciones publicadas
   (pypdf y Docling) y previsualización paginada de lo que realmente se indexó.

Remate: la misma traza que mira quien opera el sistema es la que alimenta la evaluación.

## Después de la demo — qué se cuenta con láminas

- **Golden set**: 110 casos (`allianz golden validate` → `errors: []`, `item_count: 110`),
  congelados como release `synthetic-expansion-110-2026-09-03`. Anatomía de un caso: no guarda
  una respuesta, guarda requisitos, alternativas aceptables, prohibiciones y paquetes de
  evidencia AND/OR.
- **Protocolo de evaluación** y su estado real: qué está construido, qué está en curso y qué
  está pendiente por decisión (el holdout se abre una sola vez).
- **Límites declarados**: manual de 2004, lesiones y vía penal fuera de alcance, las casillas
  de la D.A.A. no se infieren, el golden no tiene revisión de un experto humano, no hay holdout
  y `ascide-b11-roundabout` sigue sin condición verificable.

## Preguntas previsibles y dónde está la respuesta

| Pregunta | Dónde |
|---|---|
| «¿Esto no lo está inventando el modelo?» | Lámina del motor de reglas + tarjeta *Reglas evaluadas* en la demo 2. |
| «¿Y si el manual cambia de versión?» | Cadena de custodia de la ingesta: hash verificado y publicación atómica. |
| «¿Por qué no usáis Docling si es mejor?» | Lámina de parsers: se activa por evaluación, no por disponibilidad. |
| «¿Cómo sabéis que no empeora al reindexar?» | Firma de índice de 13 campos y rollback probado. |
| «¿Qué métricas tenéis?» | Lámina de protocolo, con la caja de estado real. No inventar números. |
| «¿Cuánto cuesta una consulta?» | Langfuse, desglose por etapa de la traza abierta en la demo 4. |

## Si algo falla en directo

- Sin servicios: `make local-services-up` y `curl localhost:8000/health/ready`.
- Sin respuesta del modelo: cambiar a los ejemplos de demo, que están verificados, y explicar
  el recorrido con la lámina de la interfaz (lleva la captura real del razonamiento).
- Sin red: las láminas 17 y 19 contienen capturas reales del producto — la demo se puede
  contar sin el sistema delante, aunque pierde fuerza.
