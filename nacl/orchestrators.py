import os
import subprocess
import sys

import vagrant
import shutil
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
    def login(self, host):
        pass


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
        self.config = config
        self.scenario_dir = f"{self.config['running_tmp_dir']}vagrant/{self.config['formula']}/{self.config['scenario']}/nacl/"
        self.formula_dir = f"{self.config['running_tmp_dir']}/formulas"
        self.vagrant = vagrant.Vagrant(
            self.scenario_dir, quiet_stdout=False, quiet_stderr=False
        )

    def get_inventory(self) -> list[str]:
        if not os.path.exists(f"{self.scenario_dir}/Vagrantfile"):
            return []
        return [x.name for x in self.vagrant.status() if x.state == "running"]

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
