# Guion de defensa

Duración prevista: 30–45 minutos. La secuencia usa casos sintéticos del
enunciado y del golden; no se deben introducir expedientes reales.

| Tiempo | Bloque | Qué explicar o mostrar |
|---|---|---|
| 0–3 min | Problema | Qué información necesitan las personas tramitadoras y qué límites tiene el manual de 2004 |
| 3–7 min | Alcance | Consulta documental frente a análisis de un siniestro; qué queda fuera |
| 7–14 min | Datos y modelos | Ingesta PDF, fragmentos y citas; explicar que no hubo fine-tuning: se usa RAG con modelos preentrenados. Jev clasifica; OpenAI genera y extrae |
| 14–24 min | Demostración | Una consulta con citas y un accidente sintético que termine en exclusión o aclaración, con la traza visible si Langfuse está disponible |
| 24–31 min | Evaluación | Golden de 110 casos, comparación de router, métricas de citas, abstención y límites del modo `claim` |
| 31–36 min | Riesgos y decisiones | Separación del LLM y las reglas, red-team, privacidad y validaciones que faltan |
| 36–45 min | Preguntas | Responder dudas; ampliar la demo o la evaluación cuando haga falta |

## Demostración sugerida

1. **Consulta al manual:** «¿La alcoholemia del conductor excluye la aplicación
   de los Convenios CIDE/ASCIDE?». Comprobar que la respuesta cite las páginas
   del manual y abrir una de ellas.
2. **Siniestro con varios vehículos:** usar el caso sintético del enunciado de
   cinco coches en cadena. Explicar por qué el alcance del convenio se evalúa
   antes de intentar atribuir responsabilidad.
3. **Relato incompleto:** usar el caso de vehículo aparcado con fuga o el
   alcance con versiones contradictorias. Señalar qué información falta y que
   el sistema no debe rellenarla por inferencia.
4. **Observabilidad:** si Langfuse está operativo, abrir una traza y distinguir
   los spans, el modelo y los tokens que realmente registre. Si no está
   disponible, mostrar la evidencia guardada y declarar que la traza live no se
   ha verificado en esa sesión.

La demostración no debe prometer que el sistema resuelve siniestros de forma
fiable: la evaluación actual muestra una brecha en citas y un número alto de
aclaraciones. La presentación y el anexo de validación contienen los
denominadores y resultados completos.

## Preguntas previsibles

- **¿Se entrenó el modelo?** No. El modelo base conserva sus pesos; el prototipo
  añade recuperación del manual, instrucciones, salida estructurada y
  validación posterior.
- **¿Por qué Jev?** Router y guardarraíl responden valores tipados de conjuntos
  cerrados. Su resultado se expresa como elección o probabilidad y no redacta
  la respuesta al usuario.
- **¿Por qué no dejar que el LLM decida la culpa?** La imputación depende de
  reglas versionadas y hechos explícitos. El LLM extrae o explica; el motor
  determinista evalúa reglas y se abstiene si faltan hechos.
- **¿Está listo para producción?** No. Es un prototipo académico evaluado con
  datos sintéticos. Hace falta validación de dominio, privacidad, seguridad y
  rendimiento con datos autorizados antes de un piloto real.
