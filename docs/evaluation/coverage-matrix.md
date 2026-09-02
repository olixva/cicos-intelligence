# Matriz de cobertura del golden set

Estado: cobertura efectiva del golden actual (`development.jsonl`, 100 casos en español,
congelado como release `synthetic-expansion-2026-09-02`). No contiene casos admitidos ni
resultados de evaluación.

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

Los cinco siniestros del enunciado están incluidos dentro del golden actual (como family_ids
`accident-0X-…`) junto con sus variantes y muchos otros casos sintéticos que amplían la
cobertura (50 siniestros + 50 consultas, balance exacto). La reserva se congela antes de
utilizar resultados para ajustar prompts, reglas, recuperación o enrutamiento.
