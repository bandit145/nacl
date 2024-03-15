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
        self.inventory = [
            f"ssh://{x}" for x in orchestrator.get_inventory()
        ]

    def run(self) -> None:
        proc = subprocess.run(
            f'python -m pytest --ssh-config={self.scenario_dir}/ssh_config --hosts={",".join(self.inventory)} tests/',
            shell=True,
            cwd=f"{self.config['running_tmp_dir']}/formulas/{self.config['formula']}/nacl/{self.config['scenario']}"
        )
        if proc.returncode != 0:
            sys.exit(proc.returncode)
