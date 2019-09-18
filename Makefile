all: docker

.venv/timestamp: requirements.txt Makefile
	/usr/bin/virtualenv --python=/usr/bin/python3 .venv
	.venv/bin/pip install --upgrade -r requirements.txt
	touch $@

.PHONY: docker
docker:
	docker build --tag camptocamp/es-ooms-exporter:latest .