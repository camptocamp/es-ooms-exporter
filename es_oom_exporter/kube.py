import logging
import os
from typing import Any, Dict, List

from kubernetes.client import CoreV1Api, VersionApi
from kubernetes.client.api_client import ApiClient
from kubernetes.client.models.v1_pod_list import V1PodList
from kubernetes.config.incluster_config import SERVICE_TOKEN_FILENAME, load_incluster_config
from kubernetes.config.kube_config import load_kube_config

LOG = logging.getLogger(__name__)
NAMESPACE = os.environ.get("NAMESPACE")


class Kubernetes:
    """Get some additional the information about the kubernetes contest."""

    def __init__(self) -> None:
        if os.path.exists(SERVICE_TOKEN_FILENAME):
            load_incluster_config()
        else:
            load_kube_config()
        self.api = ApiClient()
        version_api = VersionApi(self.api)
        self._is_openshift = "eks" not in version_api.get_code().git_version

    def get_pod_infos(self) -> Dict[Any, Dict[str, Any]]:
        if NAMESPACE is None:
            results = {}
            namespaces = self.get_namespaces()
            for namespace in namespaces:
                results.update(self._get_pod_infos_ns(namespace))
            return results
        else:
            return self._get_pod_infos_ns(NAMESPACE)

    def _get_pod_infos_ns(self, namespace: str) -> Dict[Any, Dict[str, Any]]:
        v1 = CoreV1Api(self.api)
        results = {}
        pods: V1PodList = v1.list_namespaced_pod(namespace)
        for pod in pods.items:
            md = pod.metadata
            status = pod.status
            containers = {}
            for statuses in (status.container_statuses, status.init_container_statuses):
                if statuses is not None:
                    for container_status in statuses:
                        if container_status.container_id is not None:
                            containers[
                                container_status.container_id.replace("docker://", "")
                            ] = container_status.name
                        if container_status.last_state.terminated is not None:
                            containers[
                                container_status.last_state.terminated.container_id.replace("docker://", "")
                            ] = container_status.name
            results[md.uid] = {
                "namespace": md.namespace,
                "release": md.labels.get("release", md.labels.get("app.kubernetes.io/instance")),
                "service": md.labels.get("service", md.labels.get("app.kubernetes.io/name")),
                "pod_name": md.name,
                "containers": containers,
            }
        return results

    def get_namespaces(self) -> List[Any]:
        if self._is_openshift:
            data, status, _headers = self.api.call_api(
                "/apis/project.openshift.io/v1/projects",
                "GET",
                auth_settings=["BearerToken"],
                response_type=object,
            )
            assert status == 200  # nosec
            assert data["kind"] == "ProjectList"  # nosec
            return [ns["metadata"]["name"] for ns in data["items"]]
        else:
            v1 = CoreV1Api(self.api)
            namespaces = v1.list_namespace()
            return [ns.metadata.name for ns in namespaces.items]
