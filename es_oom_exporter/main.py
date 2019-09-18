from c2cwsgiutils import setup_process  # noqa  # pylint: disable=unused-import
from es_oom_exporter.es import ElasticSearch
from es_oom_exporter.kube import Kubernetes
import logging
import prometheus_client
from prometheus_client.core import GaugeMetricFamily
import time

LABELS = ['namespace', 'pod', 'container', 'process']

LOG = logging.getLogger('es_oom_exporter')


class OomsCollector:
    def __init__(self, kube, es):
        self.kube = kube
        self.es = es

    def collect(self):
        pod_infos = self.kube.get_pod_infos()
        ooms = self.es.get_ooms(pod_infos)
        LOG.info(ooms)
        g_oom = GaugeMetricFamily('pod_process_oom',
                                  "OOM events in a POD's container",
                                  labels=LABELS)
        g_rss = GaugeMetricFamily('pod_process_oom_rss',
                                  "RSS in bytes before an OOM events in a POD's container",
                                  labels=LABELS)
        count_containers = {}
        rss_containers = {}
        for oom in ooms:
            if 'container' in oom:
                key = tuple(oom[k] for k in ('namespace', 'pod_name', 'container', 'process'))
                if key in count_containers:
                    count_containers[key] += 1
                else:
                    count_containers[key] = 1
                rss_containers[key] = max(rss_containers.get(key, 0), oom['rss'])

        for key in count_containers.keys():
            g_oom.add_metric(labels=key, value=count_containers[key])
            g_rss.add_metric(labels=key, value=rss_containers[key])

        yield g_oom
        yield g_rss


def main():
    logging.getLogger('kubernetes').setLevel(logging.INFO)
    es = ElasticSearch()
    kube = Kubernetes()
    prometheus_client.start_http_server(port=8080)
    prometheus_client.REGISTRY.register(OomsCollector(kube, es))
    while True:
        time.sleep(10)


main()