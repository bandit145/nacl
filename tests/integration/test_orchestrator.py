from nacl.orchestrators import Docker
from nacl.config import parse_config
import nacl.utils
import docker
import yaml
import copy
import os
import pytest

CWD = os.getcwd()
NO_CLEANUP = os.getenv("NO_INT_TEST_CLEANUP")


@pytest.fixture
def reset_dir():
    yield
    os.chdir(CWD)


def load_test_config(path: str) -> dict:
    with open(path, "r") as config:
        return yaml.safe_load(config)


def test_docker_image_pull(reset_dir) -> None:
    test_conf = parse_config(load_test_config("tests/data/test_confs/test1.yml"))
    orch = Docker(test_conf)
    orch.__pull_images__()
    image = orch.client.images.get(test_conf["instances"][0]["image"])
    assert isinstance(image, docker.models.images.Image)


def test_docker_create_network(reset_dir) -> None:
    test_conf = parse_config(load_test_config("tests/data/test_confs/test1.yml"))
    orch = Docker(copy.deepcopy(test_conf))
    orch.__create_networks__()
    nets = [
        x.name
        for x in orch.client.networks.list(
            filters={
                "label": f"nacl_{test_conf['formula']}=nacl_{test_conf['scenario']}"
            }
        )
    ]
    assert (
        f'nacl_{test_conf["formula"]}_{test_conf["scenario"]}_{test_conf["instances"][0]["networks"][0]["name"]}'
        in nets
    )
    assert (
        f'nacl_{test_conf["formula"]}_{test_conf["scenario"]}_{test_conf["instances"][0]["networks"][1]["name"]}'
        in nets
    )
    assert len(nets) == 2


def test_docker_start_containers(reset_dir) -> None:
    test_conf = parse_config(load_test_config("tests/data/test_confs/test1.yml"))
    orch = Docker(copy.deepcopy(test_conf))
    orch.__pull_images__()
    orch.__start_containers__()
    conts = [
        x.name
        for x in orch.client.containers.list(
            all=True,
            filters={
                "label": f"nacl_{test_conf['formula']}=nacl_{test_conf['scenario']}"
            },
        )
    ]
    assert len(conts) == 2
    assert (
        f'nacl_{test_conf["formula"]}_{test_conf["scenario"]}_{test_conf["instances"][0]["name"]}'
        in conts
    )
    assert (
        f'nacl_{test_conf["formula"]}_{test_conf["scenario"]}_{test_conf["instances"][1]["name"]}'
        in conts
    )
    if not NO_CLEANUP:
        [
            x.remove(force=True)
            for x in orch.client.containers.list(
                all=True,
                filters={
                    "label": f"nacl_{test_conf['formula']}=nacl_{test_conf['scenario']}"
                },
            )
        ]


def test_docker_create_image(reset_dir) -> None:
    test_conf = parse_config(
        load_test_config("tests/data/test_confs_dockerfile/test1.yml")
    )
    os.chdir("tests/data/test_confs_dockerfile")
    test_conf["running_tmp_dir"] = "/tmp/nacl/"
    orch = Docker(copy.deepcopy(test_conf))
    orch.__build_custom_image__(test_conf["instances"][0])
    images = []
    for img in orch.client.images.list():
        for tag in img.tags:
            images.append(tag)
    assert (
        f"nacl_{test_conf['formula']}_{test_conf['scenario']}_{test_conf['instances'][0]['name']}:latest"
        in images
    )


def test_docker_bootstrap(reset_dir) -> None:
    test_conf = parse_config(
        load_test_config("tests/data/test_confs_dockerfile/test1.yml")
    )
    print(test_conf)
    os.chdir("tests/data/test_confs_dockerfile")
    test_conf["running_tmp_dir"] = "/tmp/nacl/"
    nacl.utils.copy_srv_dir(
        test_conf["running_tmp_dir"], test_conf["formula"], os.getcwd()
    )
    orch = Docker(copy.deepcopy(test_conf))
    orch.__build_custom_image__(test_conf["instances"][0])
    conts = orch.__start_containers__()
    orch.__bootstrap_instances__(conts)
    out = conts[0].exec_run("systemctl status salt-minion")
    assert "Active: active (running)" in str(out.output)
    out = conts[0].exec_run("cat /etc/salt/minion")
    assert "file_client: local" in str(out.output)
    if not NO_CLEANUP:
        [x.remove(force=True) for x in conts]


def test_docker_orchestrate(reset_dir) -> None:
    test_conf = parse_config(
        load_test_config("tests/data/test_confs_dockerfile/test2.yml")
    )
    os.chdir("tests/data/test_confs_dockerfile")
    test_conf["running_tmp_dir"] = "/tmp/nacl/"
    nacl.utils.copy_srv_dir(
        test_conf["running_tmp_dir"], test_conf["formula"], os.getcwd()
    )
    orch = Docker(copy.deepcopy(test_conf))
    conts = orch.orchestrate()
    assert len(conts) == 2
    if not NO_CLEANUP:
        [orch.client.containers.get(x).remove(force=True) for x in conts]
