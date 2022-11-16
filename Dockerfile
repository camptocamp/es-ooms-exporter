FROM ubuntu:22.04 AS base-all
LABEL maintainer Camptocamp "info@camptocamp.com"
SHELL ["/bin/bash", "-o", "pipefail", "-cux"]

RUN --mount=type=cache,target=/var/lib/apt/lists \
  --mount=type=cache,target=/var/cache,sharing=locked \
  apt-get update \
  && apt-get upgrade --assume-yes \
  && apt-get install --assume-yes --no-install-recommends python3-pip \
  && python3 -m pip install --disable-pip-version-check --upgrade pip

# Used to convert the locked packages by poetry to pip requirements format
# We don't directly use `poetry install` because it force to use a virtual environment.
FROM base-all as poetry

# Install Poetry
WORKDIR /tmp
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache \
  python3 -m pip install --disable-pip-version-check --requirement=requirements.txt

# Do the conversion
COPY poetry.lock pyproject.toml ./
RUN poetry export --output=requirements.txt \
  && poetry export --with=dev --output=requirements-dev.txt

# Base, the biggest thing is to install the Python packages
FROM base-all as base

WORKDIR /app

RUN --mount=type=cache,target=/var/lib/apt/lists \
  --mount=type=cache,target=/var/cache,sharing=locked \
  --mount=type=cache,target=/root/.cache \
  --mount=type=bind,from=poetry,source=/tmp,target=/poetry \
  apt-get update \
  && apt-get install --assume-yes --no-install-recommends python3-dev gcc libpq-dev \
  && python3 -m pip install --disable-pip-version-check --no-deps --requirement=/poetry/requirements.txt \
  && apt-get autoremove --assume-yes python3-dev gcc libpq-dev

FROM base AS checker

RUN --mount=type=cache,target=/root/.cache \
  --mount=type=bind,from=poetry,source=/tmp,target=/poetry \
  python3 -m pip install --disable-pip-version-check --no-deps --requirement=/poetry/requirements-dev.txt

COPY . .
RUN --mount=type=cache,target=/root/.cache \
  python3 -m pip install --disable-pip-version-check --no-deps --editable=.

FROM base AS runner

COPY . .
RUN --mount=type=cache,target=/root/.cache \
  python3 -m pip install --disable-pip-version-check --no-deps --editable=. \
  && python3 -m compileall -q .

CMD ["/usr/local/bin/es-oom-exporter"]
ENV OTHER_LOG_LEVEL=WARN \
  LOG_LEVEL=INFO \
  C2CWSGIUTILS_LOG_LEVEL=WARN \
  LOG_TYPE=json
