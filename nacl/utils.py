import os
import shutil
import nacl.templates


def create_tmp_dir(tmp_dir):
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)


def copy_srv_dir(tmp_dir: str, formula: str, formula_path: str) -> None:
    if not os.path.exists(f"/{tmp_dir}/formulas/"):
        os.mkdir(f"/{tmp_dir}/formulas/")
    if not os.path.exists(f"/{tmp_dir}/formulas/{formula}"):
        shutil.copytree(formula_path, f"/{tmp_dir}/formulas/{formula}")


def init_state(state: str):
    if not os.path.exists(state):
        os.mkdir(state)
        with open(f"{state}/init.sls") as init:
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
                    formula=formula, driver=driver, verifier=verifier, scenario=scenario
                )
            )
        if driver == "docker":
            with open(f"{path}/nacl/{scenario}/Dockerfile.base") as d_file:
                d_file.write(nacl.templates.DOCKER)
