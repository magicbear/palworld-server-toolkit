"""RCON client CLI."""

from argparse import ArgumentParser, Namespace
from logging import DEBUG, INFO, basicConfig, getLogger
from pathlib import Path

from rcon import battleye, source
from rcon.config import CONFIG_FILES, LOG_FORMAT, from_args
from rcon.errorhandler import ErrorHandler


__all__ = ['main']


LOGGER = getLogger('rconclt')


def get_args() -> Namespace:
    """Parses and returns the CLI arguments."""

    parser = ArgumentParser(description='A Minecraft RCON client.')
    parser.add_argument('server', help='the server to connect to')
    parser.add_argument(
        '-B', '--battleye', action='store_true',
        help='use BattlEye RCon instead of Source RCON'
    )
    parser.add_argument(
        '-c', '--config', type=Path, metavar='file', default=CONFIG_FILES,
        help='the configuration file'
    )
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='print additional debug information'
    )
    parser.add_argument(
        '-t', '--timeout', type=float, metavar='seconds',
        help='connection timeout in seconds'
    )
    parser.add_argument('command', help='command to execute on the server')
    parser.add_argument(
        'argument', nargs='*', default=(), help='arguments for the command'
    )
    return parser.parse_args()


def run() -> None:
    """Runs the RCON client."""

    args = get_args()
    basicConfig(format=LOG_FORMAT, level=DEBUG if args.debug else INFO)
    host, port, passwd = from_args(args)
    client_cls = battleye.Client if args.battleye else source.Client

    with client_cls(host, port, timeout=args.timeout) as client:
        client.login(passwd)

        if text := client.run(args.command, *args.argument):
            print(text, flush=True)


def main() -> int:
    """Runs the main script with exceptions handled."""

    with ErrorHandler(LOGGER) as handler:
        run()

    return handler.exit_code
