from kubernetes.client.api_client import ApiClient
from kubernetes.client.apis.core_v1_api import CoreV1Api
from kubernetes.client.models.v1_pod_list import V1PodList
from kubernetes.config.incluster_config import load_incluster_config, SERVICE_TOKEN_FILENAME
from kubernetes.config.kube_config import load_kube_config
import logging
import os

LOG = logging.getLogger(__name__)
NAMESPACE = os.environ.get('NAMESPACE')


class Kubernetes:
    def __init__(self):
        if os.path.exists(SERVICE_TOKEN_FILENAME):
            load_incluster_config()
        else:
            load_kube_config()
        self.api = ApiClient()

    def get_pod_infos(self):
        if NAMESPACE is None:
            results = {}
            namespaces = self.get_namespaces()
            for namespace in namespaces:
                results.update(self._get_pod_infos_ns(namespace))
            return results
        else:
            return self._get_pod_infos_ns(NAMESPACE)

    def _get_pod_infos_ns(self, namespace):
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
                            containers[container_status.container_id.replace("docker://", "")] = container_status.name
            results[md.uid] = {
                'namespace': md.namespace,
                'pod_name': md.name,
                'containers': containers
            }
        return results

    def get_namespaces(self):
        data, status, _headers = self.api.call_api(
            '/apis/project.openshift.io/v1/projects', 'GET', auth_settings=['BearerToken'], response_type=object)
        assert status == 200
        assert data['kind'] == 'ProjectList'
        return [ns['metadata']['name'] for ns in data['items']]
