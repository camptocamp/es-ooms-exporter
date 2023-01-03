import logging
import os
import re
import subprocess  # nosec
from typing import Dict, Iterable, List, Optional

from es_oom_exporter.kube import Kubernetes
from es_oom_exporter.message_reader import MessageReader
from es_oom_exporter.oom import Oom

LOG = logging.getLogger(__name__)
TIMESTAMP_RE = re.compile(r"\[\s*(\d+\.\d+)\].*")

# Interesting messages in dmesg with old kernels:
# [21013.577527] Task in /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49/3b3d031aca1bab63c359a8aac8c18e373ac90373faf12c69e5225aec01fc9c84 killed as a result of limit of /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49  # pylint: disable=line-too-long
# [21013.577527] Memory cgroup stats for /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49: cache:0KB rss:0KB rss_huge:0KB shmem:0KB mapped_file:0KB dirty:0KB writeback:0KB swap:0KB inactive_anon:0KB active_anon:0KB inactive_file:0KB active_file:0KB unevictable:0KB  # pylint: disable=line-too-long
# [21013.577527] Memory cgroup stats for /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49/4c08772ec23ea2f82822e90f1d41c028b43eb01f0bfc18ea262ae4ccbc6189de: cache:0KB rss:36KB rss_huge:0KB shmem:0KB mapped_file:0KB dirty:0KB writeback:0KB swap:0KB inactive_anon:0KB active_anon:36KB inactive_file:0KB active_file:0KB unevictable:0KB  # pylint: disable=line-too-long
# [21013.577527] Memory cgroup out of memory: Kill process 8308 (java) score 1894 or sacrifice child
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

# Interesting messages in dmesg with new kernels:
# [10657070.816698] oom-kill:constraint=CONSTRAINT_MEMCG,nodemask=(null),cpuset=7a982186b58cec345c4a3f635809c7e04afc930453a5dbb5cbc9d4d49f662761,mems_allowed=0,oom_memcg=/kubepods/burstable/pod792adfde-d139-4c9c-a89e-ae94f36ea69d/7a982186b58cec345c4a3f635809c7e04afc930453a5dbb5cbc9d4d49f662761,task_memcg=/kubepods/burstable/pod792adfde-d139-4c9c-a89e-ae94f36ea69d/7a982186b58cec345c4a3f635809c7e04afc930453a5dbb5cbc9d4d49f662761,task=ruby,pid=10506,uid=1000  # pylint: disable=line-too-long
OOM_KILL_RE = re.compile(r"\[\s*(\d+\.\d+)\] oom-kill:(.*)")


class Dmesg(MessageReader):
    """Read the message from dmesg."""

    def __init__(self) -> None:
        self._node_name = os.environ["NODE_NAME"]
        self._cur: Optional[Oom] = None

        self._prev_timestamp: Optional[float] = None

    def _get_cur(self) -> Oom:
        if self._cur is None:
            self._cur = Oom(self._node_name)
        return self._cur

    def _process_ooms(self, lines: Iterable[bytes], kube: Kubernetes) -> List[Oom]:
        ooms: List[Oom] = []
        pod_infos = None
        for message in _get_messages(lines):
            # Cannot use --follow (not working in a container) and cannot specify a position in the
            # logs where to start. So, we need to read everything from the start and ignore the logs
            # we've already seen.
            timestamp_match = TIMESTAMP_RE.match(message)
            if not timestamp_match:
                continue
            timestamp = float(timestamp_match.group(1))
            if self._prev_timestamp is not None and self._prev_timestamp >= timestamp:
                continue
            self._prev_timestamp = timestamp

            LOG.debug("message: <%s>", message)
            start_match = START_RE.match(message)
            pod_match = CONTAINER_RE.match(message)
            oom_match = OOM_RE.match(message)
            oom_kill_match = OOM_KILL_RE.match(message)
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
            elif oom_kill_match:
                fields = _split_oom_kill(oom_kill_match.group(2))
                if pod_infos is None:
                    pod_infos = kube.get_pod_infos()
                if self._get_cur().add_oom_kill_info(fields, pod_infos):
                    ooms.append(self._get_cur())
                self._cur = None
        return ooms

    def get_ooms(self, kube: Kubernetes) -> List[Oom]:
        with subprocess.Popen(  # nosec
            ["/usr/bin/dmesg", "--facility=kern", "--level=info,err"], stdout=subprocess.PIPE
        ) as dmesg:
            if dmesg.stdout is None:
                return []
            ooms = self._process_ooms(dmesg.stdout, kube)
            dmesg.wait()
        return ooms


def _get_messages(data: Iterable[bytes]) -> Iterable[str]:
    prev = b""
    for cur in data:
        cur = prev + cur
        if not cur.endswith(b"\n"):
            prev = cur
        else:
            prev = b""
            yield cur.decode().rstrip("\n")


def _split_oom_kill(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for field in text.split(","):
        split_field = field.split("=", 1)
        if len(split_field) == 2:
            result[split_field[0]] = split_field[1]
    return result
