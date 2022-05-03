import os
import shutil


def create_tmp_dir(tmp_dir):
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)


def copy_srv_dir(tmp_dir: str, formula: str, formula_path: str) -> None:
    if not os.path.exists(f"/{tmp_dir}/formulas/"):
        os.mkdir(f"/{tmp_dir}/formulas/")
    if not os.path.exists(f"/{tmp_dir}/formulas/{formula}"):
        shutil.copytree(formula_path, f"/{tmp_dir}/formulas/{formula}")
