import logging
import os
import re
import subprocess  # nosec
from typing import List, Optional

from es_oom_exporter.kube import Kubernetes
from es_oom_exporter.message_reader import MessageReader
from es_oom_exporter.oom import Oom

# Interesting messages in dmesg:
# [21013.577527] Task in /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49/3b3d031aca1bab63c359a8aac8c18e373ac90373faf12c69e5225aec01fc9c84 killed as a result of limit of /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49  # noqa: E501
# [21013.577527] Memory cgroup stats for /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49: cache:0KB rss:0KB rss_huge:0KB shmem:0KB mapped_file:0KB dirty:0KB writeback:0KB swap:0KB inactive_anon:0KB active_anon:0KB inactive_file:0KB active_file:0KB unevictable:0KB  # noqa: E501
# [21013.577527] Memory cgroup stats for /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49/4c08772ec23ea2f82822e90f1d41c028b43eb01f0bfc18ea262ae4ccbc6189de: cache:0KB rss:36KB rss_huge:0KB shmem:0KB mapped_file:0KB dirty:0KB writeback:0KB swap:0KB inactive_anon:0KB active_anon:36KB inactive_file:0KB active_file:0KB unevictable:0KB  # noqa: E501
# [21013.577527] Memory cgroup out of memory: Kill process 8308 (java) score 1894 or sacrifice child  # noqa: E501

LOG = logging.getLogger(__name__)
TIMESTAMP_RE = re.compile(r"\[\s*(\d+\.\d+)\].*")
START_RE = re.compile(
    r"\[\s*(\d+\.\d+)\] Task in /kubepods/(?:burstable/)?pod([0-9a-f_-]*)/([0-9a-f]*) killed as a result of "
    r"limit of /kubepods/(?:burstable/)?pod[0-9a-f_-]*"
)
CONTAINER_RE = re.compile(
    r"\[\s*(\d+\.\d+)\] Memory cgroup stats for /kubepods/(?:burstable/)?pod([0-9a-f_-]*)/([0-9a-f]*):.* "
    r"rss:(\d+[KMG]B).*"
)
OOM_RE = re.compile(
    r"\[\s*(\d+\.\d+)\] Memory cgroup out of memory: Kill process \d+ \(([^)]+)\) score \d+ or "
    r"sacrifice child"
)


class Dmesg(MessageReader):
    def __init__(self) -> None:
        self._node_name = os.environ["NODE_NAME"]
        self._cur: Optional[Oom] = None

        self._prev_timestamp: Optional[float] = None

    def _get_cur(self) -> Oom:
        if self._cur is None:
            self._cur = Oom(self._node_name)
        return self._cur

    def get_ooms(self, kube: Kubernetes) -> List[Oom]:
        ooms: List[Oom] = []
        pod_infos = None
        dmesg = subprocess.Popen(  # nosec
            ["/usr/bin/dmesg", "--facility=kern", "--level=info,err"], stdout=subprocess.PIPE
        )
        if dmesg.stdout is None:
            return []
        prev = b""
        timestamp = None
        for line in dmesg.stdout:
            line = prev + line
            if not line.endswith(b"\n"):
                prev = line
            else:
                prev = b""
                message = line.decode().rstrip("\n")

                # Cannot use --follow (not working in a container) and cannot specify a position in the logs
                # where to start. So, we need to read everything from the start and ignore the logs we've
                # already seen.
                timestamp_match = TIMESTAMP_RE.match(message)
                if not timestamp_match:
                    continue
                timestamp = float(timestamp_match.group(1))
                if self._prev_timestamp is not None and self._prev_timestamp >= timestamp:
                    continue

                LOG.debug("message: <%s>", message)
                start_match = START_RE.match(message)
                pod_match = CONTAINER_RE.match(message)
                oom_match = OOM_RE.match(message)
                if start_match:
                    if pod_infos is None:
                        pod_infos = kube.get_pod_infos()
                    self._get_cur().add_start_info(start_match, pod_infos)
                elif pod_match:
                    self._get_cur().add_pod_info(pod_match)
                elif oom_match:
                    if self._cur is not None and self._cur.add_oom_info(oom_match):
                        ooms.append(self._cur)
                    self._cur = None
        if timestamp is not None:
            self._prev_timestamp = timestamp
        dmesg.wait()
        return ooms
