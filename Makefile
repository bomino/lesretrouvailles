.PHONY: dev test migrate css css-watch lint format check db-up db-down seed docker-build docker-run docker-down

dev:
	python manage.py runserver

test: css
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

seed:
	python manage.py loaddata seed_members

docker-build:
	docker build -t retrouvailles:local .

docker-run: docker-build
	docker compose up -d
	@echo "Staging-shaped app at http://localhost:8000 (basic-auth: admin / compose-test-pw)"

docker-down:
	docker compose down
