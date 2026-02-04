.PHONY: help install dev test lint format check docker-build docker-up docker-down clean hopp hopp-existing

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -r requirements.txt

dev: ## Install development dependencies
	pip install -e ".[dev]"

test: ## Run tests
	pytest -v

test-cov: ## Run tests with coverage
	pytest --cov=harborline --cov-report=term-missing --cov-report=html

lint: ## Run linter (ruff)
	ruff check harborline tests

format: ## Format code with ruff
	ruff format harborline tests
	ruff check --fix harborline tests

check: lint test ## Run lint and tests

type: ## Run type checker (mypy)
	mypy harborline

docker-build: ## Build Docker image
	docker build -t harborline-api .

docker-up: ## Start all services with docker-compose
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-logs: ## View docker-compose logs
	docker compose logs -f

run: ## Run the API locally
	uvicorn harborline.main:app --reload --host 0.0.0.0 --port 8000

hopp: ## Run Hoppscotch CLI collection (spins up temporary API)
	./scripts/run_hoppscotch_cli.sh

hopp-existing: ## Run Hoppscotch CLI collection against an already running API
	USE_EXISTING_SERVER=1 PORT=8000 ./scripts/run_hoppscotch_cli.sh

clean: ## Clean up cache files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
