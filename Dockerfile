FROM camptocamp/c2cwsgiutils:3

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir --disable-pip-version-check -e . && \
    python3 -m compileall -q . && \
    mypy --ignore-missing-imports /app
CMD ["/usr/local/bin/es-oom-exporter"]
