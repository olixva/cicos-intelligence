# Matriz de cobertura del golden set

Estado: cobertura efectiva del golden actual (`development.jsonl`, **110 casos** =
5 siniestros del enunciado + 5 variantes ES heredadas + 100 sintéticos, todos en español,
congelado como release `synthetic-expansion-110-2026-09-03`). No contiene resultados de
evaluación.

| Eje | Desarrollo | Reserva | Control de admisión |
| --- | --- | --- | --- |
| Consultas documentales directas | Sí | Sí | Evidencia primaria y citas válidas. |
| Reglas con excepción o varias secciones | Sí | Sí | Paquete AND/OR de evidencia completo. |
| Tablas, notas y evidencia visual | Sí | Sí | Revisión visual contra el PDF original. |
| Accidentes de dos vehículos | Sí | Sí | Hechos atribuibles, contradicciones y datos ausentes explícitos. |
| Más de dos vehículos | Sí | Sí | Aplicabilidad y excepciones separadas. |
| Semáforos, aparcamiento, carril, alcoholemia | Sí (cubierto por casos del enunciado + nuevas variaciones sintéticas) | Sí (cuando se abra) | Ninguna familia cruza particiones. |
| Abstención, respuesta condicionada y fuera de alcance | Sí | Sí | Prohibición de conclusión definitiva injustificada. |
| Solo español (la reserva, cuando se abra, podría añadir otras lenguas) | n/a en `development` | Sí | Mismo significado; familia no dividida. |
| Robustez y citas adversariales | Sí | Sí | No se admite evidencia o hecho inventado. |

Los cinco siniestros del enunciado están incluidos dentro del golden actual (case_ids
`accident-01-rear-end` … `accident-05-alcohol-injury`, evidencia de aceptación de la
entrevista) junto con sus 5 variantes ES y los 100 sintéticos (50 siniestros + 50
consultas, balance exacto). La reserva se congela antes de utilizar resultados para
ajustar prompts, reglas, recuperación o enrutamiento.
