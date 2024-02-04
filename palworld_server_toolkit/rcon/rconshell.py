"""An interactive RCON shell."""

from argparse import ArgumentParser, Namespace
from logging import INFO, basicConfig, getLogger
from pathlib import Path

from rcon import battleye, source
from rcon.readline import CommandHistory
from rcon.config import CONFIG_FILES, LOG_FORMAT, from_args
from rcon.console import PROMPT, rconcmd
from rcon.errorhandler import ErrorHandler


__all__ = ['get_args', 'main']


LOGGER = getLogger('rconshell')


def get_args() -> Namespace:
    """Parses and returns the CLI arguments."""

    parser = ArgumentParser(description='An interactive RCON shell.')
    parser.add_argument('server', nargs='?', help='the server to connect to')
    parser.add_argument(
        '-B', '--battleye', action='store_true',
        help='use BattlEye RCon instead of Source RCON'
    )
    parser.add_argument(
        '-c', '--config', type=Path, metavar='file', default=CONFIG_FILES,
        help='the configuration file'
    )
    parser.add_argument(
        '-p', '--prompt', default=PROMPT, metavar='PS1',
        help='the shell prompt'
    )
    return parser.parse_args()


def run() -> None:
    """Runs the RCON shell."""

    args = get_args()
    basicConfig(level=INFO, format=LOG_FORMAT)
    client_cls = battleye.Client if args.battleye else source.Client

    if args.server:
        host, port, passwd = from_args(args)
    else:
        host = port = passwd = None

    with CommandHistory(LOGGER):
        rconcmd(client_cls, host, port, passwd, prompt=args.prompt)


def main() -> int:
    """Runs the main script with exceptions handled."""

    with ErrorHandler(LOGGER) as handler:
        run()

    return handler.exit_code
