from typing import List

from es_oom_exporter.kube import Kubernetes
from es_oom_exporter.oom import Oom


class MessageReader:
    def get_ooms(self, kube: Kubernetes) -> List[Oom]:
        raise NotImplementedError()
