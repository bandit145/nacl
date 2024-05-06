import os
import shutil

import nacl.templates
from nacl.exceptions import ScenarioExists


def create_tmp_dir(tmp_dir):
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)


def copy_srv_dir(tmp_dir: str, formula: str, formula_path: str) -> None:
    if not os.path.exists(tmp_dir):
        os.mkdir(tmp_dir)
    if not os.path.exists(f"/{tmp_dir}/formulas/"):
        os.mkdir(f"/{tmp_dir}/formulas")
    if os.path.exists(f"/{tmp_dir}/formulas/{formula}"):
        shutil.rmtree(f"/{tmp_dir}/formulas/{formula}")
    shutil.copytree(formula_path, f"/{tmp_dir}/formulas/{formula}")


def init_state(state: str, force=False):
    if not os.path.exists(state):
        os.mkdir(state)
    if not os.path.exists(f"{state}/init.sls") or force:
        with open(f"{state}/init.sls", "w") as init:
            init.write("")


def init_scenario(
    path: str, formula: str, driver: str, verifier: str, scenario="default"
) -> None:
    if not path:
        path = os.getcwd()
    if not os.path.exists(f"{path}/nacl/{scenario}"):
        os.makedirs(f"{path}/nacl/{scenario}")
        with open(f"{path}/nacl/{scenario}/nacl.yml", "w") as nacl_conf:
            nacl_conf.write(
                nacl.templates.CONFIG.format(
                    formula=formula,
                    provider=driver,
                    verifier=verifier,
                    scenario=scenario,
                )
            )
        os.mkdir(f"{path}/nacl/{scenario}/pillar")
        with open(f"{path}/nacl/{scenario}/pillar/top.sls", "w") as pillar_top:
            pillar_top.write(nacl.templates.TOP_SLS)
        with open(f"{path}/nacl/{scenario}/pillar/default.sls", "w") as default_pillar:
            default_pillar.write("")
    else:
        raise ScenarioExists(f"{scenario} scenario already exists")
