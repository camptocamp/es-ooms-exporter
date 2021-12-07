FROM ubuntu:20.04 AS base

RUN \
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt install --assume-yes --no-install-recommends \
  python3-pip && \
  apt clean && \
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache/*

WORKDIR /app
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --requirement=requirements.txt

COPY Pipfile* ./
RUN pipenv sync --system --clear

FROM base AS checks

RUN pipenv sync --system --clear --dev

COPY . .
RUN python3 -m pip install --no-cache-dir --disable-pip-version-check --no-deps --editable=.
RUN prospector --output=pylint
RUN pytest

FROM base AS runner

COPY . .
RUN python3 -m pip install --no-cache-dir --disable-pip-version-check --no-deps --editable=. && \
    python3 -m compileall -q .

CMD ["/usr/local/bin/es-oom-exporter"]
ENV OTHER_LOG_LEVEL=WARN \
    LOG_LEVEL=INFO \
    C2CWSGIUTILS_LOG_LEVEL=WARN \
    LOG_TYPE=json
