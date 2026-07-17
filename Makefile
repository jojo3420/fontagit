.PHONY: web-dev collect test lint deploy

web-dev:
	pnpm --filter web dev

collect:
	cd apps/pipeline && uv run python -m fontagit_pipeline

test:
	cd apps/pipeline && uv run pytest

lint:
	cd apps/pipeline && uv run ruff check . && uv run mypy src

deploy:
	./scripts/deploy.sh
