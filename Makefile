export DOCKER_BUILDKIT = 1

.PHONY: help
help: ## Display this help message
	@echo "Usage: make <target>"
	@echo
	@echo "Available targets:"
	@grep --extended-regexp --no-filename '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "	%-20s%s\n", $$1, $$2}'

.venv/timestamp: requirements.txt Makefile Pipfile
	/usr/bin/python3 -m virtualenv .venv
	.venv/bin/pip install --upgrade -r requirements.txt
	.venv/bin/poetry install
	touch $@

.venv/bin/c2cciutils-checks: ci/requirements.txt
	.venv/bin/pip install --upgrade -r ci/requirements.txt
	touch $@

.PHONY: local-tests
local-tests: .venv/timestamp
	.venv/bin/pytest

.PHONY: fix
fix: .venv/bin/c2cciutils-checks
	.venv/bin/c2cciutils-checks --fix --check=black
	.venv/bin/c2cciutils-checks --fix --check=isort

.PHONY: build
build: # Build the application Docker image
	docker build --tag=camptocamp/es-ooms-exporter .

.PHONY: build-checker
build-checker: # Build the checker Docker image
	docker build --target=checker --tag=camptocamp/es-ooms-exporter-checker .

.PHONY: checks
checks: prospector ## Run the checks

.PHONY: prospector
prospector: build-checker ## Run Prospector
	docker run --rm --volume=${PWD}:/app camptocamp/es-ooms-exporter-checker prospector --output=pylint --die-on-tool-error

.PHONY: tests
tests: build-checker ## Run the unit tests
	docker run --rm --volume=${PWD}:/app camptocamp/es-ooms-exporter-checker pytest
