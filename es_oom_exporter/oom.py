import logging
import re

LOG = logging.getLogger(__name__)
SIZE_RE = re.compile(r"^(\d+)([KMG])B$")
SIZES = {"K": 1024, "M": 1024 * 1024, "G": 1024 * 1024 * 1024}


class Oom:
    def __init__(self, host):
        self._host = host
        self._pod_uid = None
        self._process = None
        self._when = None
        self._container_uid = None
        self._containers_rss = {}
        self._pod_name = None
        self._namespace = None
        self._release = None
        self._service = None
        self._container = None

    def add_start_info(self, matcher, pod_infos):
        pod_uid = matcher.group(2).replace("_", "-")
        if self._pod_uid is not None:
            LOG.warning("Inconsistent logs (twice the start): %s", matcher.group(0))
            return
        self._pod_uid = pod_uid
        self._container_uid = matcher.group(3)
        pod_info = pod_infos.get(pod_uid)
        if pod_info is not None:
            self._pod_name = pod_info["pod_name"]
            self._namespace = pod_info["namespace"]
            self._release = pod_info["release"]
            self._service = pod_info["service"]
            container_info = pod_info["containers"].get(self._container_uid)
            if container_info is not None:
                self._container = container_info
            else:
                LOG.info("Didn't find container info for %s", matcher.group(0))
        else:
            LOG.debug(
                "Didn't find POD info for %s in [%s]: %s", pod_uid, ", ".join(pod_infos), matcher.group(0)
            )

    def add_pod_info(self, matcher):
        pod_uid = matcher.group(2).replace("_", "-")
        if pod_uid != self._pod_uid:
            LOG.warning(
                "Inconsistent logs (different PODs %s!=%s): %s", pod_uid, self._pod_uid, matcher.group(0)
            )
            return

        rss = _get_size(matcher.group(4))
        container_uid = matcher.group(3)
        self._containers_rss[container_uid] = rss

    def add_oom_info(self, matcher) -> bool:
        self._process = matcher.group(2)
        return self._container is not None

    def get_release(self):
        return self._release

    def get_service(self):
        return self._service

    def get_namespace(self):
        return self._namespace

    def get_pod_name(self):
        return self._pod_name

    def get_container(self):
        return self._container

    def get_process(self):
        return self._process

    def get_host(self):
        return self._host

    def get_key(self):
        return self._namespace, self._pod_name, self._container, self._process, self._host

    def get_rss(self):
        return sum(self._containers_rss.values())

    def get_killed_rss(self):
        return self._containers_rss.get(self._container_uid, 0)

    def __str__(self):
        return f"{'/'.join(self.get_key())}={self._containers_rss.get(self._container_uid)}"

    def __repr__(self):
        return f"Oom({str(self)})"


def _get_size(txt):
    matcher = SIZE_RE.match(txt)
    assert matcher, "Cannot parse " + txt  # nosec
    return int(matcher.group(1)) * SIZES[matcher.group(2)]
