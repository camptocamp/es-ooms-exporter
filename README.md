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

* For fetching logs from elasticsearch (suitable for OpenShift):
    * ES_URL: Base URL of elasticsearch
    * ES_AUTH: Optional auth string for elasticsearch
    * ES_INDEXES: Optional index to use
* For fetching logs from dmesg (suitable for EKS):
    * NODE_NAME: The name of the node running the POD
* NAMESPACE: Kubernetes namespace to use (by default, uses all
             the OpenShift projects)

Will detect automatically if run from within kubernetes or from the outside
(uses the current context)

To test it use a stress container, run it with e.g.:

```bash
oc run oom --restart=Never --labels="release=test,service=toto" --image=polinux/stress --requests="cpu=1m,memory=10Mi" --limits="memory=10Mi" -- stress --vm 1 --vm-bytes 20M
oc delete pod oom
```

Then, you need to get the metrics:

```bash
curl http://localhost:8080/metrics
```

## EKS

To run it on EKS without needing to setup logs on elasticsearch, deploy a DaemonSet like that:
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: {{ include "oom-exporter.fullname" . }}
  labels:
      {{- include "oom-exporter.labels" . | nindent 4 }}
spec:
  selector:
    matchLabels:
      {{- include "oom-exporter.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "oom-exporter.selectorLabels" . | nindent 8 }}
    spec:
      serviceAccount: {{ include "oom-exporter.fullname" $ }}
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          # don't put probes, they would consume the OOM events
          env:
            - name: NODE_NAME
              valueFrom:
                fieldRef:
                  fieldPath: spec.nodeName

---

apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
    name: {{ include "oom-exporter.fullname" $ }}
    labels:
        {{- include "oom-exporter.labels" $ | nindent 4 }}
rules:
    - apiGroups: [""]
      resources:
          - namespaces
          - pods
      verbs: ["list", "get"]

---

apiVersion: v1
kind: ServiceAccount
metadata:
    name: {{ include "oom-exporter.fullname" $ }}
    namespace: {{ $.Release.Namespace }}
    labels:
        {{- include "oom-exporter.labels" $ | nindent 4 }}

---

kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
    name: {{ include "oom-exporter.fullname" $ }}
    namespace: {{ $.Release.Namespace }}
    labels:
        {{- include "oom-exporter.labels" $ | nindent 4 }}
subjects:
    - kind: ServiceAccount
      name: {{ include "oom-exporter.fullname" $ }}
      namespace: {{ $.Release.Namespace }}
roleRef:
    apiGroup: rbac.authorization.k8s.io
    kind: ClusterRole
    name: {{ include "oom-exporter.fullname" $ }}
```
