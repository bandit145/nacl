import nacl.orchestrators
from nacl.exceptions import ConfigException

SCHEMA = {
    "provider": {"required": True, "type": str},
    "instances": {"required": True, "type": list},
    "formula": {"required": True, "type": str},
}

# bad validator that is not generic but whatever. Brain no worky today.
def validate_config(config: dict, schema=SCHEMA) -> None:
    for k, v in schema.items():
        if v["required"] and k not in config.keys():
            raise ConfigException(f"Missing required key {k}")
        elif v["type"] != type(config[k]):
            raise ConfigException(
                f"Incorrect type for {k} \"{type(config[k])}\" should be {v['type']}"
            )
    prov_name = list(config["provider"])
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
    prov_name = list(config["provider"])
    prov_name[0] = prov_name[0].upper()
    schema = getattr(nacl.orchestrators, "".join(prov_name)).__conf_schema__
    for instance in config["instances"]:
        new_ins = {}
        for k, v in schema.items():
            if type(v) != dict:
                new_ins[k] = v
            elif k in instance.keys():
                new_ins[k] = instance[k]
        new_ins["prov_name"] = f'nacl_{config["formula"]}_{instance["name"]}'
        new_instance_config.append(new_ins)
    return new_instance_config


def parse_config(raw_config: dict):
    validate_config(raw_config)
    raw_config["instances"] = generate_instance_config(raw_config)
    return raw_config
