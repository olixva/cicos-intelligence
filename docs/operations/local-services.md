# Servicios locales: Qdrant y Langfuse

El entorno de desarrollo es local y usa el proyecto Docker `allianz-rag` en el contexto
`colima-allianz`. Sus únicos puertos publicados se enlazan a `127.0.0.1`:

| Servicio | Dirección | Uso |
| --- | --- | --- |
| Langfuse | `http://127.0.0.1:3000` | Datasets, trazas y experimentos |
| Qdrant | `http://127.0.0.1:6333` | Índices y consultas de recuperación |
| MinIO | `http://127.0.0.1:9090` | Almacenamiento interno de Langfuse |

Los servicios dependientes (PostgreSQL, ClickHouse y Redis) no se publican en el host. Las
imágenes se fijan por digest en [compose.yaml](../../compose.yaml); el snapshot oficial de Langfuse,
su commit y su checksum están en [SOURCE.md](../../ops/langfuse/SOURCE.md).

## Preparación y operación

Se necesita Docker/Colima y el contexto `colima-allianz`. Crea el archivo privado una sola vez:

```bash
cp ops/local.env.example ops/local.env
chmod 600 ops/local.env
```

Rellena exclusivamente valores locales en `ops/local.env`. El archivo está ignorado por Git; no se
debe copiar desde una instalación de producción ni pegar sus valores en una incidencia o consola
compartida. En este worktree ya existe un archivo local compatible con los volúmenes del proyecto.

```bash
make local-services-config
make local-services-up
make doctor
```

`make doctor` comprueba el motor seleccionado, `Qdrant /readyz` y `Langfuse /api/public/health`
con timeout. No envía peticiones a proveedores de IA y solo informa de la presencia de credenciales,
nunca de sus valores. Operaciones concretas permiten una comprobación más precisa:

```bash
uv run --project backend allianz doctor --operation retrieval
uv run --project backend allianz doctor --operation evaluation
uv run --project backend allianz doctor --operation generation
```

La comprobación `generation` requiere que `OPENAI_API_KEY` exista en el proceso; no valida la clave
ni hace llamadas de pago. La comprobación `evaluation` requiere salud de Langfuse y presencia de
`LANGFUSE_PUBLIC_KEY` y `LANGFUSE_SECRET_KEY` en el proceso. Para parar servicios sin eliminar datos:

```bash
make local-services-stop
```

No uses `docker compose down -v`: los volúmenes persistentes contienen el estado local de Langfuse,
Qdrant y sus dependencias.

## Compatibilidad validada

La configuración se validó con Docker Compose 5.5.0 y el daemon del contexto local. Un reinicio de
Qdrant conservó la colección técnica `compatibility_smoke_v1`. Durante el cierre/arranque, una
petición HTTP puede recibir una respuesta vacía; el `doctor` debe consultarse una vez que `/readyz`
responda 200.

El smoke nativo de Qdrant 1.19.0 creó/actualizó tres puntos técnicos con vectores densos y BM25
español, y la fusión RRF devolvió los IDs `[1, 2, 3]`. El smoke nativo de Langfuse SDK 4.15.1 sobre
el servidor 4.26.0 usó un dataset técnico plano de dos items y `DatasetClient.run_experiment`: el
run correcto obtuvo `[1.0, 1.0]` y el run deliberadamente erróneo `[0.0, 0.0]`. Los dos aparecieron
después en las APIs v4 de experimentos. No se usó el golden set, OpenAI ni ningún proveedor de pago.

Langfuse v4 en modo `events_only` no expone el endpoint legacy de dataset runs. Las tareas de
evaluación deben usar `DatasetClient.run_experiment` y las APIs de Experiments, ExperimentItems y
Scores; no deben crear un runner alternativo ni usar `dataset-runs` o `dataset-run-items` legacy.

Ragas 0.4.3 necesita `langchain-community==0.4.1` en este entorno: 0.4.2 retiró el módulo
`vertexai` que Ragas importa. Esta compatibilidad está bloqueada en el extra `local-rag` del backend.

En reposo, los servicios locales observados ocupan aproximadamente 2,5–3 GiB combinados. La ingesta
Docling puede llegar a unos 3,40 GiB de RSS adicionales, por lo que no conviene ejecutarla junto con
una carga pesada de evaluación en un equipo de memoria limitada.
