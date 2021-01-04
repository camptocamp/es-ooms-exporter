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
RUN pipenv install --system --clear --verbose

COPY . .
RUN python3 -m pip install --no-cache-dir --disable-pip-version-check --no-deps --editable=. && \
    python3 -m compileall -q .

FROM base AS checks

RUN pipenv install --system --clear --dev --verbose
RUN prospector

FROM base AS runner

CMD ["/usr/local/bin/es-oom-exporter"]
