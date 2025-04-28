import os

import yaml

import nacl.orchestrators
from nacl.exceptions import ConfigException, ConfigFileNotFound

TMP_DIR = f'{os.getenv("HOME")}/.nacl/'

PHASES = ["destroy", "lint", "create", "prepare","converge", "idempotence", "verify"]

SCHEMA = {
    "provider": {"required": True, "type": dict},
    "instances": {"required": True, "type": list},
    "formula": {"required": True, "type": str},
    "scenario": {"required": True, "type": str},
    "verifier": {"required": True, "type": str},
    "grains": {"required": False, "type": dict},
    "phases": {"required": False, "type": list},
    "extra_file_roots": {"required": False, "type": list},
    "master_config": {"required": True, "type": dict},
    "salt_exec_mode": {"required": True, "type": str, "options": ["salt-ssh", "salt-master"]},
}


# bad validator that is not generic but whatever. Brain no worky today.
def validate_config(config: dict, schema=SCHEMA) -> None:
    for k, v in schema.items():
        if v["required"] and k not in config.keys() and 'enabled':
            raise ConfigException(f"Missing required key {k}")
        elif k in config.keys() and v["type"] != type(config[k]):
            raise ConfigException(
                f"Incorrect type for {k} \"{type(config[k])}\" should be {v['type']}"
            )
        elif "options" in v and config[k] not in v["options"]:
            raise ConfigException(
                f"Option provided for {k} not allowed. Allowable selections are: {v['options']}"
            )
    prov_name = list(config["provider"]["name"])
    prov_name[0] = prov_name[0].upper()
    instance_schema = getattr(nacl.orchestrators, "".join(prov_name)).__conf_schema__
    for instance in config["instances"]:
        for k, v in instance_schema.items():
            if type(v) == dict:
                if v["required"] and k not in instance.keys():
                    raise ConfigException(
                        f"Missing required key in instance config {k}"
                    )
                elif k in instance.keys() and v["type"] != type(instance[k]):
                    raise ConfigException(
                        f"Incorrect type for provider.instances.{k} \"{type(instance[k])}\" should be {v['type']}"
                    )


def generate_instance_config(config: dict) -> list[dict]:
    new_instance_config = []
    prov_name = list(config["provider"]["name"])
    prov_name[0] = prov_name[0].upper()
    schema = getattr(nacl.orchestrators, "".join(prov_name)).__conf_schema__
    for instance in config["instances"]:
        new_ins = {}
        for k, v in schema.items():
            if type(v) != dict:
                new_ins[k] = v
            elif k in instance.keys():
                new_ins[k] = instance[k]
        new_ins[
            "prov_name"
        ] = f'nacl_{config["formula"]}_{config["scenario"]}_{instance["name"]}'
        new_instance_config.append(new_ins)
    return new_instance_config


def parse_config(raw_config: dict) -> dict:
    validate_config(raw_config)
    raw_config["instances"] = generate_instance_config(raw_config)
    raw_config["running_tmp_dir"] = TMP_DIR
    return raw_config


def get_config(scenario: str) -> dict:
    try:
        with open(f"nacl/{scenario}/nacl.yml", "r") as nacl_conf:
            return yaml.safe_load(nacl_conf)
    except FileNotFoundError:
        raise ConfigFileNotFound(f"Could not find/read {scenario}/nacl.yml")
