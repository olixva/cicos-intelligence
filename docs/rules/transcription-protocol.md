# Reglas y matriz CIDE — protocolo de transcripción y atestación

> **Estado:** borrador (2026-09-02). Ninguna decisión automatizada
> puede leerse de la tabla extraída automáticamente ni del contenido de
> un solo revisor.

## 1. Fuentes documentales

- Manual CIDE/ASCIDE/CICOS, edición noviembre de 2004.
  Hash esperado:
  `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`.
  Página 101 contiene la matriz de responsabilidad 18×18 (A contra B).
- Página 32 (DAA escaneada) y página 101 (matriz) requieren
  revisión contra el PDF original; las advertencias que emita Docling
  sobre estas páginas no invalidan la existencia de la tabla, solo la
  confianza en una transcripción automática.

## 2. Lo que NO se permite

* Convertir la tabla extraída por Docling en reglas directamente. Las
  tablas extraídas sirven solo como índice visual para el revisor.
* Crear el artefacto a partir de un único revisor. La matriz exige
  dos transcripciones independientes y resolución documentada de
  divergencias contra el PDF.
* Inventar filas, columnas, celdas o notas que no estén visibles en
  la página. Si una celda es ilegible, se registra como
  `normalized_outcome: "unclear"` y no se utiliza en decisiones
  deterministas.
* Asignar `normalized_outcome` fuera de la enumeración cerrada
  (`A_full`, `B_full`, `shared_50_50`, `shared_by_maneuver`,
  `no_convention`, `exception`, `unclear`).
* Producir un artefacto sin attestation firmada por al menos un
  responsable.

## 3. Artefactos y paths

| Artefacto | Path | Esquema |
| --- | --- | --- |
| Matriz 18×18 transcrita | `data/rules/cide-matrix.v1.json` | `data/rules/cide-matrix.schema.json` |
| Reglas de convenio | `data/rules/ruleset.v1.json` | `data/rules/ruleset.schema.json` |
| Notas de calibración | `data/rules/calibration.md` | texto libre |

Los archivos solo se crean cuando al menos dos transcripciones
independientes coinciden o cuando las divergencias quedan resueltas
contra el PDF y registradas en `attestation.divergence_resolution`.

## 4. Flujo de transcripción

1. **Preparación**: dos revisores reciben una copia del PDF original
   (página 101) sin anotaciones. Cada uno abre la página en una
   herramienta que permita verificar coordenadas físicas.
2. **Transcripción ciega**: cada revisor rellena
   `cells[(a, b)]`, `row_labels`, `column_labels` y `notes`, marcando
   ilegibles como `"unclear"`. No comparte su transcripción con el
   otro hasta terminar.
3. **Confrontación**: las dos transcripciones se comparan
   automáticamente (ver CLI `rules compare-transcriptions`). Las
   divergencias se listan con su clave `(a, b)` y el texto que cada
   uno escribió.
4. **Resolución contra el PDF**: para cada divergencia, ambos
   revisores vuelven a abrir la página y registran la lectura final
   junto con la captura o coordenada. La resolución se documenta en
   `attestation.divergence_resolution`.
5. **Adjudicación**: cuando ambas transcripciones convergen o todas
   las divergencias están resueltas, se calcula el SHA-256 de cada
   transcripción cruda y se añade a `attestation.transcriptions`.
6. **Firma**: al menos un responsable firma el artefacto con su
   identificador (`attestation.signed_by`) y fecha.

## 5. Verificación automática

`allianz rules validate` realiza las siguientes comprobaciones y se
niega a aceptar el artefacto si fallan:

* El documento JSON cumple el esquema (`cide-matrix.schema.json`).
* Contiene exactamente 324 claves en `cells` con `a ∈ [1,18]` y
  `b ∈ [1,18]`, cubriendo todas las posiciones únicas.
* `orientation` queda declarado y todas las celdas usan la misma
  convención.
* Cada celda cita al menos un `evidence_id` con el patrón
  `sha256:<hash>:page:<n>` que exista en la publicación verificada.
* `reviewer_ids` incluye al menos dos identificadores.
* `attestation.transcriptions` contiene al menos dos entradas con
  `independent = true` y `pdf_page_checked = true`.
* `attestation.divergence_resolution` no está vacío y
  `signed_by` no está vacío.

`allianz rules validate-ruleset` aplica las mismas comprobaciones al
`ruleset.v1.json`.

`allianz rules compare-transcriptions FILE_A FILE_B` imprime las
divergencias entre dos transcripciones sin firmar, sin tocar el
artefacto canónico.

## 6. Uso en tiempo de ejecución

* `domain.rules.cide_matrix.lookup_matrix` solo lee celdas cuyo
  `evidence_id` figure en la publicación cargada por el caso de uso.
  Una celda `unclear` se devuelve como `MatrixLookup(status="undetermined")`.
* `domain.rules.applicability.assess_applicability` aplica únicamente
  las reglas de aplicabilidad del artefacto; cualquier cambio a las
  reglas exige un nuevo freeze.
* Las excepciones explícitas documentadas en el manual se modelan
  como reglas con `kind = "exception"` y se evalúan después de la
  aplicabilidad y antes del lookup.

## 7. Lo que viene después

* Una vez firmadas las dos primeras versiones, las modificaciones
  generan nuevas versiones (`cide-matrix.v2.json`) con attestation
  renovada. Las reglas nunca se editan en su sitio.
* La calibración de jueces automáticos (Ragas + humanos) consume
  estos artefactos como verdad documental.
* El plan de cierre (T15) abre el holdout una sola vez después de
  congelar `cide-matrix.v1.json` y `ruleset.v1.json` y de medir el
  acuerdo del extractor con los revisores humanos.
