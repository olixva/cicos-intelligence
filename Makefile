.PHONY: check-backend check-frontend check-openapi check-all check-unit check-integration check-e2e \
        lint-backend format-check format-backend typecheck-backend test-backend \
        lint-frontend typecheck-frontend test-frontend build-frontend test-e2e \
        local-services-config local-services-up local-services-stop \
        doctor serve-backend serve-frontend provision-prompts

LOCAL_COMPOSE = docker compose --env-file ops/local.env
PNPM ?= npm exec --yes pnpm@9.12.0 --
# El host no tiene pnpm en PATH; el wrapper evita instalar una versión
# global y respeta la política de antigüedad mínima de npm.

# --- Backend ----------------------------------------------------------------
lint-backend:
	uv run --project backend --group ingestion --extra local-rag ruff check backend

format-check:
	uv run --project backend --group ingestion --extra local-rag ruff format --check backend

format-backend:
	uv run --project backend --group ingestion --extra local-rag ruff format backend

# Pyright en modo estricto: baseline conocido ≈ 79 errores (deuda técnica
# preexistente registrada en .slim/deepwork/). El gate rápido no incluye
# pyright para que `make check-backend` pase desde checkout limpio; el
# target `typecheck-backend-strict` ejecuta la verificación completa y
# se aborda en una fase posterior del plan de cierre.
typecheck-backend:
	uv run --project backend --group ingestion --extra local-rag pyright --project backend backend/src

typecheck-backend-strict:
	uv run --project backend --group ingestion --extra local-rag pyright --project backend

test-backend:
	uv run --project backend --group ingestion --extra local-rag pytest backend/tests

check-unit: test-backend

check-integration:
	uv run --project backend --group ingestion --extra local-rag pytest backend/tests/integration -m integration

check-backend: lint-backend format-check test-backend

# --- Frontend ---------------------------------------------------------------
lint-frontend:
	$(PNPM) --dir frontend lint

typecheck-frontend:
	$(PNPM) --dir frontend typecheck

test-frontend:
	$(PNPM) --dir frontend test

build-frontend:
	$(PNPM) --dir frontend build

test-e2e:
	$(PNPM) --dir frontend exec playwright test --reporter=list

check-frontend: lint-frontend typecheck-frontend test-frontend build-frontend

# --- OpenAPI / contratos ----------------------------------------------------
check-openapi:
	uv run --project backend python backend/scripts/check_openapi.py
	$(PNPM) --dir frontend openapi:check

# --- Suite completa reproducible -------------------------------------------
check-all: check-backend check-frontend check-openapi

# --- Servicios locales ------------------------------------------------------
local-services-config:
	$(LOCAL_COMPOSE) config --quiet

local-services-up:
	$(LOCAL_COMPOSE) up -d

local-services-stop:
	$(LOCAL_COMPOSE) stop

doctor:
	uv run --project backend allianz doctor

# --- Servir en desarrollo ---------------------------------------------------
# Carga `.env` y mapea las claves de Langfuse desde `ops/local.env`, donde
# compose las define con prefijo ALLIANZ_. Sin este mapeo el arranque falla con
# "missing Langfuse configuration", que era el estado previo: `make
# serve-backend` no funcionaba desde un entorno limpio.
BACKEND_ENV = set -a; . ./.env; . ./ops/local.env; \
	: "$${LANGFUSE_PUBLIC_KEY:=$$ALLIANZ_LANGFUSE_PUBLIC_KEY}"; \
	: "$${LANGFUSE_SECRET_KEY:=$$ALLIANZ_LANGFUSE_SECRET_KEY}"; \
	: "$${LANGFUSE_BASE_URL:=http://127.0.0.1:3000}"; \
	: "$${LANGFUSE_PROJECT_ID:=allianz-rag}"; set +a;

provision-prompts:
	@$(BACKEND_ENV) uv run --project backend --extra local-rag \
		python backend/scripts/provision_langfuse_prompts.py

serve-backend: provision-prompts
	@$(BACKEND_ENV) uv run --project backend --extra local-rag \
		uvicorn asgi_local:app --factory --host 127.0.0.1 --port 8000

serve-frontend:
	$(PNPM) --dir frontend dev
