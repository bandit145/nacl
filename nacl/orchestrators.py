import docker


class Docker:

    __conf_schema__ = {
        "detach": True,
        "auto_remove": False,
        "command": {"type": str, "required": False},
        "cap_add": {"type": list, "required": False},
        "environment": {"type": list, "required": False},
        "dns_search": {"type": str, "required": False},
        "extra_hosts": {"type": dict, "required": False},
        "volumes": {"type": list, "required": False},
        "privileged": {"type": bool, "required": False},
        "ports": {"type": dict, "required": False},
        "networks": {"type": list, "required": False},
        "name": {"type": str, "required": True},
        "image": {"type": str, "required": True},
    }

    def __init__(self, config: dict) -> None:
        self.config = config
        self.client = docker.from_env()

    def __pull_images__(self) -> None:
        print("> Pulling container images")
        for instance in self.config["instances"]:
            repo, tag = instance["image"].split(":")
            if not tag:
                tag = "latest"
            print(f'==> Pulling image {instance["image"]}')
            self.client.images.pull(repo, tag=tag)

    def __create_networks__(self) -> None:
        cur_networks = [x.name for x in self.client.networks.list()]
        required_networks = []
        # Do not modify config here, fix this
        for instance in self.config["instances"]:
            for net in instance["networks"]:
                net["name"] = f'nacl_{self.config["formula"]}_{net["name"]}'
                if net["name"] not in cur_networks:
                    required_networks.append(net)
        if len(required_networks) > 0:
            print(f'> Creating required networks nacl_{net["name"]}')
        for net in required_networks:
            if net["name"] not in [x.name for x in self.client.networks.list()]:
                print(f'==> Creating network {net["name"]}')
                print({**net, **{"labels":{f"nacl_formula_{self.config['formula']}": f"nacl_scenario_{self.config['scenario']}"}}})
                self.client.networks.create(**{**net, **{"labels":{f"nacl_formula_{self.config['formula']}": f"nacl_scenario_{self.config['scenario']}"}}})

    def __start_containers__(self):
        print("> Starting instances")
        for instance in self.config["instances"]:
            print(f'==> Starting instance {instance["name"]}')
            cont_dict = {
                k: v for (k, v) in instance.items() if k != "networks" and k != "name"
            }
            cont_dict["name"] = cont_dict["prov_name"]
            del cont_dict["prov_name"]
            self.client.containers.run(**{**cont_dict, **{"labels": {f"nacl_formula_{self.config['formula']}": f"nacl_scenario_{self.config['scenario']}"}}})

    def orchestrate(self) -> None:
        self.__pull_images__()
        self.__create_networks__()
        self.__start_containers__()

    def cleanup(self) -> None:
        for cont in self.client.containers.list(filters={"label": f"nacl_formula_{self.config['formula']}=nacl_scenario_{self.config['scenario']}"}):
            cont.remove(force=True)

        for net in self.client.networks.list(filters={"label": f"nacl_formula_{self.config['formula']}=nacl_scenario_{self.config['scenario']}"}):
            self.client.networks.remove()


class Vagrant:
    def __init__(self, config: dict) -> None:
        self.config = config

    def __generate_vagrant_config__(self) -> dict:
        return {}

    def orchestrate(self) -> None:
        pass

    def cleanup(self) -> None:
        pass


class Vmware:
    def __init__(self, config: dict) -> None:
        self.config = config

    def orchestrate(self) -> None:
        pass

    def cleanup(self) -> None:
        pass
