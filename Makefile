.PHONY: check-backend

check-backend:
	uv run --project backend ruff check backend
	uv run --project backend ruff format --check backend
	uv run --project backend pyright --project backend
	uv run --project backend pytest backend/tests
