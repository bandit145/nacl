import os
import subprocess
import sys

import vagrant
import docker
import yaml
import re
from abc import ABC, abstractmethod
from jinja2 import Environment, BaseLoader, select_autoescape

from nacl.exceptions import BootStrapException, NoHostSpecified


class Orchestrator(ABC):
    connection_type = ""
    @abstractmethod
    def orchestrate(self):
        pass
    @abstractmethod
    def cleanup(self):
        pass
    @abstractmethod
    def get_inventory(self):
        pass
    @abstractmethod
    def converge(self):
        pass
    @abstractmethod
    def login(self, host):
        pass


class Docker(Orchestrator):

    connection_type = "docker"

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

    def get_inventory(self) -> list[str]:
        return [
            x.name
            for x in self.client.containers.list(
                filters={
                    "label": f"nacl_{self.config['formula']}=nacl_{self.config['scenario']}"
                }
            )
        ]

    def __create_networks__(self) -> None:
        cur_networks = [x.name for x in self.client.networks.list()]
        required_networks = []
        # Do not modify config here, fix this
        for instance in self.config["instances"]:
            if "networks" in instance.keys():
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
            cont = self.client.containers.list(filters=dict(name=instance["prov_name"]))
            if cont != []:
                print(
                    f'==> Instance {instance["prov_name"]} already created and started'
                )
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
            if "active" not in str(out.output):
                print("> Bootstrapping instances with Salt")
                print(f"==> Bootstrapping instance {cont.name.split('_')[-1]}")
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
                    f"bash -o pipefail -c \"echo 'file_roots:\n  base: [/srv/salt/, /srv/formulas/{self.config['formula']}]\npillar_roots:\n  base: [/srv/formulas/{self.config['formula']}/nacl/{self.config['scenario']}/pillar/]' >> /etc/salt/minion\""
                )
                if out.exit_code != 0:
                    print(
                        f"==> Error bootstrapping instance {cont.name.split('_')[-1]}. {out.output}",
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
            # these two always run in case you are using a a container that has it running, so grains get applied and picked up
            if (
                "grains" in self.config.keys()
                and cont.name.split("_")[-1] in self.config["grains"].keys()
            ):
                out = cont.exec_run(
                    "bash -c 'echo \"$GRAINS\" > /etc/salt/grains'",
                    environment={
                        "GRAINS": yaml.dump(
                            self.config["grains"][cont.name.split("_")[-1]]
                        )
                    },
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

    def converge(self) -> str:
        print("> Applying state")
        for cont in self.client.containers.list(
            filters={
                "label": f"nacl_{self.config['formula']}=nacl_{self.config['scenario']}"
            }
        ):
            print(f"==> Applying state on {cont.name.split('_')[-1]}")
            out = cont.exec_run("salt-call --local state.apply", stream=True)
            output = ""
            for line in out.output:
                output += line.decode()
                print(line.decode())
        return output

    def login(self, host: str) -> None:
        conts = self.client.containers.list(
            filters={
                "label": f"nacl_{self.config['formula']}=nacl_{self.config['scenario']}"
            }
        )
        if len(conts) > 1 and not host:
            raise NoHostSpecified(
                "You must specify a host for environments with multiple hosts"
            )
        elif len(conts) == 1:
            subprocess.run(f"docker exec -it {conts[0].name} /bin/bash", shell=True)
        else:
            name = [x for x in self.config["instances"] if x.name == host][0]
            subprocess.run(f"docker exec -it {name} /bin/bash", shell=True)

    def orchestrate(self) -> list:
        self.__pull_images__()
        self.__create_networks__()
        containers = self.__start_containers__()
        self.__bootstrap_instances__(containers)
        return [x.name for x in containers]

    def cleanup(self) -> None:
        print("> Cleaning up")
        for cont in self.client.containers.list(
            all=True,
            filters={
                "label": f"nacl_{self.config['formula']}=nacl_{self.config['scenario']}"
            },
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
    VAGRANT_FILE = '''\n
    Vagrant.configure("2") do | config |
        {% for instance in instances %}
            config.vm.define "{{ instance.prov_name }}" do |{{ instance.prov_name }}|
                {{ instance.prov_name }}.vm.box = "{{ instance.box }}"
                {{ instance.prov_name }}.vm.synced_folder "{{ host_dir }}", "/srv/formulas/"
                {% if instance.bootstrap %}
                {{ instance.prov_name }}.vm.provision "shell", inline: "curl -L https://bootstrap.saltstack.com -o /bootstrap_script.sh && chmod +x /bootstrap_script.sh && /bootstrap_script.sh && echo 'file_client: local' >> /etc/salt/minion"
                {% endif %}
                {% if salt_exec_mode == 'masterless_minion '%}
                {{ instance.prov_name }}.vm.provision "shell", inline: "echo 'features:\\n  x509_v2: true\\nfile_roots:\\n  base: [/srv/salt/, /srv/formulas/]\\npillar_roots:\\n  base: [/srv/formulas/{{ formula_name }}/nacl/{{ scenario_name }}/pillar/]' >> /etc/salt/minion"
                {{ instance.prov_name }}.vm.provision "shell", inline: "mkdir /srv/salt/ && echo 'base: \\n  \\"*\\":\\n    - {{ formula_name }}' >> /srv/salt/top.sls"
                {% if "grains" in grains and instance.prov_name | split('_') | last in grains.keys() %}
                {{ instance.prov_name }}.vm.provision "shell", inline: "echo {{ grains[intance.prov_name | split('_') | last] | to_pretty_yaml }} > /etc/salt/grains"
                {% endif %}
                {% endif %}
                {{ instance.prov_name }}.vm.provider "{{ provider }}" do |{{ provider }}, override|
                {% if 'provider_raw_config_args' in instance %}
                {% for line in instance.provider_raw_config_args %}
                    {{ provider }}.{{ line }}
                {% endfor %}
                {% endif %}
                end   
            end
        {% endfor %}
    end
    '''
    __conf_schema__ = {
            "box": {"type": str, "required": True},
            "bootstrap": False,
            "provider_raw_config_args": {"type": list, "required": False}
            }
    def __init__(self, config: dict) -> None:
        self.config = config
        self.scenario_dir = f"{self.config['running_tmp_dir']}vagrant/{self.config['formula']}/{self.config['scenario']}/nacl/"
        self.formula_dir = f"{self.config['running_tmp_dir']}/formulas"
        self.vagrant = vagrant.Vagrant(self.scenario_dir, quiet_stdout=False, quiet_stderr=False)

    def get_inventory(self) -> list[str]:
        if not os.path.exists(f"{self.scenario_dir}/Vagrantfile"):
            return []
        return [x.name for x in self.vagrant.status() if x.state == 'running']

    def orchestrate(self) -> None:
        if not os.path.exists(self.scenario_dir):
            os.makedirs(self.scenario_dir)
        vagrant_template = Environment(loader=BaseLoader).from_string(Vagrant.VAGRANT_FILE)
        data = vagrant_template.render(instances=self.config['instances'], formula_name=self.config['formula'], scenario_name=self.config['scenario'],
            host_dir=self.formula_dir, provider=self.config['provider']['provider']['name'], salt_exec_mode=self.config['salt_exec_mode'])
        with open(f"{self.scenario_dir}/Vagrantfile", "w") as vf:
            vf.write(data)
        self.vagrant.up()
        if self.config['salt_exec_mode'] == 'salt-ssh':
            roster = {}
            master = {}
            master["file_roots"] = dict(base=[self.formula_dir])
            master["pillar_roots"] = dict(base=[f"{self.formula_dir}/{self.config['formula']}/nacl/{self.config['scenario']}/pillar"])
            ident_file = ''
            for vm in self.config['instances']:
                ssh_config = self.vagrant.ssh_config(vm_name=vm['prov_name'])
                ssh_port = re.findall(r'\sPort (\d*)', ssh_config)[0]
                if ident_file == '':
                    ident_file = re.findall(r'\sIdentityFile (.*)', ssh_config)[0]
                roster[vm['prov_name']] = dict(host="127.0.0.1", user="vagrant", port=ssh_port, sudo=True)
            with open(f"{self.scenario_dir}/roster", "w") as roster_file:
                roster_file.write(yaml.dump(roster))
            salt_config = {}
            salt_config['salt-ssh'] = dict(roster_file=f"{self.scenario_dir}roster", 
                config_dir=self.scenario_dir, log_file=f"{self.scenario_dir}salt_log.txt", 
                ssh_log_file=f"{self.scenario_dir}salt_ssh_log.txt", pki_dir=f"{self.scenario_dir}pki", cache_dir=f"{self.scenario_dir}cache", ssh_priv=ident_file)
            with open(f"{self.scenario_dir}/Saltfile", "w") as salt_file:
                salt_file.write(yaml.dump(salt_config))
            with open(f"{self.scenario_dir}master", "w") as master_file:
                master_file.write(yaml.dump(master))

    
    def login(self, host: str) -> None:
        subprocess.run(f"vagrant ssh nacl_{self.config['formula']}_{self.config['scenario']}_{host}", shell=True, cwd=self.scenario_dir)

    def cleanup(self) -> None:
        if not os.path.exists(f"{self.scenario_dir}/Vagrantfile"):
            return []
        self.vagrant.destroy()

    def converge(self) -> str:
        print("> Applying state")
        for vm in self.config['instances']:
            print(f"==> Applying state on {vm['prov_name'].split('_')[-1]}")
            try:
                if self.config['salt_exec_mode'] == 'salt-ssh':
                    output = subprocess.run(f'salt-ssh {vm["prov_name"]} --saltfile={self.scenario_dir}Saltfile -i state.sls {self.config["formula"]}', shell=True)
                else:
                    output = self.vagrant.ssh(vm_name=vm['prov_name'], command="sudo salt-call --local state.apply")
            except subprocess.CalledProcessError as error:
                output = error.output.decode()
        return output


