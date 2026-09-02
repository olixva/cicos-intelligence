# Baseline ingestion review

The approved source `data/raw/Manual-cide-ascide-y-cicos.pdf` was ingested
with `pypdf-6.16.2` on 2026-08-31. Its SHA-256 is
`b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`; the published
artifact contains all 111 physical PDF pages.

This is a text-only baseline. It keeps the original page number and any text `pypdf`
can expose, but stores no image, coordinates, printed label, or inferred table cells.

- PDF page 32 is a scanned *Declaración amistosa de accidente* form. The baseline only
  captures its printed page number (`33`); all form fields, checkboxes, diagram, colors,
  and placement are absent from the text evidence.
- PDF page 101 contains the CIDE culpability matrix. The row and column labels and cell
  values are present as linear text, but the grid geometry and unambiguous row/column
  associations are not preserved. It must not be treated as a structured extracted
  matrix.

Future OCR and layout/table extraction can add evidence versions under their own parser
identities; they must not overwrite this `pypdf-6.16.2` baseline.
