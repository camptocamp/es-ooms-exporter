all: build

.venv/timestamp: requirements.txt Makefile Pipfile
	/usr/bin/python3 -m virtualenv .venv
	.venv/bin/pip install --upgrade -r requirements.txt
	.venv/bin/pipenv install --dev
	touch $@

.venv/bin/c2cciutils-checks: ci/requirements.txt
	.venv/bin/pip install --upgrade -r ci/requirements.txt
	touch $@

.PHONY: tests
tests: .venv/timestamp
	.venv/bin/pytest

.PHONY: fix
fix: .venv/bin/c2cciutils-checks
	(source .venv/bin/activate; c2cciutils-checks --fix --check black)
	(source .venv/bin/activate; c2cciutils-checks --fix --check isort)

.PHONY: build
build:
	docker build --tag camptocamp/es-ooms-exporter:latest .
