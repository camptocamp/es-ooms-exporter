import logging.config
import os
import time
from typing import List

import prometheus_client  # type: ignore
from prometheus_client.core import GaugeMetricFamily  # type: ignore

from es_oom_exporter.dmesg import Dmesg
from es_oom_exporter.es import ElasticSearch
from es_oom_exporter.kube import Kubernetes
from es_oom_exporter.message_reader import MessageReader
from es_oom_exporter.oom import Oom

LABELS = ["namespace", "pod", "container", "process", "host"]

LOG = logging.getLogger("es_oom_exporter")


class OomsCollector:
    def __init__(self, kube: Kubernetes, message_reader: MessageReader):
        self.kube = kube
        self.message_reader = message_reader

    def collect(self):
        ooms: List[Oom] = self.message_reader.get_ooms(self.kube)
        g_oom = GaugeMetricFamily("pod_process_oom", "OOM events in a POD's container", labels=LABELS)
        g_rss_killed = GaugeMetricFamily(
            "pod_process_oom_rss_container",
            "RSS in bytes before an OOM events in a POD's container",
            labels=LABELS,
        )
        g_rss = GaugeMetricFamily(
            "pod_process_oom_rss", "RSS in bytes before an OOM events in a POD's container", labels=LABELS
        )
        count_containers = {}
        rss_containers = {}
        rss_killed_container = {}
        for oom in ooms:
            key = oom.get_key()
            LOG.warning(
                "Killed host: %s, namespace: %s, release: %s, service: %s, pod: %s, container: %s, "
                "process: %s, rss: %s, rss_killed: %s",
                oom.get_host(),
                oom.get_namespace(),
                oom.get_release(),
                oom.get_service(),
                oom.get_pod_name(),
                oom.get_container(),
                oom.get_process(),
                oom.get_rss(),
                oom.get_killed_rss(),
            )
            if key in count_containers:
                count_containers[key] += 1
            else:
                count_containers[key] = 1
            rss_containers[key] = max(rss_containers.get(key, 0), oom.get_rss())
            rss_killed_container[key] = max(rss_killed_container.get(key, 0), oom.get_killed_rss())

        for key, count_container in count_containers.items():
            LOG.warning(
                "Killed container: %s count: %s, rss: %s, rss_killed: %s",
                key,
                count_container,
                rss_containers[key],
                rss_killed_container[key],
            )
            g_oom.add_metric(labels=key, value=count_container)
            g_rss.add_metric(labels=key, value=rss_containers[key])
            g_rss_killed.add_metric(labels=key, value=rss_killed_container[key])

        yield g_oom
        yield g_rss_killed
        yield g_rss


def main():
    logging.config.fileConfig("/app/production.ini", defaults=dict(os.environ))
    logging.getLogger("kubernetes").setLevel(logging.INFO)
    if "ES_URL" in os.environ:
        message_reader = ElasticSearch()
    else:
        message_reader = Dmesg()
    kube = Kubernetes()
    prometheus_client.REGISTRY.register(OomsCollector(kube, message_reader))
    prometheus_client.start_http_server(port=8080)
    while True:
        time.sleep(10)


main()
