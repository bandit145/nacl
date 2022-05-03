from nacl.config import generate_instance_config, validate_config
import nacl.exceptions
from nacl.orchestrators import Docker
import pytest
import copy
import yaml


def load_test_config(path: str) -> dict:
    with open(path, "r") as config:
        return yaml.safe_load(config)


def test_validate_config() -> None:
    test_conf = load_test_config("tests/data/test_confs/test1.yml")
    validate_config(test_conf)
    broken_confg = copy.deepcopy(test_conf)
    del broken_confg["provider"]
    with pytest.raises(nacl.exceptions.ConfigException):
        validate_config(broken_confg)

    broken_confg = copy.deepcopy(test_conf)
    broken_confg["instances"][0]["cap_add"] = 1

    with pytest.raises(nacl.exceptions.ConfigException):
        validate_config(broken_confg)


def test_generate_instance_config() -> None:
    test_conf = load_test_config("tests/data/test_confs/test1.yml")
    ins_conf = generate_instance_config(test_conf)
    print(ins_conf)
    assert len(ins_conf[0].keys()) == 6
    assert ins_conf[0]["detach"]
    assert ins_conf[0]["prov_name"] == "nacl_nacl-test_default_box1"
    assert len(ins_conf[1].keys()) == 6
    assert ins_conf[1]["detach"]
    assert ins_conf[1]["prov_name"] == "nacl_nacl-test_default_box2"
