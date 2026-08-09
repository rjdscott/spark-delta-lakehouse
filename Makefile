PY ?= python3
UV ?= uv

.DEFAULT_GOAL := help
.PHONY: help setup check docs docs-check lint test generate stack-up stack-down stack-destroy stack-ps stack-logs stack-smoke stack-shell seed bronze silver party gold demo demo-queries demo-reset

COMPOSE = docker compose -f docker/compose.yaml --env-file docker/.env
include docker/.env
export

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

generate: ## Generate the seeded source CSVs into data/raw
	$(UV) run python -m lakehouse.generate --out data/raw

stack-up: ## Build and start the lakehouse stack
	$(COMPOSE) up -d --build
	@echo "MinIO console http://localhost:9001 | Spark master http://localhost:8090 | Unity Catalog http://localhost:8080"

stack-down: ## Stop the stack, keep the data volumes
	$(COMPOSE) down

stack-destroy: ## Stop the stack and delete the data volumes
	$(COMPOSE) down -v

stack-ps: ## Show service status
	$(COMPOSE) ps

stack-logs: ## Tail logs for all services
	$(COMPOSE) logs -f --tail=50

stack-smoke: ## Prove cluster + catalog + MinIO + Delta end to end
	$(COMPOSE) exec -T app /opt/spark/bin/spark-submit \
		--master spark://spark-master:7077 scripts/smoke_stack.py

seed: ## Upload the generated CSVs to the MinIO landing zone
	docker run --rm --network lakehouse_default -v $(PWD)/data/raw:/raw:ro \
		--entrypoint sh minio/mc:RELEASE.2024-11-21T17-21-54Z -c \
		"mc alias set l http://minio:9000 lakehouse lakehouse123 >/dev/null && \
		 mc mirror --overwrite /raw l/lakehouse/landing && mc ls -r l/lakehouse/landing | head -3"

bronze: ## Load all three batches into bronze on the cluster
	@for b in 2026-01-15 2026-02-15 2026-03-15; do \
		$(COMPOSE) exec -T app /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
			scripts/run_bronze.py --batch $$b || exit 1; \
	done

silver: ## Advance silver through all three batches, in order
	@for b in 2026-01-15 2026-02-15 2026-03-15; do \
		$(COMPOSE) exec -T app /opt/spark/bin/spark-submit \
			--master spark://spark-master:7077 scripts/run_silver.py --batch $$b || exit 1; \
	done

party: ## Build the SCD2 party dimension through all three batches
	@for b in 2026-01-15 2026-02-15 2026-03-15; do \
		$(COMPOSE) exec -T app /opt/spark/bin/spark-submit \
			--master spark://spark-master:7077 scripts/run_scd2.py --batch $$b || exit 1; \
	done

gold: ## Build the gold dimensions and facts
	$(COMPOSE) exec -T app /opt/spark/bin/spark-submit \
		--master spark://spark-master:7077 scripts/run_gold.py

demo: ## Walk the whole lakehouse one batch at a time, narrating
	$(COMPOSE) exec -T app /opt/spark/bin/spark-submit \
		--master spark://spark-master:7077 scripts/demo.py

demo-queries: ## Answer business questions against the star schema
	$(COMPOSE) exec -T app /opt/spark/bin/spark-submit \
		--master spark://spark-master:7077 scripts/demo_queries.py

demo-reset: ## Drop every table and object so the demo runs from cold
	$(COMPOSE) exec -T app /opt/spark/bin/spark-submit \
		--master spark://spark-master:7077 scripts/reset.py
	docker run --rm --network lakehouse_default --entrypoint sh $(MINIO_MC_IMAGE) -c \
		"mc alias set l http://minio:9000 $(MINIO_ROOT_USER) $(MINIO_ROOT_PASSWORD) >/dev/null && \
		 mc rm -r --force l/$(LAKEHOUSE_BUCKET)/bronze l/$(LAKEHOUSE_BUCKET)/silver l/$(LAKEHOUSE_BUCKET)/gold || true"

stack-shell: ## Open a shell on the driver container
	$(COMPOSE) exec app bash
