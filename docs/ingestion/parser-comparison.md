# Parser comparison and structured evidence review

## Reproducible configuration

The structured adapter uses Docling 2.124.0 with `PyPdfiumDocumentBackend`, RapidOCR 3.9.2
(`latin`, Torch CPU), and independent pypdfium2 5.13.0 rendering at 2x PDF scale (144 dpi).
Its effective options, dependency versions, exact upstream model revisions, and hashes of all nine
effective model files are stored in `configuration.json` and hashed into the parser identity. The
reviewed bundle digest is
`135374b2b3918a3d1bad9dcb295901e24df0928753782cae69a3fa78d25377e1`.

The bundle fixes layout revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`, table-model
revision `fc0f2d45e2218ea24bce5045f58a389aed16dc23`, and the RapidOCR 3.9.2 release files.
`allianz prepare-ingestion-models` is the only path allowed to download them. It verifies the
declared hashes before atomically publishing the 390 MB bundle. Ordinary ingestion requires and
revalidates this local bundle, supplies every path explicitly to Docling/RapidOCR, and performs no
implicit model download. Absolute local paths are replaced by stable bundle roles in the parser
fingerprint.

Docling receives a byte stream derived from the immutable source snapshot. For PDFs with a crop
offset or `/Rotate`, a layout-only copy first moves the visible crop to a zero origin and bakes the
rotation. This compensates for the installed PDFium backend returning native text boxes without
subtracting crop offsets. `original.pdf` always retains the exact input bytes. Every page image is
rendered independently from those original bytes, so neural layout output cannot replace visual
evidence.

## Inventory on the Allianz manual

The reviewed source has SHA-256
`b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344` and 111 physical pages.
Both pypdf and Docling retain all 111 page IDs. The observed inventories were:

| Measure | pypdf baseline | Docling/PDFium |
| --- | ---: | ---: |
| Physical page records | 111 | 111 |
| Records with non-whitespace text | 111 | 111 |
| Extracted text characters | 117,789 | 130,975 |
| Source elements | none | 849 |
| Table elements | none | 11 on pages 45, 65, 68, 80, 101–107 |
| Furniture elements | not represented | 105 |
| Pages below 80 text characters | not classified | 31, 32, 54, 93 |

The Docling element inventory contains 423 text blocks, 164 section headers, 140 list items,
105 page footers, 11 tables, 3 pictures, 2 document-index blocks, and 1 footnote. These labels and
regions are parser evidence, not verified insurance rules.

## Fidelity findings

PDF page 32 is a scanned friendly-accident form. The baseline exposes only its printed footer
(`33`). Docling adds the heading `DECLARACION AMISTOSA DE ACCIDENTE` and a picture region, but it
does not recover the form fields or circumstances. The extraction therefore declares both a
low-text/OCR warning and a picture-content warning and retains the full original render for review.

PDF page 101 is the continuation of the CIDE culpability matrix. Docling identifies a table and
retains the four observation footnotes, but its Markdown has an extra unlabeled column, displaced A
row labels, and merged/mis-grouped cells around the B16/B17 area. The pypdf baseline preserves a
more linear row/column text sequence but has no grid geometry. Neither representation is published
as a verified matrix or domain rule. The page carries an explicit unverified-table warning.

Independent 2x renders were visually compared with the supplied originals. The adapter produced
1190×1684 PNGs and the supplied renders were 1202×1700; both page 32 form content and page 101
matrix/footnotes were complete and aligned. The small size difference reflects the render scale,
not missing page content.

## Published artifact and trust boundary

A complete structured publication contains `original.pdf`, one PNG per physical page,
`document.json`, `document.md`, `diagnostics.json`, `configuration.json`, `manifest.json`,
`pages.jsonl`, `extraction.json`, and `publication.json`. A normalized `layout-input.pdf` is added only when crop or
rotation normalization is required. Asset paths must be unique, relative, and non-overlapping.
The publication root records SHA-256 and size for every metadata and binary file; reads validate it
before decoding page evidence, reject symlinks before reading through them, reject unlisted files,
and verify that `original.pdf` matches the manifest hash. The persisted source filename is a
content-derived canonical name, so aliases with identical bytes share one immutable publication.
Publication occurs by a same-filesystem rename only after the complete staged directory validates.

On the reviewed macOS host, the locked Python environment occupied 1.2 GB, the model bundle 390 MB,
and the 111-page integration reached 3,648,962,560 bytes maximum RSS (about 3.40 GiB). These are
local engineering measurements rather than portable resource guarantees.

Docling and RapidOCR currently emit two upstream deprecation warnings during conversion. They do
not alter the reviewed output, but should be reassessed when upgrading the pinned ingestion group.
