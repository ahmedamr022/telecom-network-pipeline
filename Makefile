.PHONY: help install run test benchmark dashboard docker-up docker-down clean

PYTHON := python
VENV_PYTHON := .venv/bin/python
ifeq ($(OS),Windows_NT)
    VENV_PYTHON := .venv\Scripts\python.exe
endif

help:
	@echo "Available commands:"
	@echo "  make install     - Set up virtual environment and install dependencies"
	@echo "  make run         - Execute the full ETL and Analytics pipeline"
	@echo "  make test        - Run automated Pytest test suite"
	@echo "  make benchmark   - Run hardware performance benchmark"
	@echo "  make dashboard   - Launch Streamlit NOC Operations Console"
	@echo "  make docker-up   - Start PostgreSQL/TimescaleDB, Grafana & Pipeline"
	@echo "  make docker-down - Stop Docker Compose stack"
	@echo "  make clean       - Remove cached files, temporary DuckDB, and logs"

install:
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt

run:
	$(VENV_PYTHON) scripts/run_pipeline.py --periods 24

test:
	$(VENV_PYTHON) -m pytest tests -v

benchmark:
	$(VENV_PYTHON) scripts/benchmark.py

dashboard:
	$(VENV_PYTHON) -m streamlit run dashboards/app.py

docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down -v

clean:
	rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache
	rm -rf data/bronze/* data/silver/* data/gold/* data/dlq/* data/*.duckdb
