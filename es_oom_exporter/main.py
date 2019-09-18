from c2cwsgiutils import setup_process  # noqa  # pylint: disable=unused-import
from es_oom_exporter.es import ElasticSearch
from es_oom_exporter.kube import Kubernetes
import logging
import prometheus_client
import prometheus_client.core
import time

LOG = logging.getLogger('es_oom_exporter')


class OomsCollector:
    def __init__(self, kube, es):
        self.kube = kube
        self.es = es

    def collect(self):
        pod_infos = self.kube.get_pod_infos()
        ooms = self.es.get_ooms(pod_infos)
        LOG.info(ooms)
        g_container = prometheus_client.core.GaugeMetricFamily('pod_process_oom', "OOM events in a POD's container",
                                                               labels=['namespace', 'pod', 'container', 'process'])
        count_containers = {}
        for oom in ooms:
            if 'container' in oom:
                key = tuple(oom[k] for k in ('namespace', 'pod_name', 'container', 'process'))
                if key in count_containers:
                    count_containers[key] += 1
                else:
                    count_containers[key] = 1

        for key, count in count_containers.items():
            g_container.add_metric(labels=key, value=count)
        yield g_container


def main():
    logging.getLogger('kubernetes').setLevel(logging.INFO)
    es = ElasticSearch()
    kube = Kubernetes()
    prometheus_client.start_http_server(port=8080)
    prometheus_client.REGISTRY.register(OomsCollector(kube, es))
    while True:
        time.sleep(10)



main()