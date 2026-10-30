.PHONY: help init-db seed run test cov reconcile report benchmark clean

help:
	@echo "Available commands:"
	@echo "  make init-db       - Initialize the SQLite database"
	@echo "  make generate      - Generate sample data (default 100 rows)"
	@echo "  make run           - Run pipeline on sample data"
	@echo "  make test          - Run automated tests"
	@echo "  make cov           - Run test coverage"
	@echo "  make reconcile     - Run metrics reconciliation"
	@echo "  make report        - Generate reports"
	@echo "  make benchmark     - Run performance benchmark (100000 rows)"
	@echo "  make clean         - Clean up temporary files"

init-db:
	python -m src.main init-db

generate:
	python -m src.main generate --rows 100 --seed 42

run:
	python -m src.main run --input data/sample/valid/events.csv

test:
	pytest -v

cov:
	pytest --cov=src --cov-report=term-missing

reconcile:
	python -m src.main reconcile

report:
	python -m src.main report

benchmark:
	python -m src.main benchmark --rows 100000

clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov *.db *.sqlite
