from nacl.config import generate_instance_config, validate_config
import nacl.exceptions
import pytest
import copy
import yaml
import os


def load_test_config(path: str) -> dict:
    with open(path, "r") as config:
        return yaml.safe_load(config)

def test_validate_config() -> None:
    print(os.getcwd())
    test_conf = load_test_config("tests/data/test_confs/test1.yml")
    validate_config(test_conf)
    broken_confg = copy.deepcopy(test_conf)
    del broken_confg["provider"]
    with pytest.raises(nacl.exceptions.ConfigException):
        validate_config(broken_confg)

    broken_confg = copy.deepcopy(test_conf)
    broken_confg["salt_exec_mode"] = "master"

    with pytest.raises(nacl.exceptions.ConfigException):
        validate_config(broken_confg)

#These are currently tested against the Vagrant provider
def test_generate_instance_config() -> None:
    test_conf = load_test_config("tests/data/test_confs/test1.yml")
    ins_conf = generate_instance_config(test_conf)
    assert len(ins_conf) == 2
    assert ins_conf[0]["prov_name"] == "nacl_nacl-test_default_box1"
    assert ins_conf[1]["prov_name"] == "nacl_nacl-test_default_box2"
