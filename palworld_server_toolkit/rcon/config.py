"""RCON server configuration."""

from __future__ import annotations
from argparse import Namespace
from configparser import ConfigParser, SectionProxy
from getpass import getpass
from logging import getLogger
from os import getenv, name
from pathlib import Path
from typing import Iterable, NamedTuple, Optional, Union

from rcon.exceptions import ConfigReadError, UserAbort


__all__ = ['CONFIG_FILES', 'LOG_FORMAT', 'SERVERS', 'Config', 'from_args']


CONFIG = ConfigParser()

if name == 'posix':
    CONFIG_FILES = (
        Path('/etc/rcon.conf'),
        Path('/usr/local/etc/rcon.conf'),
        Path.home().joinpath('.rcon.conf')
    )
elif name == 'nt':
    CONFIG_FILES = (
        Path(getenv('LOCALAPPDATA')).joinpath('rcon.conf'),
        Path.home().joinpath('.rcon.conf')
    )
else:
    raise NotImplementedError(f'Unsupported operating system: {name}')

LOG_FORMAT = '[%(levelname)s] %(name)s: %(message)s'
LOGGER = getLogger('RCON Config')
SERVERS = {}


class Config(NamedTuple):
    """Represents server configuration."""

    host: str
    port: int
    passwd: Optional[str] = None

    @classmethod
    def from_string(cls, string: str) -> Config:
        """Reads the credentials from the given string."""
        try:
            host, port = string.rsplit(':', maxsplit=1)
        except ValueError:
            raise ValueError(f'Invalid socket: {string}.') from None

        port = int(port)

        try:
            passwd, host = host.rsplit('@', maxsplit=1)
        except ValueError:
            passwd = None

        return cls(host, port, passwd)

    @classmethod
    def from_config_section(cls, section: SectionProxy) -> Config:
        """Creates a credentials tuple from
        the respective config section.
        """
        host = section['host']
        port = section.getint('port')
        passwd = section.get('passwd')
        return cls(host, port, passwd)


def load(config_files: Union[Path, Iterable[Path]] = CONFIG_FILES) -> None:
    """Reads the configuration files and populates SERVERS."""

    SERVERS.clear()
    CONFIG.read(config_files)

    for section in CONFIG.sections():
        SERVERS[section] = Config.from_config_section(CONFIG[section])


def from_args(args: Namespace) -> Config:
    """Get the credentials for a server from the respective arguments."""

    try:
        host, port, passwd = Config.from_string(args.server)
    except ValueError:
        load(args.config)

        try:
            host, port, passwd = SERVERS[args.server]
        except KeyError:
            LOGGER.error('No such server: %s.', args.server)
            raise ConfigReadError() from None

    if passwd is None:
        try:
            passwd = getpass('Password: ')
        except (KeyboardInterrupt, EOFError):
            print()
            LOGGER.error('Aborted by user.')
            raise UserAbort() from None

    return Config(host, port, passwd)
