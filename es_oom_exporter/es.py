import logging
import os
import re
import time

import requests

from es_oom_exporter.utils import ensure_slash

LOG = logging.getLogger(__name__)
POD_RE = re.compile(r".*kernel: Memory cgroup stats for /kubepods\.slice/kubepods-burstable\.slice/kubepods-burstable-pod([0-9a-f_]*)\.slice/docker-([0-9a-f]*)\.scope: .*")
OOM_RE = re.compile(r".*kernel: Memory cgroup out of memory: Kill process \d+ \(([^)]+)\) score \d+ or sacrifice child")

class ElasticSearch:
    def __init__(self):
        es_url = ensure_slash(os.environ['ES_URL'])
        es_indexes = os.environ.get('ES_INDEXES', '_all')
        es_auth = os.environ.get('ES_AUTH')
        self.search_headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "kbn-version": "6.8.0"
        }
        if es_auth is not None:
            self.search_headers['Authorization'] = es_auth
        self.search_url = f"{es_url}{es_indexes}/_search"
        self.last_timestamp = int(time.time() * 1000)

    def get_ooms(self, pod_infos):
        query = {
            "version": True,
            "size": 500,
            "sort": [
                {
                    "@timestamp": {
                        "order": "asc",
                        "unmapped_type": "boolean"
                    }
                }
            ],
            "docvalue_fields": [
                {
                    "field": "@timestamp",
                    "format": "epoch_millis"
                }
            ],
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_all": {}
                        }
                    ],
                    "filter": [
                        {
                            "match_phrase": {
                                "log.file.path": {
                                    "query": "/var/log/messages"
                                }
                            }
                        }, {
                            "match_phrase": {
                                "message": {
                                    "query": "kernel"
                                }
                            }
                        }, {
                            "bool": {
                                "should": [
                                    {
                                        "match_phrase": {
                                            "message": "Memory cgroup stats for"
                                        }
                                    }, {
                                        "match_phrase": {
                                            "message": "Memory cgroup out of memory"
                                        }
                                    }
                                ],
                                "minimum_should_match": 1
                            }
                        }
                    ]
                }
            }
        }
        if self.last_timestamp is not None:
            query['query']['bool']['filter'].append({
                "range": {
                    "@timestamp": {
                        "gt": self.last_timestamp,
                        "format": "epoch_millis"
                    }
                }
            })
        with requests.post(self.search_url, json=query, headers=self.search_headers) as r:
            if r.status_code != 200:
                LOG.warning("Error from ES: %s", r.text)
            r.raise_for_status()
            json = r.json()
            cur = None
            ooms = []
            for hit in json['hits']['hits']:
                timestamp = int(hit['fields']['@timestamp'][0])
                self.last_timestamp = timestamp
                message = hit['_source']['message']
                pod_match = POD_RE.match(message)
                if pod_match:
                    # LOG.debug("Found POD info: %s %s", pod_match.group(1), pod_match.group(2))
                    cur = dict(pod_uid=pod_match.group(1).replace("_", "-"), container_id=pod_match.group(2))
                else:
                    oom_match = OOM_RE.match(message)
                    if oom_match:
                        # LOG.debug("Found OOM info: %s", oom_match.group(1))
                        if cur is not None:
                            cur['process'] = oom_match.group(1)
                            cur['when'] = timestamp
                            pod_info = pod_infos.get(cur['pod_uid'])
                            if pod_info is not None:
                                cur['pod_name'] = pod_info['pod_name']
                                cur['namespace'] = pod_info['namespace']
                                container_info = pod_info['containers'].get(cur['container_id'])
                                if container_info is not None:
                                    cur['container'] = container_info
                            ooms.append(cur)
                            cur = None
            return ooms