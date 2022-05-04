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


def create(args: argparse.Namespace, config: dict) -> None:
    orch = get_orchestrator(config["provider"], config)
    if not "nacl.yml" in os.listdir():
        os.chdir(f"nacl/{config['scenario']}")
    return orch.orchestrate()


def converge(args: argparse.Namespace, config: dict) -> None:
    orch = get_orchestrator(config["provider"], config)
    if not "nacl.yml" in os.listdir():
        os.chdir(f"nacl/{config['scenario']}")
    orch.converge()


def delete(args: argparse.Namespace, config: dict) -> None:
    orch = get_orchestrator(config["provider"], config)
    if not "nacl.yml" in os.listdir():
        os.chdir(f"nacl/{config['scenario']}")
    return orch.cleanup()


def verify(args: argparse.Namespace, config: dict) -> None:
    veri = get_verifier(config["verifier"])
    if not "nacl.yml" in os.listdir():
        os.chdir(f"nacl/{args.scenario}")
    veri.verify()


def sync(args: argparse.Namespace, config: dict) -> None:
    nacl.utils.copy_srv_dir(config["running_tmp_dir"], config["formula"], cur_dir)


def init(args: argparse.Namespace) -> None:
    if args.scenario:
        nacl.utils.init_scenario(
            args.path, args.formula, args.driver, args.verifier, args.scenario
        )
    else:
        nacl.utils.init_state(args.state)


def test(args: argparse.Namespace, config: dict):
    create(args)
    converge(args)
    verify(args)
    if args.cleanup:
        delete(args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="nacl is a cli tool that helps you test salt stack formulas!"
    )
    subparsers = parser.add_subparsers()
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
        help="Scenario to create resources for. Default is default",
        default="default",
    )
    # delete command
    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument(
        "-s",
        "--scenario",
        help="Scenario to delete resources for. Default is default",
        default="default",
    )
    # verify
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument(
        "-s",
        "--scenario",
        help="Scenario to verify. Default is default",
        default="default",
    )

    # init
    init_parser = subparsers.add_parser("init")
    init_sub = init_parser.add_subparsers()
    # init formulas sub parser
    init_scen_parser = init_sub.add_parser("formula")
    init_scen_parser.add_argument(
        "-d", "--driver", default="docker", help="default driver"
    )
    init_scen_parser.add_argument(
        "-s",
        "--scenario",
        help="scenario to intially create. Default is default",
        default="default",
    )
    init_scen_parser.add_argument(
        "-v", "--verifier", default="testinfra", help="default verifier"
    )
    init_scen_parser.add_argument(
        "-f",
        "--formula",
        default=os.getcwd().split("/")[-1],
        help="formula name if it is different from the repo folder name",
    )
    init_scen_parser.add_argument("path", help="path to formula to init")
    # init state
    init_state_parser = init_sub.add_parser("state")
    init_state_parser.add_argument(
        "-s", "--state", help="state to create", required=True
    )
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    cur_dir = os.getcwd()
    if "init" in args:
        init(args)
    elif "test" in args:
        config = nacl.config.parse_config(nacl.config.get_config(args.scenario))
        test(args, config)
    elif "delete" in args:
        config = nacl.config.parse_config(nacl.config.get_config(args.scenario))
        delete(args, config)
    elif "create" in args:
        config = nacl.config.parse_config(nacl.config.get_config(args.scenario))
        create(args, config)
    elif "converge" in args:
        config = nacl.config.parse_config(nacl.config.get_config(args.scenario))
        converge(args, config)
    elif "verify" in args:
        config = nacl.config.parse_config(nacl.config.get_config(args.scenario))
        verify(args, config)
    elif "sync" in args:
        config = nacl.config.parse_config(nacl.config.get_config(args.scenario))
        sync(args, config)
    else:
        pass
