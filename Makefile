.PHONY: install lint format test type-check build clean help

install: ## Install dependencies
	uv sync --all-extras

lint: ## Run linting
	uv run ruff check .

format: ## Run formatting
	uv run ruff format .

type-check: ## Run type checking
	uv run mypy src/remora_fin tests

test: ## Run tests
	uv run pytest tests/ -v --cov=remora_fin --cov-report=xml

build: ## Build the package
	uv build

clean: ## Clean build artifacts
	if exist dist (rmdir /s /q dist)
	if exist .mypy_cache (rmdir /s /q .mypy_cache)
	if exist .pytest_cache (rmdir /s /q .pytest_cache)
	if exist .ruff_cache (rmdir /s /q .ruff_cache)
	if exist .uv_cache (rmdir /s /q .uv_cache)

help: ## Show this help message
	@powershell -ExecutionPolicy Bypass -Command "Get-Content Makefile | Select-String '^[a-zA-Z_-]+:.*?## .*$$' | ForEach-Object { if ($$_ -match '^(?<name>[a-zA-Z_-]+):.*?## (?<desc>.*)$$') { Write-Host ([char]27 + '[36m' + $$Matches.name.PadRight(20) + [char]27 + '[0m ' + $$Matches.desc) } }"
