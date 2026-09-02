# Diseño — Entrevista de siniestros guiada por LLM

Fecha: 2 de septiembre de 2026.

## Objetivo

Convertir el análisis de siniestros en una entrevista acotada. El sistema no
emitirá una conclusión de culpa mientras falten hechos materiales; preguntará
por los que desbloqueen una regla del manual. El LLM decide qué falta y cómo
preguntarlo; las reglas revisadas siguen siendo la única fuente de una
atribución automática de responsabilidad.

## Decisiones

- El LLM devuelve una salida estructurada con hechos atribuidos y un plan de
  entrevista: `ask`, `ready`, `inconsistent` o `coverage_gap`.
- Cada pregunta tiene un identificador semántico estable, texto para el
  usuario, motivo breve, tipo de respuesta y opciones opcionales. Nunca se
  exponen casillas internas A0--A17 salvo que el usuario haya aportado una DAA
  y sea estrictamente necesaria para la matriz.
- LangGraph guarda el plan, respuestas normalizadas, preguntas ya realizadas y
  número de rondas en el mismo `thread_id`. Una reanudación sólo añade hechos;
  no reinicia la entrevista ni repite una pregunta respondida.
- Máximo tres rondas y tres preguntas por ronda. `No lo sé` marca un hecho como
  no disponible. Si una ronda no añade ningún hecho nuevo, el flujo termina con
  una explicación de insuficiencia, sin volver a preguntar.
- `ready` sólo permite evaluar una regla determinista. Si ninguna regla
  verificable cubre el supuesto después de los hechos disponibles, se devuelve
  `coverage_gap`, no “Convenio aplicable pero no puedo determinar”.
- `inconsistent` explica las versiones incompatibles y ofrece una sola pregunta
  de contraste sólo si puede resolver la contradicción; de otro modo finaliza
  como contradicción no resoluble.
- Se mantiene `MemorySaver` para la demo local. Su pérdida de estado tras un
  reinicio se documenta; producción requeriría `AsyncPostgresSaver`.

## Flujo

```text
extract_and_plan -> retrieve -> assess_requirements ->
  ask_human --Command(resume)--> extract_and_plan
  ready -----------------------> evaluate_rules -> explain
  inconsistent/coverage_gap ---> explain_terminal
```

El planificador recibe el relato original, aclaraciones acumuladas, hechos ya
confirmados, contradicciones, reglas candidatas y preguntas anteriores. Debe
preguntar únicamente por un hecho que cambie la aplicabilidad, haga coincidir
una regla revisada, distinga dos reglas candidatas o resuelva una contradicción.

## Contrato de entrevista

```json
{
  "status": "ask | ready | inconsistent | coverage_gap",
  "questions": [{
    "id": "vehicle_a_signal",
    "prompt": "¿Qué color tenía el semáforo del vehículo A?",
    "reason": "La señal puede cambiar la prioridad.",
    "answer_kind": "choice | text | boolean",
    "options": ["Verde", "Ámbar", "Rojo", "No se sabe"]
  }],
  "terminal_reason": "string | null"
}
```

Los límites se validan en código: no IDs repetidos, no preguntas ya respondidas,
ni `ready` con preguntas, ni `ask` sin preguntas. Las opciones son sugerencias:
la interfaz siempre permite texto libre.

## Estados visibles

| Estado | Interfaz | Resultado |
| --- | --- | --- |
| `ask` | Paso “Necesito confirmar…” con preguntas y opciones. | `resolved_mode=clarification` |
| `ready` | Sin formulario. | Decisión determinista y citas. |
| `inconsistent` | Explica la discrepancia; una pregunta de contraste si sirve. | Sin imputación. |
| `coverage_gap` | Explica que los hechos están completos pero ninguna regla revisada cubre el caso. | Sin imputación. |
| límite/no progreso | Lista los hechos aún desconocidos y permite cerrar. | Sin imputación. |

## Aceptación

- El caso de dos semáforos pregunta por colores y versiones, no concluye ni usa
  “aplicable pero indeterminado”.
- Un cambio de carril reconocido por ambos llega directamente a la regla b.10 y
  se resuelve sin DAA.
- Alcance simple, fuga de vehículo y alcohol/lesiones preguntan sólo por los
  hechos relevantes o cierran con una limitación explícita.
- Cinco vehículos termina como no aplicable sin entrevista.
- Una conversación de dos respuestas parciales conserva lo ya aportado y no
  repite preguntas; tras tres rondas o falta de progreso finaliza.
- API, SSE y frontend representan los estados sin textos de reserva engañosos.
