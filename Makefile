.PHONY: install run test sample docker docs

install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt

run:
	SEED_DEMO_DATA=true uvicorn app.main:app --reload --port 8000

test:
	python -m pytest tests -q

sample:
	python scripts/generate_sample_data.py

docker:
	docker compose up --build

docs:
	python scripts/export_openapi.py
