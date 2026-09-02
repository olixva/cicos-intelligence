.PHONY: check-backend check-frontend check-openapi local-services-config local-services-up local-services-stop doctor serve-backend serve-frontend

ALLIANZ_DOCKER_CONTEXT ?= colima-allianz
LOCAL_COMPOSE = docker --context $(ALLIANZ_DOCKER_CONTEXT) compose --env-file ops/local.env
PNPM ?= npm exec --yes pnpm@9.12.0 --

check-backend:
	uv run --project backend --group ingestion --extra local-rag ruff check backend
	uv run --project backend --group ingestion --extra local-rag ruff format --check backend
	uv run --project backend --group ingestion --extra local-rag pyright --project backend
	uv run --project backend --group ingestion --extra local-rag pytest backend/tests

check-frontend:
	$(PNPM) --dir frontend lint
	$(PNPM) --dir frontend typecheck
	$(PNPM) --dir frontend test
	$(PNPM) --dir frontend build

check-openapi:
	uv run --project backend python backend/scripts/check_openapi.py
	$(PNPM) --dir frontend openapi:check

local-services-config:
	$(LOCAL_COMPOSE) config --quiet

local-services-up:
	$(LOCAL_COMPOSE) up -d

local-services-stop:
	$(LOCAL_COMPOSE) stop

doctor:
	ALLIANZ_DOCKER_CONTEXT=$(ALLIANZ_DOCKER_CONTEXT) uv run --project backend allianz doctor

serve-backend:
	uv run --project backend uvicorn bootstrap:build_api --factory --host 127.0.0.1 --port 8000

serve-frontend:
	$(PNPM) --dir frontend dev
