.PHONY: check-backend local-services-config local-services-up local-services-stop doctor

ALLIANZ_DOCKER_CONTEXT ?= colima-allianz
LOCAL_COMPOSE = docker --context $(ALLIANZ_DOCKER_CONTEXT) compose --env-file ops/local.env

check-backend:
	uv run --project backend --group ingestion ruff check backend
	uv run --project backend --group ingestion ruff format --check backend
	uv run --project backend --group ingestion pyright --project backend
	uv run --project backend --group ingestion pytest backend/tests

local-services-config:
	$(LOCAL_COMPOSE) config --quiet

local-services-up:
	$(LOCAL_COMPOSE) up -d

local-services-stop:
	$(LOCAL_COMPOSE) stop

doctor:
	ALLIANZ_DOCKER_CONTEXT=$(ALLIANZ_DOCKER_CONTEXT) uv run --project backend allianz doctor
