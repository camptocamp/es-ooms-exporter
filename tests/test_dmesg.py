from mockito import mock, when

from es_oom_exporter.dmesg import Dmesg


def test_new_kernel(monkeypatch):
    monkeypatch.setenv("NODE_NAME", "toto")
    dmesg = Dmesg()
    kube = mock()
    when(kube).get_pod_infos().thenReturn(
        {
            "792adfde-d139-4c9c-a89e-ae94f36ea69d": {
                "namespace": "my_ns",
                "release": "my_release",
                "service": "my_service",
                "pod_name": "my_pod",
                "containers": {
                    "7a982186b58cec345c4a3f635809c7e04afc930453a5dbb5cbc9d4d49f662761": "my_container"
                },
            }
        }
    )

    ooms = dmesg._process_ooms(
        [
            b"[10657070.816698] oom-kill:constraint=CONSTRAINT_MEMCG,nodemask=(null),cpuset=7a982186b58cec345c4a3f635809c7e04afc930453a5dbb5cbc9d4d49f662761,mems_allowed=0,oom_memcg=/kubepods/burstable/pod792adfde-d139-4c9c-a89e-ae94f36ea69d/7a982186b58cec345c4a3f635809c7e04afc930453a5dbb5cbc9d4d49f662761,task_memcg=/kubepods/burstable/pod792adfde-d139-4c9c-a89e-ae94f36ea69d/7a982186b58cec345c4a3f635809c7e04afc930453a5dbb5cbc9d4d49f662761,task=ruby,pid=10506,uid=1000\n"  # noqa: E501
        ],
        kube,
    )

    assert list(map(repr, ooms)) == ["Oom(my_ns/my_pod/my_container/ruby/toto=None)"]


def test_old_kernel(monkeypatch):
    monkeypatch.setenv("NODE_NAME", "toto")
    dmesg = Dmesg()
    kube = mock()
    when(kube).get_pod_infos().thenReturn(
        {
            "af389229-5fc5-4617-ae95-9160d576eb49": {
                "namespace": "my_ns",
                "release": "my_release",
                "service": "my_service",
                "pod_name": "my_pod",
                "containers": {
                    "3b3d031aca1bab63c359a8aac8c18e373ac90373faf12c69e5225aec01fc9c84": "my_container"
                },
            }
        }
    )

    ooms = dmesg._process_ooms(
        [
            b"[21013.577527] Task in /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49/3b3d031aca1bab63c359a8aac8c18e373ac90373faf12c69e5225aec01fc9c84 killed as a result of limit of /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49\n",  # noqa: E501
            b"[21013.577528] Memory cgroup stats for /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49: cache:0KB rss:0KB rss_huge:0KB shmem:0KB mapped_file:0KB dirty:0KB writeback:0KB swap:0KB inactive_anon:0KB active_anon:0KB inactive_file:0KB active_file:0KB unevictable:0KB\n",  # noqa: E501
            b"[21013.577529] Memory cgroup stats for /kubepods/burstable/podaf389229-5fc5-4617-ae95-9160d576eb49/3b3d031aca1bab63c359a8aac8c18e373ac90373faf12c69e5225aec01fc9c84: cache:0KB rss:36KB rss_huge:0KB shmem:0KB mapped_file:0KB dirty:0KB writeback:0KB swap:0KB inactive_anon:0KB active_anon:36KB inactive_file:0KB active_file:0KB unevictable:0KB\n",  # noqa: E501
            b"[21013.577530] Memory cgroup out of memory: Kill process 8308 (java) score 1894 or sacrifice child\n",  # noqa: E501
        ],
        kube,
    )

    assert list(map(repr, ooms)) == ["Oom(my_ns/my_pod/my_container/java/toto=36864)"]
