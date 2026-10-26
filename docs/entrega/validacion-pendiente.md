# Estado de validación y límites

Actualizado el 26-10-2026. Resume las comprobaciones reproducibles del código
actual y los límites que deben acompañar a la entrega. Las evaluaciones usan
casos sintéticos; no se enviaron expedientes reales ni datos personales.

## Puertas de calidad

`make check-all` terminó correctamente:

- Ruff y formato: correctos.
- Pyright estricto: 0 errores.
- Backend: 602 tests recopilados, 601 aprobados y 1 omitido (integración
  opcional de Docling); pytest registró 2 avisos de dependencias.
- Frontend: lint y TypeScript correctos; 99 tests aprobados.
- Build de producción y contrato OpenAPI: correctos. Vite advierte que el
  chunk principal de 628 KB supera el umbral informativo de 500 KB.
- `make test-e2e`: 2/2 escenarios de Playwright aprobados.

Los avisos de React/localStorage y el tamaño del bundle no hicieron fallar las
puertas. La imagen Docker final se construye y prueba con la huella asociada al
commit de entrega; el resultado se describe en `docs/operacion.md`.

## Configuración y evaluación final

La corrida final usó `gpt-6-luna` para respuesta y extracción, Jev
(`jev-latest`) para router y guardarraíl, confianza del router 0,4 y umbrales de
guard 0,9/0,95. Ejecutó 110 casos en `question`, `claim` y `auto`: 330/330
respuestas completas, 0 errores técnicos, 1244,9 s. El golden tiene SHA-256
`837dfb6d…074d874`; el manual tiene SHA-256
`b9c70c74…54c8344` y el índice activo contiene 118 puntos. El manifiesto
registra como commit base `660595e1` y huella de fuentes
`f9e6a230efee0209…`; esta huella identifica `backend/src`, `backend/scripts`,
`configs` y `prompts` del árbol ejecutado.

| Modo | Métrica | Valor | Casos puntuados | Sin puntuación | No aplicable |
|---|---|---:|---:|---:|---:|
| question | Estado de respuesta | 0,509 | 53 | 0 | 57 |
| question | Validez de citas | 0,408 | 110 | 0 | 0 |
| question | Cobertura de evidencia | 0,495 | 110 | 0 | 0 |
| claim | Aplicabilidad | 0,500 | 8 | 101 | 1 |
| claim | Convenio | 0,000 | 2 | 101 | 7 |
| claim | Decisión | 0,625 | 8 | 101 | 1 |
| claim | Validez de citas | 0,036 | 110 | 0 | 0 |
| claim | Cobertura de evidencia | 0,015 | 110 | 0 | 0 |
| cross-mode | Sobre-resolución frente a referencia | 0,000 | 8 | 49 | 53 |

El sistema pidió aclaraciones en 101/110 relatos de siniestro. La exactitud de
la decisión se calculó sobre sólo ocho casos y la tasa de sobre-resolución sobre
otros ocho puntuables; ninguna cifra acredita que el sistema pueda resolver
siniestros de forma fiable. La baja validez de citas y cobertura de evidencia en
`claim` también limita su uso.

### Comparación y seguridad

Jev y OpenAI Luna acertaron 97/110 rutas (88,2 %) cada uno sobre el mismo
conjunto, índice y huella; no hay diferencia de exactitud en esta muestra. La
corrida OpenAI se reanudó tras un timeout transitorio y terminó con 110/110
casos, sin errores. No se deduce ahorro monetario de los tokens: no se midieron
precios comparables de Jev y OpenAI.

En tres variantes red-team —Jev con guard `off`, Jev con guard Jev y OpenAI
Luna con guard Jev— hubo 0/27 ataques exitosos y 0/3 controles benignos
rechazados por variante. La batería no demuestra una mejora causal del guard
Jev. Los resultados y la matriz completa figuran en
[el anexo de evidencias](evidencias/README.md).

## Integraciones, privacidad y límites académicos

La respuesta interrumpida de `claim` conserva `thread_id`, `trace_id` y el campo
`langfuse_url`; un test de regresión y una petición sintética en Docker lo
comprobaron. Se comprobó una traza mediante la API de Langfuse; el enlace no se
abrió manualmente en su interfaz y no se midió coste.

TypeSafe declara que no entrena con solicitudes y respuestas, que la retención
depende de los datos y del acuerdo, y que ofrece ZDR a clientes Enterprise tras
configuración. Su política indica alojamiento del servicio en Estados Unidos.
No se verificó un contrato, DPA ni configuración ZDR para esta instalación.
Antes de usar relatos reales deben revisarse esos términos y la transferencia
internacional ([guía de retención](https://help.typesafe.ai/articles/5974925716-how-is-submitted-data-used-or-retained),
[política de privacidad](https://typesafe.ai/legal/privacy-policy)). OpenAI se
usa con `store=False`, lo que no desactiva por sí solo los registros de abuso
que pueden conservar contenido hasta 30 días por defecto.

El golden y el red-team son sintéticos y no los adjudicó una persona experta en
convenios. La matriz CIDE coincide entre lectura visual y extracción estricta
de texto, y el autor firmó el artefacto; eso no sustituye la revisión de un
experto. El manual fuente es de 2004 y no sustituye normativa vigente.

Antes de presentar, la persona autora debe revisar la descripción personal del
proceso en §8 de la memoria y completar los datos de portada o formato que
exija su universidad. No se atribuyen actividades no comprobables ni se inventa
metadato institucional.
