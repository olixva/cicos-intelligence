# Generador de la presentación de entrega

`docs/entrega/presentacion.pptx` no se edita a mano: se genera desde aquí. El motivo es el
mismo que atraviesa el proyecto — que la lámina y la cifra que enseña salgan del mismo sitio
y se puedan volver a producir.

```bash
cd docs/entrega/deck
npm install          # sólo la primera vez (pptxgenjs)
npm run build        # escribe ../presentacion.pptx y ../guion-orador.md
```

## Qué hay aquí

| Fichero | Papel |
|---|---|
| `build.mjs` | Orquesta las láminas y escribe el `.pptx` y el guion de orador en markdown. |
| `lib.mjs` | Sistema de diseño: retícula, paleta, tipografía y componentes. No conoce el contenido. |
| `slides-apertura.mjs` | Portada y agenda. |
| `slides-problema.mjs` | Bloques 01 (el problema) y 02 (plan, supuestos, riesgos y decisiones). |
| `slides-arquitectura.mjs` | Bloque 03 completo. |
| `slides-evaluacion.mjs` | Bloques 04 (demo), 05 (evaluación y límites) y el apéndice. |
| `assets/` | Logo y las capturas reales del producto que usan las láminas 17 y 19. |

## Reglas del diseño

- **Título de acción**: el título de cada lámina es la conclusión, no el tema. Leídos en
  orden cuentan el argumento entero.
- **Una banda inferior por lámina** con el «y por tanto», nunca decorativa.
- Motivo repetido: tarjetas con sombra suave, chips numerados y píldoras monoespaciadas de
  evidencia. **Sin franjas ni líneas de acento** bajo los títulos o en los bordes.
- Tipografía: Arial para titulares, Calibri para texto, Courier New para identificadores y
  comandos. Los tres se renderizan igual en cualquier PowerPoint.
- La banda inferior nunca baja de `y = 6.94"`, para no pisar el número de lámina.

## Regenerar las capturas del producto

Las capturas de `assets/ui-*.png` se tomaron con Playwright contra la aplicación en marcha
(`make serve-backend` + `make serve-frontend`). El script vive fuera del repositorio porque
hace llamadas reales al modelo; si hay que rehacerlas, basta con capturar a 1480 px de ancho
y `deviceScaleFactor: 2`, en tema oscuro, y conservar los mismos nombres de fichero.

## Comprobación antes de dar por buena una versión

```bash
npm run build
# validación de esquema y relaciones del OOXML (script de la skill de pptx)
python scripts/office/validate.py ../presentacion.pptx
# revisión visual: exportar a PDF y mirar las láminas una a una
soffice --headless --convert-to pdf ../presentacion.pptx
```
