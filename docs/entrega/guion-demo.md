# Guion de demo — Allianz CICOS Claims Intelligence

Recreado el 2026-09-02. Recorrido en directo para la presentación de 30–45 minutos, apoyado en
`docs/entrega/arquitectura.md`. Todos los comandos son reproducibles localmente.

## 0. Arranque (antes de la sesión)

```bash
make local-services-config && make local-services-up   # Qdrant, Langfuse, postgres, redis, clickhouse, minio
make serve-backend    # backend en :8000, mapea claves de Langfuse desde ops/local.env
make serve-frontend   # frontend en :5173
```

Comprobar `GET /health/ready` → `{"status": "ready"}` antes de arrancar.

## 1. Contexto (3 min)

- Enunciado: RAG sobre `Manual-cide-ascide-y-cicos.pdf` (111 páginas, nov. 2004) que responde
  preguntas del manual y analiza accidentes.
- Alcance explícito: no es normativa vigente, no hay autenticación multiusuario, no se opera con
  siniestros reales.
- Tres modos: Automático (por defecto), Consultar manual, Analizar siniestro.

## 2. Modo Automático — enrutamiento (5 min)

En la pantalla principal, enviar una pregunta puramente documental sin mencionar un accidente:

> «¿Qué establece el manual sobre la alcoholemia?»

Mostrar: `Modo detectado: Consulta del manual`, la respuesta con citas, apertura del PDF en la
página 9. Señalar que el router no responde al contenido, sólo clasifica.

Luego enviar un relato de accidente hipotético para mostrar que el router también acierta con
narrativas sin datos completos, sin forzar una aclaración innecesaria.

## 3. Consulta documental explícita (5 min)

Cambiar a "Pregunta". Preguntar algo con referencias cruzadas, p. ej. sobre adelantamientos y
prioridad de paso. Mostrar:

- Bloques de respuesta con citas explícitas por afirmación.
- Apertura del PDF junto a la respuesta; sin coordenadas verificadas, navega a la página sin
  fingir un resaltado.
- Estados `answered`/`partial`/`insufficient_evidence`/`out_of_scope` si aparece alguno.

## 4. Análisis de siniestro — el caso que se resuelve (8 min)

Cambiar a "Siniestro" y usar el ejemplo de demo `accident-04-lane-change`:

> «While changing lanes on the highway, Car A sideswipes Car B. Car A claims that Car B was in
> their blind spot and did not signal, while Car B claims that Car A did not check their
> mirrors before changing lanes.»

Mostrar en el resultado:

- `Reglas evaluadas` expandido: hechos extraídos (`lane_change_acknowledged_by_both=true`,
  `contradictory_versions=true`, `lane_change_vehicle=A`), atribución y texto literal de origen.
- `Decisión emitida`: **Convenio aplicable · ASCIDE · resuelto** — culpable el Coche A, citando
  la norma subsidiaria b.10 (pág. 75) con el texto exacto del manual.
- Enlace "Ver en Langfuse" a la traza real de esa ejecución.

Explicar brevemente que este es el único de los cinco casos originales del enunciado que se
resuelve de forma determinista con los datos del relato — y por qué eso es correcto, no una
limitación oculta.

## 5. Análisis de siniestro — abstención con criterio (5 min)

Usar `accident-02-pile-up` (cinco vehículos, colisión en cadena):

> «During heavy rain, a multi-vehicle pile-up occurs on the highway involving five cars…»

Mostrar que el sistema declara `not_applicable` citando la página 56 (dos vehículos exigidos) y
las páginas 57–58 (colisión en cadena), sin inventar una conclusión. Contrastar con
`accident-01-rear-end`: aplicable, pero `undetermined` en cuanto a culpa porque faltan las
casillas DAA (A0–A17) de la declaración amistosa — mostrar que el sistema pide exactamente ese
dato, no una respuesta genérica.

## 6. Visor de evidencias y trazabilidad (4 min)

- Pulsar una cita: PDF junto a la respuesta, número de página física vs. etiqueta impresa.
- Modo administrador: estado de ingesta, hash verificado, 111 páginas, extracción publicada
  (pypdf y Docling), previsualización de extracciones paginada.
- Langfuse: abrir la traza enlazada, mostrar `session_id` agrupando los pasos de un hilo, coste
  y latencia por etapa.

## 7. Golden set y evaluación (5 min)

- `data/evaluation/golden/development.jsonl`: los 5 casos con schema completo, citas reales,
  revisión de tres pasos por IA documentada (`metadata.review`), declarando explícitamente que
  no hay revisión de un experto humano del dominio.
- `allianz golden validate` en vivo: `item_count: 5`, cero errores.
- Release congelada `v1-interview-2026-09-02` publicada como dataset en Langfuse.

## 8. Límites y próximos pasos (3 min)

- 7 de 14 reglas del ruleset siguen documentadas pero no verificables automáticamente (matriz
  18×18 incluida); se explica el patrón usado para completar la primera (`b.10`) y que el mismo
  patrón se replica para el resto.
- Índice Docling/structured publicado pero no promovido a demo: falta la comparación de
  evaluación baseline-vs-structured.
- Golden set limitado a los 5 casos de entrevista; falta ampliar con generación Ragas + revisión
  y congelar una reserva.

## 9. Preguntas y respuestas

Reservar el tiempo restante. Tener a mano: `docs/ESTADO.md` (estado verificado), el ruleset
firmado, y la traza de Langfuse del caso resuelto.
