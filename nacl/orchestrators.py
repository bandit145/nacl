import docker


class Docker:

    __conf_schema__ = {
        "detached": True,
        "auto_remove": True,
        "command": {"type": str, "required": False},
        "cap_add": {"type": list[str], "required": False},
        "environment": {"type": list[str], "required": False},
        "dns_search": {"type": str, "required": False},
        "extra_hosts": {"type": dict, "required": False},
        "volumes": {"type": list, "required": False},
        "privileged": {"type": bool, "required": False},
        "ports": {"type": dict, "required": False},
    }

    def __init__(self, config: dict) -> None:
        self.config = config
        self.client = docker.from_env()
        self.state = {"containers": [], "networks": []}  # type: dict

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
        for instance in self.config["instances"]:
            for net in instance["networks"]:
                net["name"] = f'nacl_{self.config["formula"]}_{net["name"]}'
                if net["name"] not in cur_networks:
                    required_networks.append(net)
        if len(required_networks) > 0:
            print(f'> Creating required networks nacl_{net["name"]}')
        for net in required_networks:
            if net["name"] not in self.state["networks"]:
                print(f'==> Creating network {net["name"]}')
                self.state["networks"].append(self.client.networks.create(**net).name)

    def __start_containers__(self):
        print("> Starting instances")
        for instance in self.config["instances"]:
            print(f'==> Starting instance {instance["name"]}')
            self.state["containers"].append(
                self.client.containers.run(instance["image"], **instance)
            )

    def orchestrate(self) -> None:
        self.__pull_images__()
        self.__create_networks__()
        self.__start_containers__()

    def cleanup(self) -> None:
        pass


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
