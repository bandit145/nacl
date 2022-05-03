import argparse
import nacl.orchestrators
import nacl.verifiers
import nacl.config
import nacl.utils
import os


def get_orchestrator(orch_name, config) -> nacl.orchestrators.Orchestrator:
    proper_name = list(orch_name)
    proper_name[0] = proper_name[0].upper()
    return getattr(nacl.orchestraters, "".join(proper_name))(config)


def get_verifier(verifier_name) -> nacl.verifiers.Verifier:
    proper_name = list(orch_name)
    proper_name[0] = proper_name[0].upper()
    return getattr(nacl.verifiers, "".join(proper_name))()


def create(args: Namespace, config: dict) -> None:
    orch = get_orchestrator(config["provider"], config)
    if not "nacl.yml" in os.listdir():
        os.chdir(f"nacl/{config['scenario']}")
    return orch.orchestrate()


def converge(args: Namespace, config: dict) -> None:
    orch = get_orchestrator(config["provider"], config)
    if not "nacl.yml" in os.listdir():
        os.chdir(f"nacl/{config['scenario']}")
    orch.converge()


def delete(args: Namespace, config: dict) -> None:
    orch = get_orchestrator(config["provider"], config)
    if not "nacl.yml" in os.listdir():
        os.chdir(f"nacl/{config['scenario']}")
    return orch.cleanup()


def verify(args: Namespace, config: dict) -> None:
    veri = get_verifier(config["verifier"])
    if not "nacl.yml" in os.listdir():
        os.chdir(f"nacl/{args.scenario}")
    veri.verify()


def sync(args: Namespace, config: dict) -> None:
    nacl.utils.copy_srv_dir(config["running_tmp_dir"], config["formula"], cur_dir)


def init(args: Namespace, config: dict) -> None:
    pass


def test(args: Namespace, config: dict):
    create(args)
    converge(args)
    verify(args)
    if args.cleanup:
        delete(args)


def parse_args() -> Namespace:
    parser = argparse.ArgumentParser(
        description="nacl is a cli tool that helps you test salt stack formulas!"
    )
    subparsers = argparse.add_subparser()
    # test command
    test_parser = subparsers.add_parser("test")
    test_parser.add_argument(
        "-s", "--scenario", help="Scenario to test. If not provided all are run"
    )
    test_parser.add_argument(
        "-p",
        "--parallelsim",
        default=1,
        help="How many scenarios can be run at once. This defaults to 1",
    )
    test_parser.add_argument(
        "-c",
        "--cleanup",
        default=True,
        help="Cleanup resources created. By default the is True",
    )
    # create command
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument(
        "-s",
        "--scenario",
        default="default",
        help="Scenario to create resources for. Default is the default scenario",
    )
    # delete command
    delete_parser = subparsers.add_parser("delete")
    create_parser.add_argument(
        "-s",
        "--scenario",
        default="default",
        help="Scenario to tear down resources for. Default is the default scenario",
    )
    # verify
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument(
        "-s",
        "--scenario",
        default="default",
        help="Scenario to run tests on. Default is the default scenario",
    )
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    cur_dir = os.getcwd()
    config = nacl.config.parse_config(nacl.config.get_config())
    if "test" in args:
        test(args, config)
    elif "delete" in args:
        delete(args, config)
    elif "create" in args:
        create(args, config)
    elif "converge" in args:
        converge(args, config)
    elif "verify" in args:
        verify(args, config)
    elif "sync" in args:
        sync(args, config)
    else:
        pass
