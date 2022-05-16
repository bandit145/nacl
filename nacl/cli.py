import argparse
import nacl.orchestrators
import nacl.verifiers
import nacl.config
import nacl.utils
import nacl.exceptions
import sys
import os
import re

def get_orchestrator(orch_name, config) -> nacl.orchestrators.Orchestrator:
    proper_name = list(orch_name)
    proper_name[0] = proper_name[0].upper()
    return getattr(nacl.orchestrators, "".join(proper_name))(config)


def get_verifier(config: dict, orch) -> nacl.verifiers.Verifier:
    proper_name = list(config['verifier'])
    proper_name[0] = proper_name[0].upper()
    return getattr(nacl.verifiers, "".join(proper_name))(config, orch)


def create(args: argparse.Namespace, cur_dir: str, config: dict, orch: nacl.orchestrators.Orchestrator) -> None:
    nacl.utils.copy_srv_dir(config["running_tmp_dir"], config["formula"], cur_dir)
    if not "nacl.yml" in os.listdir():
        os.chdir(f"nacl/{config['scenario']}")
    orch.orchestrate()


def converge(args: argparse.Namespace, cur_dir: str, config: dict, orch: nacl.orchestrators.Orchestrator) -> None:
    if orch.get_inventory() == []:
        nacl.utils.copy_srv_dir(config["running_tmp_dir"], config["formula"], cur_dir)
    if not "nacl.yml" in os.listdir():
        os.chdir(f"nacl/{config['scenario']}")
    if orch.get_inventory() == []:
        orch.orchestrate()
    orch.converge()

def idempotance(orch: nacl.orchestrators.Orchestrator) -> None:
    print('> Running idempotance check')
    output = orch.converge()
    if re.match(r'\(changed=\d*\)', output):
        print('==> Failed idempotance check', file=sys.stderr)
        sys.exit(1)


def delete(args: argparse.Namespace, config: dict, orch: nacl.orchestrators.Orchestrator) -> None:
    if not "nacl.yml" in os.listdir():
        os.chdir(f"nacl/{config['scenario']}")
    orch.cleanup()


def verify(args: argparse.Namespace, config: dict, orch: nacl.orchestrators.Orchestrator) -> None:
    veri = get_verifier(config, orch)
    veri.run()


def sync(args: argparse.Namespace, config: dict) -> None:
    nacl.utils.copy_srv_dir(config["running_tmp_dir"], config["formula"], cur_dir)

def login(args: argparse.Namespace, config: dict, orch: nacl.orchestrators.Orchestrator) -> None:
    orch.login(args.host)


def init(args: argparse.Namespace) -> None:
    if 'scenario' in args:
        nacl.utils.init_scenario(
            args.path, args.formula, args.driver, args.verifier, args.scenario
        )
    elif 'state' in args:
        nacl.utils.init_state(args.state, args.force)
    else:
        print('[x] you must specifiy scenario or state for init command', file=sys.stderr)
        sys.exit(1)


def test(args: argparse.Namespace, cur_dir: str, config: dict, orch: nacl.orchestrators.Orchestrator) -> None:
    delete(args, config, orch)
    converge(args, cur_dir, config, orch)
    os.chdir(cur_dir)
    idempotance(orch)
    verify(args, config, orch)
    if args.cleanup:
        delete(args, config, orch)


def parse_args() -> (argparse.Namespace, argparse.ArgumentParser):
    parser = argparse.ArgumentParser(
        description="nacl is a cli tool that helps you test salt stack formulas!"
    )
    subparsers = parser.add_subparsers()
    #converge parser
    converge_parser = subparsers.add_parser("converge")
    converge_parser.add_argument('--converge', help=argparse.SUPPRESS)
    converge_parser.add_argument('--scenario', help='scenario to use fir converge. Default is default', default='default')
    #login parser
    login_parser = subparsers.add_parser("login")
    login_parser.add_argument('--login', help=argparse.SUPPRESS)
    login_parser.add_argument('--host', help='host to login to', default=None)
    login_parser.add_argument('--scenario', help='scenario that host belongs to', default='default')
    #sync parser
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument('--sync', help=argparse.SUPPRESS, default=True)
    sync_parser.add_argument('--scenario', help="Scenario to load config of. Default is default", default="default")
    # test command
    test_parser = subparsers.add_parser("test")
    test_parser.add_argument(
        "-s", "--scenario", help="Scenario to test. If not provided default is run", default='default'
    )
    test_parser.add_argument('--test', help=argparse.SUPPRESS)
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
    create_parser.add_argument('--create', help=argparse.SUPPRESS)
    create_parser.add_argument(
        "-s",
        "--scenario",
        help="Scenario to create resources for. Default is default",
        default="default",
    )
    # delete command
    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument('--delete', help=argparse.SUPPRESS)
    delete_parser.add_argument(
        "-s",
        "--scenario",
        help="Scenario to delete resources for. Default is default",
        default="default",
    )
    # verify
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument('--verify', help=argparse.SUPPRESS)
    verify_parser.add_argument(
        "-s",
        "--scenario",
        help="Scenario to verify. Default is default",
        default="default",
    )

    # init
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument('--init', help=argparse.SUPPRESS)
    init_sub = init_parser.add_subparsers()
    # init formulas sub parser
    init_scen_parser = init_sub.add_parser("scenario")
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
    init_scen_parser.add_argument("--path", help="path to formula to init", default=None, required=False)
    # init state
    init_state_parser = init_sub.add_parser("state")
    init_state_parser.add_argument(
        "-s", "--state", help="state to create", required=True
    )
    init_state_parser.add_argument('--force', '-f', help='force init a state', action='store_true', default=False)
    return parser.parse_args(), parser


def run() -> None:
    args, parser = parse_args()
    cur_dir = os.getcwd()
    try:
        if 'scenario' not in args:
            parser.print_help()
            sys.exit(0)
        config = nacl.config.parse_config(nacl.config.get_config(args.scenario))
        orch = get_orchestrator(config["provider"], config)
        if "init" in args:
            init(args)
        elif "test" in args:
            test(args, cur_dir, config, orch)
        elif "delete" in args:
            delete(args, config, orch)
        elif "create" in args:
            create(args, cur_dir, config, orch)
        elif "sync" in args:
            nacl.utils.copy_srv_dir(config["running_tmp_dir"], config["formula"], cur_dir)
        elif "converge" in args:
            converge(args, cur_dir, config, orch)
        elif "login" in args:
            login(args, config, orch)
        elif "verify" in args:
            verify(args, config, orch)
        else:
            parser.print_help()
    except (nacl.exceptions.ConfigFileNotFound, nacl.exceptions.ScenarioExists) as error:
        print('[x]', error, file=sys.stderr)
        sys.exit(1)