import docker
import sys
import os
from nacl.exceptions import BootStrapException


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
        "customize": {"type": bool, "required": False},
        "privileged": {"type": bool, "required": False},
        "tmpfs": {"type": dict, "required": False},
        "ports": {"type": dict, "required": False},
        "networks": {"type": list, "required": False},
        "name": {"type": str, "required": True},
        "image": {"type": str, "required": False},
    }

    def __init__(self, config: dict) -> None:
        self.config = config
        self.client = docker.from_env()

    def __build_custom_image__(self, instance) -> None:
        if not os.path.exists(f"{self.config['running_tmp_dir']}"):
            os.makedirs(f"{self.config['running_tmp_dir']}")
        new_file = [f"FROM {instance['image']}\n"]
        with open(f"{self.config['scenario_dir']}/Dockerfile.base", 'r') as dfile:
            new_file = new_file + dfile.readlines()
        with open(f"{self.config['running_tmp_dir']}/Dockerfile", 'w') as ndfile:
            ndfile.write(''.join(new_file))
        self.client.images.build(path=f"{self.config['running_tmp_dir']}", forcerm=True, rm=True, tag=f"nacl_scenario_{self.config['scenario']}_{instance['name']}:latest")

    def __pull_images__(self) -> None:
        print("> Pulling container images")
        for instance in self.config["instances"]:
            if 'customize' in instance.keys():
                self.__build_custom_image__(instance)
            else:
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

    def __start_containers__(self) -> list[docker.models.containers.Container]:
        containers = []
        print("> Starting instances")
        for instance in self.config["instances"]:
            print(f'==> Starting instance {instance["name"]}')
            cont_dict = {
                k: v for (k, v) in instance.items() if k != "networks" and k != "name" and k != "customize"
            }
            cont_dict["name"] = cont_dict["prov_name"]
            del cont_dict["prov_name"]
            if 'customize' in instance.keys():
                cont_dict["image"] = f"nacl_scenario_{self.config['scenario']}_{instance['name']}:latest"
            containers.append(self.client.containers.run(**{**cont_dict, **{"labels": {f"nacl_formula_{self.config['formula']}": f"nacl_scenario_{self.config['scenario']}"}}}))
        return containers

    # this will bootstrap an instance with local only minion
    # this might change in the future (maybe we create a temp master)
    def __bootstrap_instances__(self, containers):
        print("> Bootstrapping instances with Salt")
        for cont in containers:
            print(f"==> Bootstrapping instance {cont.name}")
            #out = cont.exec_run("bash -c \"set -o pipefail curl -L https://bootstrap.saltstack.com -o /bootstrap_script.sh && chmod +x /bootstrap_script.sh && /bootstrap_script.sh && echo 'file_client: local' >> /etc/salt/minion\"")
            out = cont.exec_run("bash -o pipefail -c \"curl -L https://bootstrap.saltstack.com -o /bootstrap_script.sh && chmod +x /bootstrap_script.sh && /bootstrap_script.sh && echo 'file_client: local' >> /etc/salt/minion && systemctl restart salt-minion\"")
            if out.exit_code != 0:
                print(f"==> Error bootstrapping instance {cont.name}. {out.output}", file=sys.stderr)
                raise BootStrapException()

    def orchestrate(self) -> None:
        self.__pull_images__()
        self.__create_networks__()
        containers = self.__start_containers__()
        self.__bootstrap_instances__(containers)

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
