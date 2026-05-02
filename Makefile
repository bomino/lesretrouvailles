.PHONY: dev test migrate css css-watch lint format check db-up db-down

dev:
	python manage.py runserver

test:
	pytest -v

migrate:
	python manage.py migrate

css:
	npm run css:build

css-watch:
	npm run css:watch

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

check:
	python manage.py check
	python manage.py makemigrations --dry-run --check

db-up:
	docker compose up -d db

db-down:
	docker compose down
