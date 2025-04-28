import os
import subprocess
import sys

import shutil
import yaml
import json
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
    def login(self, host):
        pass

class Docker(Orchestrator):
    __conf_schema__ = {
        "image": {"type": str, "required": True},
        "docker_options": {"type": dict, "required": False},
    }

    def __init__(self, config: dict) -> None:
        import docker
        self.config = config
        self.scenario_dir = f"{self.config['running_tmp_dir']}docker/{self.config['formula']}/{self.config['scenario']}/nacl/"
        self.formula_dir = f"{self.config['running_tmp_dir']}/formulas"
        self.client = docker.from_env()
    
    def get_inventory(self) -> list[tuple[str]]:
        inventory = []
        for instance in self.config["instances"]:
            cont = self.client.containers.list(filters={"name":instance["prov_name"]})
            if cont == []:
                status = "Not created"
            elif os.path.exists(f"{self.config['running_tmp_dir']}/{self.config['provider']['name']}/{self.config['formula']}/{self.config['scenario']}/{instance['prov_name']}.prepared"):
                status = "Prepared"
            else:
                status = "Created"
            inventory.append((instance["prov_name"].split("_")[-1], status))

        return inventory

    def exec(self, name: str, cmd: str) -> subprocess.CompletedProcess:
        proc = subprocess.run(f"docker exec -it {name} {cmd}", shell=True)
        return proc

    def orchestrate(self) -> None:
        if not os.path.exists(self.scenario_dir):
            os.makedirs(self.scenario_dir)
        nets = self.client.networks.list(names=[f"nacl_{self.config['formula']}_{self.config['scenario']}"])  
        if nets == []:
            net = self.client.networks.create(f"nacl_{self.config['formula']}_{self.config['scenario']}")
        else:
            net = nets[0]
        master_config = {"pillar_roots": {"base": [f"/srv/salt/formulas/{self.config['formula']}/nacl/{self.config['scenario']}/pillar"]}, "file_roots": {"base": ["/srv/salt/formulas/{self.config['formula']}/nacl/{self.config['scenario']}/saltfs", "/srv/salt/formulas"]}, "auto_accept": True}
        master_config.update(self.config.get('master_config', {}))
        with open(f"{self.scenario_dir}/master", "w") as f:
            json.dump(master_config, f)
        master_container_options = {"tty": True, "tmpfs": {"/tmp":"", "/run": ""}, "volumes": [f"{self.formula_dir}:/srv/salt/formulas", f"{self.scenario_dir}:/srv/salt/data", f"{self.scenario_dir}/master:/etc/salt/master"], "name": f"nacl_{self.config['formula']}_{self.config['scenario']}_master", "labels": {"app": "nacl", "scenario": self.config["scenario"], "formula": self.config["formula"]}, "detach": True, "hostname": "master", "image": "salt:3006"}
        master_container_options.update(self.config.get("master_container_options", {}))
        master_container = self.client.containers.run(**master_container_options)
        while self.exec(f"nacl_{self.config['formula']}_{self.config['scenario']}_master", "salt '*' test.version").returncode != 0:
            time.sleep(1)
        net.connect(master_container, aliases=["master"])
        for instance in self.config["instances"]:
            minion_config = {"master": "master"}
            instance_container_options = {"tty": True, "tmpfs": {"/tmp":"", "/run": ""}, "volumes": [f"{self.scenario_dir}/{instance['prov_name']}_minion:/etc/salt/minion:z"], "name": instance["prov_name"], "labels": {"app": "nacl", "scenario": self.config["scenario"], "formula": self.config["formula"]}, "detach": True, "hostname": instance["prov_name"].split("_")[-1], "image": instance["image"]}
            instance_container_options.update(instance.get("docker_options", {}))
            with open(f"{self.scenario_dir}/{instance['prov_name']}_minion", "w") as f:
                json.dump(minion_config, f)
            cont = self.client.containers.run(**instance_container_options)
            net.connect(cont, aliases=[instance["prov_name"].split("_")[-1]])


    def login(self, host: str) -> None:
        if host == "":
            inv = self.get_inventory()
            if len(inv) > 1:
                print("More than one host exists in scenarios, please specify with --host which one you wish to connect to")
                return
            host = inv[0]
        subprocess.run(
            f"docker exec -it {host} /bin/bash",
            shell=True,
        )

    def cleanup(self) -> None:
        for instance in self.client.containers.list(filters={"label": ["app=nacl", f"formula={self.config['formula']}", f"scenario={self.config['scenario']}"]}):
            instance.remove(force=True)
        nets = self.client.networks.list(names=[f"nacl_{self.config['formula']}_{self.config['scenario']}"])  
        if nets != []:
            nets[0].remove()

        if os.path.exists(self.scenario_dir):
            shutil.rmtree(self.scenario_dir)
    

class Vagrant(Orchestrator):
    VAGRANT_FILE = """\n
    Vagrant.configure("2") do | config |
        {% for instance in instances %}
            config.vm.define "{{ instance.prov_name }}" do |{{ instance.prov_name }}|
                {{ instance.prov_name }}.vm.box = "{{ instance.box }}"
                {% if instance.bootstrap %}
                {{ instance.prov_name }}.vm.provision "shell", inline: "curl -L https://bootstrap.saltstack.com -o /bootstrap_script.sh && chmod +x /bootstrap_script.sh && /bootstrap_script.sh && echo 'file_client: local' >> /etc/salt/minion"
                {% endif %}
                {% if "grains" in grains and instance.prov_name | split('_') | last in grains.keys() %}
                {{ instance.prov_name }}.vm.provision "shell", inline: "echo {{ grains[intance.prov_name | split('_') | last] | to_pretty_yaml }} > /etc/salt/grains"
                {% endif %}
                {% for line in instance.instance_raw_config_args %}
                {{ instance.prov_name }}.{{ line }}
                {% endfor %}
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
    """
    __conf_schema__ = {
        "box": {"type": str, "required": True},
        "bootstrap": False,
        "converge": {"type": bool, "required": False},
        "provider_raw_config_args": {"type": list, "required": False},
        "instance_raw_config_args": {"type": list, "required": False}
    }

    def __init__(self, config: dict) -> None:
        import vagrant
        self.config = config
        self.scenario_dir = f"{self.config['running_tmp_dir']}vagrant/{self.config['formula']}/{self.config['scenario']}/nacl/"
        self.formula_dir = f"{self.config['running_tmp_dir']}/formulas"
        self.vagrant = vagrant.Vagrant(
            self.scenario_dir, quiet_stdout=False, quiet_stderr=False
        )

    def get_inventory(self) -> list[tuple[str]]:
        inventory = []
        if not os.path.exists(f"{self.scenario_dir}/Vagrantfile"):
            for instance in self.config["instances"]:
                inventory.append((instance["prov_name"].split("_")[-1], "Not created"))
        else:
            for instance in self.vagrant.status():
                if os.path.exists(f"{self.config['running_tmp_dir']}/{self.config['provider']['name']}/{self.config['formula']}/{self.config['scenario']}/{instance['prov_name']}.prepared"):
                    status = "Prepared"
                else:
                    status = x.state
                inventory.append((instance.name.split("_")[-1], status))

        return inventory

    def orchestrate(self) -> None:
        if not os.path.exists(self.scenario_dir):
            os.makedirs(self.scenario_dir)
        vagrant_template = Environment(loader=BaseLoader).from_string(
            Vagrant.VAGRANT_FILE
        )
        data = vagrant_template.render(
            instances=self.config["instances"],
            formula_name=self.config["formula"],
            scenario_name=self.config["scenario"],
            host_dir=self.formula_dir,
            provider=self.config["provider"]["provider"]["name"],
            salt_exec_mode=self.config["salt_exec_mode"],
        )
        with open(f"{self.scenario_dir}/Vagrantfile", "w") as vf:
            vf.write(data)
        self.vagrant.up()
        if self.config["salt_exec_mode"] == "salt-ssh":
            roster = {}
            master = {}
            master["file_roots"] = dict(base=[self.formula_dir, f"{self.formula_dir}/{self.config['formula']}/nacl/{self.config['scenario']}"] + self.config.get("extra_file_roots", []))
            master["pillar_roots"] = dict(
                base=[
                    f"{self.formula_dir}/{self.config['formula']}/nacl/{self.config['scenario']}/pillar"
                ]
            )
            ssh_config_full = ""
            master.update(self.config['master_config'])
            for vm in self.config["instances"]:
                ssh_config = self.vagrant.ssh_config(vm_name=vm["prov_name"])
                ssh_port = re.findall(r"\sPort (\d*)", ssh_config)[0]
                ident_file = re.findall(r"\sIdentityFile (.*)", ssh_config)[0]
                roster[vm["prov_name"]] = dict(
                    host="127.0.0.1", user="vagrant", port=ssh_port, sudo=True, priv=ident_file
                )
                ssh_config_full += ssh_config
            with open(f"{self.scenario_dir}/roster", "w") as roster_file:
                roster_file.write(yaml.dump(roster))
            salt_config = {}
            salt_config["salt-ssh"] = dict(
                roster_file=f"{self.scenario_dir}roster",
                config_dir=self.scenario_dir,
                log_file=f"{self.scenario_dir}salt_log.txt",
                ssh_log_file=f"{self.scenario_dir}salt_ssh_log.txt",
                pki_dir=f"{self.scenario_dir}pki",
                cache_dir=f"{self.scenario_dir}cache",
                ssh_options=["StrictHostKeyChecking=no"],
                ssh_priv=""
            )
            with open(f"{self.scenario_dir}/Saltfile", "w") as salt_file:
                salt_file.write(yaml.dump(salt_config))
            with open(f"{self.scenario_dir}master", "w") as master_file:
                master_file.write(yaml.dump(master))
            with open(f"{self.scenario_dir}ssh_config", "w") as ssh_config_file:
                ssh_config_file.write(ssh_config_full)

    def login(self, host: str) -> None:
        if host == "":
            inv = self.get_inventory()
            if len(inv) > 1:
                print("More than one host exists in scenarios, please specify with --host which one you wish to connect to")
                return
            host = inv[0].split("_")[-1]
        subprocess.run(
            f"vagrant ssh nacl_{self.config['formula']}_{self.config['scenario']}_{host}",
            shell=True,
            cwd=self.scenario_dir,
        )

    def cleanup(self) -> None:
        if os.path.exists(f"{self.scenario_dir}/Vagrantfile"):
            self.vagrant.destroy()
        if os.path.exists(self.scenario_dir):
            shutil.rmtree(self.scenario_dir)
