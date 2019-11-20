# es-oom-exporter

Listen on elasticsearch for kernel OOM messages and tries to resolve
the POD from the kubernetes API. The result is exported to prometheus.

to run:
```bash
docker run --rm --publish=8080:8080 \
  --env=NAMESPACE=gs-gmf-demo \
  --env=ES_URL=https://elasticsearch.example.com/ \
  --env=ES_AUTH="Basic xxxx" \
  --volume=~/.kube:/root/.kube \
  camptocamp/es-ooms-exporter
```

Configuration variables:

* ES_URL: Base URL of elasticsearch
* ES_AUTH: Optional auth string for elasticsearch
* ES_INDEXES: Optional index to use
* NAMESPACE: Kubernetes namespace to use (by default, uses all
             the OpenShift projects)

Will detect automatically if run from within kubernetes or from the outside
(uses the current context)

To test it use a stress container, run it with e.-g.:

```bash
oc run oom --restart=Never --labels="release=test,service=toto" --image=polinux/stress --requests="cpu=1m,memory=10Mi" --limits="memory=10Mi" -- stress --vm 1 --vm-bytes 20M
oc delete pod oom
```

Then, you need to get the metrics:

```bash
curl http://localhost:8080/metrics
```
