import subprocess
import nacl.orchestrators

class Verifier:

    def __init__(self, config: dict, ochestrator: nacl.orchestrators.Orchestrator) -> None:
        self.inventory = [f"{ochestrator.connection_type}://{x}" for x in ochestrator.get_inventory()]
        self.config = config

    def run(self) -> None:
        pass


class Testinfra(Verifier):
    
    def __init__(self, config: dict, orchestrator: nacl.orchestrators.Orchestrator) -> None:
        super().__init__(config, orchestrator)

    def run(self) -> None:
        subprocess.run(f'py.test --hosts={",".join(self.inventory)} nacl/{self.config["scenario"]}/tests/', shell=True)