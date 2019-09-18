# es-oom-exporter

Listen on elasticsearch for kernel OOM messages and tries to resolve
the POD from the kubernetes API. The result is exported to prometheus.

to run:
```bash
docker run -ti --rm -p 8080:8080 \
  -e ES_URL=https://elasticsearch.example.com/ \
  -e ES_AUTH="Basic xxxx" \
  camptocamp/es-ooms-exporter
```

configuration variables:

* ES_URL: Base URL of elasticsearch
* ES_AUTH: Optional auth string for elasticsearch
* ES_INDEXES: Optional index to use
* NAMESPACE: Kubernetes namespace to use (by default, uses all
             the OpenShift projects)
