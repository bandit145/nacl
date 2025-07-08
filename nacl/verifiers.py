import subprocess
import sys
import nacl.orchestrators


class Verifier:
    def __init__(
        self, config: dict, orchestrator: nacl.orchestrators.Orchestrator
    ) -> None:
        self.config = config
        self.scenario_dir = orchestrator.scenario_dir

    def run(self) -> None:
        pass


class Testinfra(Verifier):
    def __init__(
        self, config: dict, orchestrator: nacl.orchestrators.Orchestrator
    ) -> None:
        super().__init__(config, orchestrator)
        match orchestrator:
            case nacl.orchestrators.Vagrant():
                self.inventory = [f"ssh://{x[0]}" for x in orchestrator.get_inventory()]
                self.extra_options = "--ssh-config={self.scenario_dir}/ssh_config"
            case nacl.orchestrators.Docker():
                self.inventory = [f"docker://nacl_{self.config['formula']}_{self.config['scenario']}_{x[0]}" for x in orchestrator.get_inventory()]
                self.extra_options = ""

    def run(self) -> None:
        proc = subprocess.run(
            f'python -m pytest {self.extra_options} --hosts={",".join(self.inventory)} tests/',
            shell=True,
            cwd=f"{self.config['running_tmp_dir']}/formulas/{self.config['formula']}/nacl/{self.config['scenario']}",
        )
        if proc.returncode != 0:
            sys.exit(proc.returncode)
