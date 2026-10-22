# Diseño: actualización de modelos y adopción validada de Jev

**Fecha:** 22 de octubre de 2026
**Rama de trabajo:** antonio-oliva_allianz/TFM
**Estado:** diseño aprobado; puertas live de Jev completadas el 22-10-2026
**Alcance global:** completar las observaciones de la auditoría funcional y dejar el TFM listo para entrega. Esta especificación concreta la primera fase: modelos y Jev.

## 1. Objetivo

Actualizar los modelos OpenAI del proyecto y decidir con mediciones reproducibles dónde Jev reduce coste sin degradar la calidad o la seguridad. Jev pasará a ser el backend predeterminado del router y del guardarraíl semántico sólo si supera los criterios de aceptación de esta especificación. OpenAI seguirá generando las respuestas documentales y extrayendo los hechos de siniestros.

## 2. Contexto observado

La rama TFM ya incluye un cliente HTTP para Jev y adaptadores para tres usos: router, guardarraíl semántico y jueces de evaluación. En el diseño router y guard estaban apagados o usaban OpenAI por defecto. El cliente y las puertas de router/guard se validaron contra el servicio el 22-10-2026; el juez y el umbral en un golden independiente siguen pendientes.

La auditoría global contiene trabajo adicional sobre evaluación, reglas, evidencia, persistencia, interfaz, operación y documentación. Se conservará ese alcance para las fases siguientes. Las tareas que reparan normalización y denominadores de evaluación son un requisito previo para confiar en las comparaciones que determinan valores por defecto.

La línea base de esta rama se ejecutó antes de escribir esta especificación: backend y frontend pasan; OpenAPI no presenta drift. Los resultados concretos quedan registrados en la conversación de trabajo.

## 3. Diseño aprobado

### 3.1 Asignación inicial de modelos

| Etapa | Modelo inicial | Condición |
|---|---|---|
| Respuesta documental | gpt-6.1-sol | Modelo predeterminado, sujeto a una llamada real con salida estructurada |
| Extracción de hechos | gpt-6-luna como candidato | Se conserva sólo si la evaluación comparable no empeora las métricas de seguridad; en caso contrario, gpt-6.1-sol |
| Router OpenAI | gpt-6-luna | Referencia de comparación cuando Jev se evalúe o no esté habilitado |
| Embeddings | text-embedding-3-small, 1536 dimensiones | Sin cambios ni reindexación en esta fase |

Los IDs corresponden al catálogo oficial vigente. La asignación favorece Sol para respuestas con citas y usa Luna en la campaña solicitada. La estimación de coste del router se calcula con tokens medidos y tarifa pública, y se identifica como una estimación de lista, no como facturación observada.

### 3.2 Usos de Jev

Jev se usará para decisiones tipadas que ya tienen un contrato cerrado:

- **Router automático:** opción de producción después de comparar su clasificación con OpenAI sobre el mismo golden, con igual conjunto de casos y reporte de exactitud, matriz de confusión, latencia y uso.
- **Guardarraíl semántico:** complemento al guardarraíl determinista existente. Sólo se activa por defecto si la campaña de red-teaming no registra ataques exitosos y el sobre-rechazo no supera la referencia.
- **Juez de evaluación:** uso opcional, con resultados identificados como juicio del modelo. La memoria sólo publicará sus cifras junto con el acuerdo medido en una muestra etiquetada por personas.

La decisión sobre activar Jev se toma de forma independiente para router y guardarraíl. Si una puerta no se supera, su configuración de producción permanece en la conducta previa y Jev queda disponible para experimentación.

Jev no redactará respuestas documentales ni reemplazará en esta fase la extracción completa de hechos. Esos contratos requieren texto y hechos tipados con procedencia/evidencia; la interfaz actual de Jev resuelve elecciones y probabilidades. Cualquier ampliación a campos discretos del extractor se evaluará después, sin sustituir el motor determinista de reglas.

### 3.3 Fallos y confianza

- El guardarraíl regex sigue ejecutándose antes del guardarraíl Jev.
- La indisponibilidad de Jev en el guardarraíl conserva el comportamiento de fallo abierto que ya define la rama; la API registra el fallo y siguen activas las defensas posteriores.
- Una confianza de router inferior al umbral produce aclaración, no una ruta adivinada.
- Las respuestas remotas deben validar que hay una contestación para cada pregunta, que sus tipos coinciden y que las probabilidades están en [0, 1].
- Una caída del router Jev debe terminar en un error de proveedor controlado; no se añadirá un fallback silencioso que oculte qué modelo respondió.
- Los jueces nunca deciden responsabilidad ni modifican una respuesta de usuario.

### 3.4 Datos y credenciales

Las pruebas remotas de Jev usarán el golden y casos sintéticos. No se enviarán relatos reales con datos personales hasta revisar el acuerdo de tratamiento y retención aplicable. TypeSafe declara que no entrena con las entradas, pero indica que retención y borrado dependen del acuerdo, los datos y las obligaciones aplicables.

Las claves se obtienen sólo de variables de entorno: OPENAI_API_KEY y TYPESAFE_API_KEY. No se guardarán en archivos versionados, logs, trazas ni esta memoria. Las pruebas locales no requieren claves si usan dobles de proveedor.

## 4. Plan de validación requerido

1. **Congelar referencias antes de cambios de comportamiento.** Guardar commit, configuración, versiones y métricas reproducibles. Reparar previamente la normalización y los denominadores afectados por la auditoría antes de usar esas métricas para activar proveedores.
2. **Validar OpenAI.** Con una clave proporcionada por el usuario, comprobar que gpt-6.1-sol y gpt-6-luna están disponibles y aceptan las llamadas de Responses API y salidas estructuradas de los adaptadores existentes.
3. **Validar Jev.** Con TYPESAFE_API_KEY, enviar una llamada sintética con una pregunta noul y otra choice; verificar el modelo devuelto, las respuestas, probabilidades, uso y tratamiento de errores.
4. **Comparar el router.** Ejecutar el mismo golden con OpenAI y Jev; reportar exactitud, matriz de confusión, latencia y tokens/coste disponibles.
5. **Comparar el guardarraíl.** Ejecutar red-teaming con guardarraíl Jev apagado y encendido; reportar éxito de ataque, sobre-rechazo y desglose por categoría. Ajustar umbrales sólo con estos resultados.
6. **Comparar extracción.** Ejecutar el golden con gpt-6.1-sol y gpt-6-luna bajo el mismo entorno; conservar Luna sólo si no introduce nuevas resoluciones injustificadas ni una regresión material en las métricas adjudicadas.
7. **Calibrar jueces.** Etiquetar manualmente una muestra de relevancia de contexto y soporte de citas. Reportar acuerdo y desacuerdos; hasta entonces, los scores de Jev son exploratorios y no son gates.
8. **Actualizar memoria y validación pendiente.** Reemplazar afirmaciones no verificadas sólo con mediciones guardadas, con fecha, commit, IDs de modelo, configuración y denominadores.

## 5. Criterios de aceptación

- Los valores por defecto, variables de entorno y documentación describen los modelos realmente seleccionados.
- La llamada real al modelo OpenAI seleccionado en esta campaña (Luna) y a Jev cumple sus contratos; Sol no se probó por instrucción del usuario. Los tests unitarios cubren salidas inválidas, errores HTTP, timeout y ausencia de clave.
- El router Jev sólo queda predeterminado si iguala o supera la referencia OpenAI en el golden adjudicado.
- El guardarraíl Jev sólo queda predeterminado si la campaña no tiene ataques exitosos y el sobre-rechazo no supera la referencia.
- La extracción usa Luna sólo si no aparecen nuevas resoluciones injustificadas y no empeoran materialmente las métricas adjudicadas; de otro modo usa Sol.
- Los scores del juez Jev se etiquetan como exploratorios hasta medir su acuerdo humano.
- Ninguna métrica de una corrida con errores de proveedor se presenta como resultado completo.
- Las claves no aparecen en Git, artefactos, trazas ni salida de pruebas.
- make check-all y make test-e2e pasan en la rama final; las pruebas con servicios/API se informan por separado de las pruebas locales.
- La memoria no conserva marcadores de validación pendiente para las comprobaciones que sí se hayan ejecutado.

## 6. Resultado de las puertas live (22-10-2026)

- **Cliente:** un humo sintético `noul` + `choice` devolvió `jev-1.14.0`, probabilidades válidas y uso de 368 tokens de entrada / 50 de salida.
- **Router:** repetición final en el commit `75da6320266f857e717fa9b846c44baaa0f4c746`, mismo golden de 110 casos, índice y concurrencia 4: el flujo `auto` obtuvo 97/110 con Jev `0,4` y 94/110 con OpenAI Luna, sin errores finales tras reintentar un caso HTTP en cada campaña. El nombre de la métrica aclara que incluye disponibilidad downstream, no sólo clasificación. Se adopta `jev-latest` con umbral `0,4`; OpenAI Luna permanece seleccionable. El umbral se eligió con el mismo golden, no un holdout independiente. Las matrices, tokens, manifiestos y límites están en `docs/evaluacion.md`.
- **Guard:** nuevas corridas en ese commit con `off` y Jev dieron 0/27 ataques exitosos y 0/3 sobre-rechazos; Jev con umbrales `0,9`/`0,95` se adopta por defecto. La muestra benigna es limitada.
- **Coste:** usando tarifas públicas del 22-10-2026 y tokens medidos, el router Jev `0,4` estima cerca de 72 % menos que OpenAI Luna por decisión. No es una factura ni el coste total de respuesta/extracción.
- **Datos:** sólo se enviaron entradas sintéticas. TypeSafe declara que no entrena con solicitudes/respuestas, pero la retención depende del acuerdo y cualquier ZDR; revisar antes de usar relatos reales.
- **Pendiente:** comparar extracción Sol/Luna, validar el umbral en un holdout independiente y calibrar el juez Jev con personas. Los errores técnicos de las corridas quedan en el denominador y no se ocultan.

## 7. Fuera de esta fase

Las correcciones del motor de decisión de siniestros, catálogo DAA, precedencias normativas, recuperación de tablas, persistencia multi-turno, estado conversacional de frontend, publicación de datasets en Langfuse, controles de despliegue y el resto de la auditoría continúan como fases posteriores. No se cambiarán reglas funcionales ni firmas de índice como parte de la actualización de modelos.

## 8. Referencias técnicas

- Catálogo OpenAI: https://developers.openai.com/api/docs/models
- Precios OpenAI: https://developers.openai.com/api/docs/pricing
- API Responses: https://developers.openai.com/api/reference/resources/responses/methods/create
- Uso y retención de datos de TypeSafe: https://help.typesafe.ai/articles/5974925716-how-is-submitted-data-used-or-retained
- Requisitos de entrega y validación del repositorio: docs/entrega/validacion-pendiente.md
- Alcance funcional global: el documento de auditoría funcional entregado para este encargo; la lista de validación de entrega de esta rama está en docs/entrega/validacion-pendiente.md.
