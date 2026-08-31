.PHONY: check-backend

check-backend:
	uv run --project backend --group ingestion ruff check backend
	uv run --project backend --group ingestion ruff format --check backend
	uv run --project backend --group ingestion pyright --project backend
	uv run --project backend --group ingestion pytest backend/tests
