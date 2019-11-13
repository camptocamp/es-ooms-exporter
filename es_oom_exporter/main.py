import logging
import time
from typing import List

from c2cwsgiutils import setup_process  # noqa  # pylint: disable=unused-import

from es_oom_exporter.es import ElasticSearch, Oom
from es_oom_exporter.kube import Kubernetes
import prometheus_client
from prometheus_client.core import GaugeMetricFamily

LABELS = ['namespace', 'pod', 'container', 'process']

LOG = logging.getLogger('es_oom_exporter')


class OomsCollector:
    def __init__(self, kube, es):
        self.kube = kube
        self.es = es

    def collect(self):
        ooms: List[Oom] = self.es.get_ooms(self.kube)
        LOG.info(ooms)
        g_oom = GaugeMetricFamily('pod_process_oom',
                                  "OOM events in a POD's container",
                                  labels=LABELS)
        g_rss_killed = GaugeMetricFamily('pod_process_oom_rss_container',
                                         "RSS in bytes before an OOM events in a POD's container",
                                         labels=LABELS)
        g_rss = GaugeMetricFamily('pod_process_oom_rss',
                                  "RSS in bytes before an OOM events in a POD's container",
                                  labels=LABELS)
        count_containers = {}
        rss_containers = {}
        rss_killed_container = {}
        for oom in ooms:
            key = oom.get_key()
            LOG.warn(
                "Killed namespace: %s, release: %s, service: %s, pod: %s, container: %s, process: %s rss: %s, "
                "rss_killed: %s",
                key[0], oom.get_release(), oom.get_service(), key[1], key[2], key[3], oom.get_rss(),
                oom.get_killed_rss()
            )
            if key in count_containers:
                count_containers[key] += 1
            else:
                count_containers[key] = 1
            rss_containers[key] = max(rss_containers.get(key, 0), oom.get_rss())
            rss_killed_container[key] = max(rss_killed_container.get(key, 0), oom.get_killed_rss())

        for key in count_containers.keys():
            g_oom.add_metric(labels=key, value=count_containers[key])
            g_rss.add_metric(labels=key, value=rss_containers[key])
            g_rss_killed.add_metric(labels=key, value=rss_killed_container[key])

        yield g_oom
        yield g_rss_killed
        yield g_rss


def main():
    logging.getLogger('kubernetes').setLevel(logging.INFO)
    es = ElasticSearch()
    kube = Kubernetes()
    prometheus_client.REGISTRY.register(OomsCollector(kube, es))
    prometheus_client.start_http_server(port=8080)
    while True:
        time.sleep(10)


main()
