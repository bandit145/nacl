import argparse

def test(args):
	pass

def create(args):
	pass

def delete(args):
	pass

def verify(args):
	pass

def parse_args() -> Namespace:
	parser = argparse.ArgumentParser(description="nacl is a cli tool that helps you test salt stack formulas!")
	subparsers = argparse.add_subparser()
	# test command
	test_parser = subparsers.add_parser('test')
	test_parser.add_argument('-s', '--scenario', help='Scenario to test. If not provided all are run')
	test_parser.add_argument('-p', '--parallelsim', default=1, help='How many scenarios can be run at once. This defaults to 1')
	test_parser.add_argument('-c', '--cleanup', default=True, help='Cleanup resources created. By default the is True')
	# create command
	create_parser = subparsers.add_parser('create')
	create_parser.add_argument('-s', '--scenario', default="default", help="Scenario to create resources for. Default is the default scenario")
	# delete command
	delete_parser = subparsers.add_parser('delete')
	create_parser.add_argument('-s', '--scenario', default="default", help="Scenario to tear down resources for. Default is the default scenario")
	# verify
	verify_parser = subparsers.add_parser('verify')
	verify_parser.add_argument('-s', '--scenario', default="default", help="Scenario to run tests on. Default is the default scenario")
	return parser.parse_args()

def run() -> None:
	pass