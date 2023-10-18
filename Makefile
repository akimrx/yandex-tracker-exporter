.PHONY: clean clean-build clean-pyc dist help clickhouse test tests migration docs
.DEFAULT_GOAL := help

help:
	@echo "🪄  PREPARE ENVIRONMENT"
	@echo "---------------------------------------------------------------------"
	@echo "  init                Install all python requirements"
	@echo "  pre-commit          Install pre-commit hooks"
	@echo ""
	@echo "👀  CHECK"
	@echo "---------------------------------------------------------------------"
	@echo "  test                Run tests (pytest)"
	@echo "  test-no-cov         Run tests (pytest) without coverage report"
	@echo "  pylint              Check python syntax & style by pylint"
	@echo "  lint                Check python syntax via Flake8"
	@echo "  black               Check python syntax & style by black"
	@echo "  black-apply         Apply black linter (autoformat)"
	@echo "  sec                 Security linter (bandit)"
	@echo ""
	@echo "🛠  INSTALL & RELEASE"
	@echo "---------------------------------------------------------------------"
	@echo "  install             Install library to site-packages"
	@echo "  build               Build package"
	@echo "  build-docker        Build docker image"
	@echo "  release             Build & push package to PyPI"
	@echo "  clean               Clean build/install artifacts"
	@echo ""
	@echo "🐳  DEV & RUN"
	@echo "---------------------------------------------------------------------"
	@echo "  up                  Up docker composition with app & clickhouse"
	@echo "  up-clickhouse       Up docker clickhouse"
	@echo "  down                Down docker composition (full)"
	@echo "  down-clickhouse     Down docker clickhouse"
	@echo "  clickhouse          Clickhouse CLI"
	@echo "  migration           Run clickhouse migration"
	@echo "  run                 Run ETL"

clean: clean-build clean-pyc

clean-build:
	rm -rf build/
	rm -rf dist/
	rm -rf .eggs/
	find . -name '*.egg-info' -exec rm -rf {} +
	find . -name '*.egg' -exec rm -rf {} +
	find . -name '.DS_Store' -exec rm -f {} +

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -rf {} +

test:
	@pytest -vv --cov=tracker_exporter

tests: test

test-no-cov:
	@pytest -v

lint:
	@flake8 --config=setup.cfg --max-line=119

pylint:
	@pylint --max-line-length=120 --rcfile=setup.cfg tracker_exporter

black:
	@black tracker_exporter/* --color --diff --check

black-apply:
	@black tracker_exporter/*

sec:
	@bandit -r tracker_exporter

build:
	@python3 setup.py sdist bdist_wheel

build-docker:
	@docker build . -t tracker_exporter:dev

release: clean build
	@make clean
	@make build
	@python3 -m twine upload --repository pypi dist/*
	@make clean

install: clean
	@python3 setup.py install

init:
	@pip3 install -r requirements.txt
	@pip3 install -r requirements-dev.txt

up:
	@docker compose -f docker-compose.dev.yml up -d

up-clickhouse:
	@docker compose -f docker-compose.dev.yml up -d clickhouse

down:
	@docker compose -f docker-compose.dev.yml down

down-clickhouse:
	@docker compose -f docker-compose.dev.yml down clickhouse

clickhouse:
	@docker exec -it clickhouse clickhouse-client

run:
	@tracker-exporter --env-file .env

migration:
	@./data-migrate.sh
