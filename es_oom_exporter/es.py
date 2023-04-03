import json
import logging
import os
import re
import time
from typing import Dict, List

import requests

from es_oom_exporter.kube import Kubernetes
from es_oom_exporter.message_reader import MessageReader
from es_oom_exporter.oom import Oom
from es_oom_exporter.utils import ensure_slash

# Interesting messages during an OOM event:
# Sep 19 08:35:40 ip-10-10-10-56 kernel: Task in /kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod12be0f08_da27_11e9_99ac_069044000888.slice/docker-4304197e5a46240357356250fcaf602bb4930f1b87157b73ae5e240f4a67a150.scope killed as a result of limit of /kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod12be0f08_da27_11e9_99ac_069044000888.slice  # pylint: disable=line-too-long
# Sep 19 08:35:40 ip-10-10-10-56 kernel: Memory cgroup stats for /kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod12be0f08_da27_11e9_99ac_069044000888.slice/docker-f7b79d53414f335b713db094565061726ff3c1237859d756392a3d7198fa0e2c.scope: cache:0KB rss:388KB rss_huge:0KB mapped_file:0KB swap:0KB inactive_anon:0KB active_anon:388KB inactive_file:0KB active_file:0KB unevictable:0KB  # pylint: disable=line-too-long
# Sep 19 08:35:40 ip-10-10-10-56 kernel: Memory cgroup stats for /kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod12be0f08_da27_11e9_99ac_069044000888.slice/docker-4304197e5a46240357356250fcaf602bb4930f1b87157b73ae5e240f4a67a150.scope: cache:92KB rss:81440KB rss_huge:0KB mapped_file:60KB swap:0KB inactive_anon:28KB active_anon:81464KB inactive_file:4KB active_file:36KB unevictable:0KB  # pylint: disable=line-too-long
# Sep 19 08:35:40 ip-10-10-10-56 kernel: Memory cgroup out of memory: Kill process 99190 (apache2) score 1534 or sacrifice child  # pylint: disable=line-too-long

LOG = logging.getLogger(__name__)
START_RE = re.compile(
    r".* ([^ ]+) kernel: Task in /kubepods\.slice/kubepods-burstable\.slice/"
    r"kubepods-burstable-pod([0-9a-f_]*)\.slice/docker-([0-9a-f]*)\.scope killed as a result of "
    r"limit of /kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod[0-9a-f_]*\.slice"
)
CONTAINER_RE = re.compile(
    r".* ([^ ]+) kernel: Memory cgroup stats for /kubepods\.slice/kubepods-burstable\.slice/"
    r"kubepods-burstable-pod([0-9a-f_]*)\.slice/docker-([0-9a-f]*)\.scope:.* rss:(\d+[KMG]B).*"
)
OOM_RE = re.compile(
    r".* ([^ ]+) kernel: Memory cgroup out of memory: Kill process \d+ \(([^)]+)\) "
    r"score \d+ or sacrifice child"
)


class ElasticSearch(MessageReader):
    """Read the message from elastic search."""

    def __init__(self) -> None:
        es_url = ensure_slash(os.environ["ES_URL"])
        es_indexes = os.environ.get("ES_INDEXES", "_all")
        es_auth = os.environ.get("ES_AUTH")
        self.search_headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "kbn-version": "6.8.0",
        }
        if es_auth is not None:
            self.search_headers["Authorization"] = es_auth
        self.search_url = f"{es_url}{es_indexes}/_search"
        self.last_timestamp = int(time.time() * 1000)

    def get_ooms(self, kube: Kubernetes) -> List[Oom]:
        query = {
            "version": True,
            "size": 500,
            "sort": [{"log.offset": {"order": "asc", "unmapped_type": "boolean"}}],
            "docvalue_fields": [{"field": "@timestamp", "format": "epoch_millis"}],
            "query": {
                "bool": {
                    "must": [{"match_all": {}}],
                    "filter": [
                        {"match_phrase": {"log.file.path": {"query": "/var/log/messages"}}},
                        {"match_phrase": {"message": {"query": "kernel"}}},
                        {
                            "bool": {
                                "should": [
                                    {"match_phrase": {"message": "Memory cgroup stats for"}},
                                    {"match_phrase": {"message": "Memory cgroup out of memory"}},
                                    {"match_phrase": {"message": "killed as a result of limit of"}},
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                    ],
                }
            },
        }
        if self.last_timestamp is not None:
            query["query"]["bool"]["filter"].append(  # type: ignore
                {"range": {"@timestamp": {"gt": self.last_timestamp, "format": "epoch_millis"}}}
            )
        LOG.info("Doing query: %s", json.dumps(query))
        with requests.post(self.search_url, json=query, headers=self.search_headers, timeout=30) as r:
            r.raise_for_status()
            json_responce = r.json()
            hits = json_responce["hits"]["hits"]
            if len(hits) == 0:
                return []
            pod_infos = kube.get_pod_infos()
            cur_by_host: Dict[str, Oom] = {}
            ooms = []
            for hit in hits:
                timestamp = int(hit["fields"]["@timestamp"][0])
                self.last_timestamp = timestamp
                message = hit["_source"]["message"]
                LOG.debug("message: %s", message)
                start_match = START_RE.match(message)
                pod_match = CONTAINER_RE.match(message)
                oom_match = OOM_RE.match(message)
                if start_match:
                    _get_cur(cur_by_host, start_match.group(1)).add_start_info(start_match, pod_infos)
                if pod_match:
                    _get_cur(cur_by_host, pod_match.group(1)).add_pod_info(pod_match)
                elif oom_match:
                    cur = cur_by_host.pop(oom_match.group(1), None)
                    if cur is not None and cur.add_oom_info(oom_match):
                        ooms.append(cur)
            return ooms


def _get_cur(cur_by_host: Dict[str, Oom], host: str) -> Oom:
    cur = cur_by_host.get(host)
    if cur is None:
        cur = Oom(host)
        cur_by_host[host] = cur
    return cur
