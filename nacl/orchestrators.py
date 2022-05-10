import docker
import sys
import os
import subprocess
from nacl.exceptions import BootStrapException
import yaml


class Orchestrator:
    def orchestrate(self):
        pass

    def cleanup(self):
        pass


class Docker(Orchestrator):

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
        if not os.path.exists(
            f"{self.config['running_tmp_dir']}/docker/{self.config['formula']}/{self.config['scenario']}/nacl/"
        ):
            os.makedirs(
                f"{self.config['running_tmp_dir']}/docker/{self.config['formula']}/{self.config['scenario']}/nacl/"
            )
        new_file = [f"FROM {instance['image']}\n"]
        with open(f"Dockerfile.base", "r") as dfile:
            new_file = new_file + dfile.readlines()
        with open(
            f"{self.config['running_tmp_dir']}/docker/{self.config['formula']}/{self.config['scenario']}/nacl/Dockerfile",
            "w",
        ) as ndfile:
            ndfile.write("".join(new_file))
        self.client.images.build(
            path=f"{self.config['running_tmp_dir']}/docker/{self.config['formula']}/{self.config['scenario']}/nacl/",
            forcerm=True,
            rm=True,
            tag=f"nacl_{self.config['formula']}_{self.config['scenario']}_{instance['name']}:latest",
        )

    def __pull_images__(self) -> None:
        print("> Pulling container images")
        for instance in self.config["instances"]:
            if "customize" in instance.keys():
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
            if 'networks' in instance.keys():
                for net in instance["networks"]:
                    net[
                        "name"
                    ] = f'nacl_{self.config["formula"]}_{self.config["scenario"]}_{net["name"]}'
                    if net["name"] not in cur_networks:
                        required_networks.append(net)
        if len(required_networks) > 0:
            print(f'> Creating required networks nacl_{net["name"]}')
        for net in required_networks:
            if net["name"] not in [x.name for x in self.client.networks.list()]:
                print(f'==> Creating network {net["name"]}')
                print(
                    {
                        **net,
                        **{
                            "labels": {
                                f"nacl_{self.config['formula']}": f"nacl_{self.config['scenario']}"
                            }
                        },
                    }
                )
                self.client.networks.create(
                    **{
                        **net,
                        **{
                            "labels": {
                                f"nacl_{self.config['formula']}": f"nacl_{self.config['scenario']}"
                            }
                        },
                    }
                )

    def __start_containers__(self) -> list[docker.models.containers.Container]:
        containers = []
        print("> Starting instances")
        for instance in self.config["instances"]:
            cont = self.client.containers.list(filters=dict(name=instance['prov_name']))
            if cont != []:
                print(f'==> Instance {instance["prov_name"]} already created and started')
                containers.append(cont[0])
            else:
                print(f'==> Starting instance {instance["name"]}')
                cont_dict = {
                    k: v
                    for (k, v) in instance.items()
                    if k != "networks" and k != "name" and k != "customize"
                }
                cont_dict["name"] = cont_dict["prov_name"]
                del cont_dict["prov_name"]
                if "volumes" in cont_dict.keys():
                    cont_dict["volumes"].append(
                        f'{self.config["running_tmp_dir"]}/formulas/:/srv/formulas:z'
                    )
                else:
                    cont_dict["volumes"] = [
                        f'{self.config["running_tmp_dir"]}/formulas/:/srv/formulas:z'
                    ]
                if "customize" in instance.keys():
                    cont_dict[
                        "image"
                    ] = f"nacl_{self.config['formula']}_{self.config['scenario']}_{instance['name']}:latest"
                containers.append(
                    self.client.containers.run(
                        **{
                            **cont_dict,
                            **{
                                "labels": {
                                    f"nacl_{self.config['formula']}": f"nacl_{self.config['scenario']}"
                                }
                            },
                        }
                    )
                )
        return containers

    # this will bootstrap an instance with local only minion
    # this might change in the future (maybe we create a temp master)
    def __bootstrap_instances__(self, containers):
        for cont in containers:
            out = cont.exec_run("systemctl status salt-minion")
            if 'active' not in str(out.output):
                print("> Bootstrapping instances with Salt")
                print(f"==> Bootstrapping instance {cont.name}")
                # out = cont.exec_run("bash -c \"set -o pipefail curl -L https://bootstrap.saltstack.com -o /bootstrap_script.sh && chmod +x /bootstrap_script.sh && /bootstrap_script.sh && echo 'file_client: local' >> /etc/salt/minion\"")
                out = cont.exec_run(
                    "bash -o pipefail -c \"curl -L https://bootstrap.saltstack.com -o /bootstrap_script.sh && chmod +x /bootstrap_script.sh && /bootstrap_script.sh && echo 'file_client: local' >> /etc/salt/minion\""
                )
                if out.exit_code != 0:
                    print(
                        f"==> Error bootstrapping instance {cont.name}. {out.output}",
                        file=sys.stderr,
                    )
                    raise BootStrapException()

                out = cont.exec_run(
                    f"bash -o pipefail -c \"echo 'file_roots:\n  base: [/srv/salt/, /srv/formulas/{self.config['formula']}]' >> /etc/salt/minion\""
                )
                if out.exit_code != 0:
                    print(
                        f"==> Error bootstrapping instance {cont.name}. {out.output}",
                        file=sys.stderr,
                    )
                    raise BootStrapException()
                out = cont.exec_run(
                    f'bash -o pipefail -c \'mkdir /srv/salt/ && echo "base: \n  \\"*\\":\n    - master" >> /srv/salt/top.sls\''
                )
                if out.exit_code != 0:
                    print(
                        f"==> Error bootstrapping instance {cont.name}. {out.output}",
                        file=sys.stderr,
                    )
                    raise BootStrapException()
                if (
                    "grains" in self.config.keys()
                    and cont.name.split('_')[-1] in self.config["grains"].keys()
                ):
                    out = cont.exec_run(
                        "bash -c 'echo \"$GRAINS\" > /etc/salt/grains'",
                        environment={"GRAINS": yaml.dump(self.config["grains"][cont.name.split('_')[-1]])},
                    )
                    if out.exit_code != 0:
                        print(
                            f"==> Error bootstrapping instance {cont.name}. {out.output}",
                            file=sys.stderr,
                        )
                        raise BootStrapException()
                out = cont.exec_run("systemctl restart salt-minion")
                if out.exit_code != 0:
                    print(
                        f"==> Error bootstrapping instance {cont.name}. {out.output}",
                        file=sys.stderr,
                    )
                    raise BootStrapException()

    def converge(self) -> None:
        print("> Applying state")
        for cont in  self.client.containers.list(
            filters={
                "label": f"nacl_{self.config['formula']}=nacl_{self.config['scenario']}"
            }):
            print(f"==> Applying state on {cont.name.split('_')[-1]}")
            out = cont.exec_run('salt-call --local state.apply', stream=True)
            for line in out.output:
                print(line.decode())

    def login(self, host: str) -> None:
        conts = self.client.containers.list(
            filters={
                "label": f"nacl_{self.config['formula']}=nacl_{self.config['scenario']}"
            })
        if len(conts) > 1 and not host:
            raise NoHostSpecified("You must specify a host for environments with multiple hosts")
        elif len(conts) == 1:
            subprocess.run(f'docker exec -it {conts[0].name} /bin/bash', shell=True)
        else:
            name = [x for x in self.config['instances'] if x.name == host][0]
            subprocess.run(f'docker exec -it {name} /bin/bash', shell=True)

    def orchestrate(self) -> None:
        self.__pull_images__()
        self.__create_networks__()
        containers = self.__start_containers__()
        self.__bootstrap_instances__(containers)
        return [x.name for x in containers]

    def cleanup(self) -> None:
        print(" > Cleaning up")
        for cont in self.client.containers.list(
            filters={
                "label": f"nacl_{self.config['formula']}=nacl_{self.config['scenario']}"
            }
        ):
            print(f'==> Removing container {cont.name.split("_")[-1]}')
            cont.remove(force=True)

        for net in self.client.networks.list(
            filters={
                "label": f"nacl_{self.config['formula']}=nacl_{self.config['scenario']}"
            }
        ):
            print(f"Removing network {net.name.split('_')[-1]}")
            net.remove()


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
