FROM ubuntu:20.04 AS base

# Workaround for setuptools >= 60.0.0
ENV SETUPTOOLS_USE_DISTUTILS=stdlib \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
  apt-get install --assume-yes --no-install-recommends python3-pip && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache/*

WORKDIR /app
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --requirement=requirements.txt

COPY Pipfile* ./
RUN apt-get update && \
  apt-get install --assume-yes --no-install-recommends python3-dev gcc libpq-dev && \
  pipenv sync --system --clear && \
  apt-get autoremove --assume-yes python3-dev gcc libpq-dev && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache/*

FROM base AS checks

RUN pipenv sync --system --clear --dev

COPY . .
RUN python3 -m pip install --no-cache-dir --disable-pip-version-check --no-deps --editable=. && \
    prospector -X --output=pylint && \
    pytest

FROM base AS runner

COPY . .
RUN python3 -m pip install --no-cache-dir --disable-pip-version-check --no-deps --editable=. && \
    python3 -m compileall -q .

CMD ["/usr/bin/es-oom-exporter"]
ENV OTHER_LOG_LEVEL=WARN \
    LOG_LEVEL=INFO \
    C2CWSGIUTILS_LOG_LEVEL=WARN \
    LOG_TYPE=json
