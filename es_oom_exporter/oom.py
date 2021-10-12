import logging
import re
from typing import Any, Dict, Match, Optional

LOG = logging.getLogger(__name__)
SIZE_RE = re.compile(r"^(\d+)([KMG])B$")
SIZES = {"K": 1024, "M": 1024 * 1024, "G": 1024 * 1024 * 1024}


class Oom:
    """Metadata information about the detected OOM."""

    def __init__(self, host: str):
        self._host = host
        self._pod_uid: Optional[str] = None
        self._process: Optional[str] = None
        self._when: Optional[str] = None
        self._container_uid: Optional[str] = None
        self._containers_rss: Dict[str, float] = {}
        self._pod_name: Optional[str] = None
        self._namespace: Optional[str] = None
        self._release: Optional[str] = None
        self._service: Optional[str] = None
        self._container: Optional[str] = None

    def add_start_info(self, matcher: Match[str], pod_infos: Dict[str, Any]) -> None:
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

    def add_pod_info(self, matcher: Match[str]) -> None:
        pod_uid = matcher.group(2).replace("_", "-")
        if pod_uid != self._pod_uid:
            LOG.warning(
                "Inconsistent logs (different PODs %s!=%s): %s", pod_uid, self._pod_uid, matcher.group(0)
            )
            return

        rss = _get_size(matcher.group(4))
        container_uid = matcher.group(3)
        self._containers_rss[container_uid] = rss

    def add_oom_info(self, matcher: Match[str]) -> bool:
        self._process = matcher.group(2)
        return self._container is not None

    def get_release(self) -> Optional[str]:
        return self._release

    def get_service(self) -> Optional[str]:
        return self._service

    def get_namespace(self) -> Optional[str]:
        return self._namespace

    def get_pod_name(self) -> Optional[str]:
        return self._pod_name

    def get_container(self) -> Optional[str]:
        return self._container

    def get_process(self) -> Optional[str]:
        return self._process

    def get_host(self) -> str:
        return self._host

    def get_key(self) -> Any:
        return self._namespace, self._pod_name, self._container, self._process, self._host

    def get_rss(self) -> float:
        return sum(self._containers_rss.values())

    def get_killed_rss(self) -> float:
        assert self._container_uid is not None  # nosec
        return self._containers_rss.get(self._container_uid, 0)

    def __str__(self) -> str:
        assert self._container_uid is not None  # nosec
        return f"{'/'.join(self.get_key())}={self._containers_rss.get(self._container_uid)}"

    def __repr__(self) -> str:
        return f"Oom({str(self)})"


def _get_size(txt: str) -> int:
    matcher = SIZE_RE.match(txt)
    assert matcher, "Cannot parse " + txt  # nosec
    return int(matcher.group(1)) * SIZES[matcher.group(2)]
