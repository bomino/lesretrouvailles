.PHONY: dev test migrate css css-watch lint format check db-up db-down seed docker-build docker-run docker-down playwright-install seed-handbook handbook

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

docker-run:
	docker compose up -d --build
	@echo "Staging-shaped app at http://localhost:8000 (basic-auth: admin / compose-test-pw)"

docker-down:
	docker compose down

# Handbook pipeline (illustrated user guide via Playwright).
# One-time browser install. Adds ~150 MB of Chromium binaries to the venv.
playwright-install:
	pip install -e ".[handbook]"
	python -m playwright install chromium

# Build the deterministic dataset that handbook flow scripts drive against.
# Idempotent. Run after `make migrate` against an empty or seeded local DB.
seed-handbook:
	python manage.py seed_handbook_demo --reset

# Boot a runserver, run all flow scripts, capture screenshots, build handbook.html + handbook.pdf.
# Requires `playwright-install` to have been run once. The server is started/stopped by assemble.py.
handbook:
	python docs/handbook/assemble.py
