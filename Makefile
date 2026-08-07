PY ?= python3
UV ?= uv

.DEFAULT_GOAL := help
.PHONY: help setup check docs docs-check lint test

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create the venv and install dev tooling
	$(UV) sync

check: docs-check lint test ## Everything CI runs. The gate for every phase and every PR.

docs: ## Regenerate the docs index tables
	$(PY) scripts/docs_index.py

docs-check: ## Fail if an index table is stale or a docs rule is broken
	$(PY) scripts/docs_index.py --check

lint: ## Lint and format-check
	$(UV) run ruff check .
	$(UV) run ruff format --check .

test: ## Run tests
	$(UV) run pytest -q
