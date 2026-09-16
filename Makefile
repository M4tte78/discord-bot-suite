.PHONY: install test lint fmt sim bot clean

install:
	python -m pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff check --fix .
	ruff format .

sim:
	python -m botsuite.sim all

bot:
	python -m botsuite.adapters.discord_adapter.bot

clean:
	rm -rf .pytest_cache .ruff_cache **/__pycache__ *.sqlite3
