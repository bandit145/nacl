from nacl.orchestrators import Docker
from nacl.config import parse_config
import docker
import yaml
import copy


def load_test_config(path: str) -> dict:
    with open(path, "r") as config:
        return yaml.safe_load(config)


def test_docker_image_pull() -> None:
    test_conf = parse_config(load_test_config("tests/data/test_confs/test1.yml"))
    orch = Docker(test_conf)
    orch.__pull_images__()
    image = orch.client.images.get(test_conf["instances"][0]["image"])
    assert isinstance(image, docker.models.images.Image)


def test_docker_create_network() -> None:
    test_conf = parse_config(load_test_config("tests/data/test_confs/test1.yml"))
    orch = Docker(copy.deepcopy(test_conf))
    orch.__create_networks__()
    nets = [x.name for x in orch.client.networks.list(filters={"type": "custom"})]
    assert (
        f'nacl_{test_conf["formula"]}_{test_conf["instances"][0]["networks"][0]["name"]}'
        in nets
    )
    assert (
        f'nacl_{test_conf["formula"]}_{test_conf["instances"][0]["networks"][1]["name"]}'
        in nets
    )
    assert len(nets) == 2
    # ensure internal state is updated
    assert len(orch.state["networks"]) == 2


def test_docker_start_containers() -> None:
    test_conf = parse_config(load_test_config("tests/data/test_confs/test1.yml"))
    orch = Docker(copy.deepcopy(test_conf))
    orch.__pull_images__()
    orch.__start_containers__()
    conts = [x.name for x in orch.state["containers"]]
    assert len(orch.state["containers"]) == 2
    assert f'nacl_{test_conf["formula"]}_{test_conf["instances"][0]["name"]}' in conts
    assert f'nacl_{test_conf["formula"]}_{test_conf["instances"][1]["name"]}' in conts
