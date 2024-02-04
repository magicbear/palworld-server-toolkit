"""GTK based GUI."""

from argparse import ArgumentParser, Namespace
from json import dump, load
from logging import DEBUG, INFO, basicConfig, getLogger
from os import getenv, name
from pathlib import Path
from socket import gaierror, timeout
from typing import Iterable, NamedTuple, Type

from gi import require_version
require_version('Gtk', '3.0')
from gi.repository import Gtk

from rcon import battleye, source
from rcon.client import BaseClient
from rcon.config import LOG_FORMAT
from rcon.exceptions import SessionTimeout, WrongPassword


__all__ = ['main']


if name == 'posix':
    CACHE_DIR = Path.home().joinpath('.cache')
elif name == 'nt':
    CACHE_DIR = Path(getenv('TEMP') or getenv('TMP'))
else:
    raise NotImplementedError('Unsupported operating system.')


CACHE_FILE = CACHE_DIR.joinpath('rcongui.json')
LOGGER = getLogger('rcongui')


def get_args() -> Namespace:
    """Parses the command line arguments."""

    parser = ArgumentParser(description='A minimalistic, GTK-based RCON GUI.')
    parser.add_argument(
        '-B', '--battleye', action='store_true',
        help='use BattlEye RCon instead of Source RCON'
    )
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='print additional debug information'
    )
    parser.add_argument(
        '-t', '--timeout', type=float, metavar='seconds',
        help='connection timeout in seconds'
    )
    return parser.parse_args()


class RCONParams(NamedTuple):
    """Represents the RCON parameters."""

    host: str
    port: int
    passwd: str
    command: Iterable[str]


class GUI(Gtk.Window):  # pylint: disable=R0902
    """A GTK based GUI for RCON."""

    def __init__(self, args: Namespace):
        """Initializes the GUI."""
        super().__init__(title='RCON GUI')
        self.args = args

        self.set_position(Gtk.WindowPosition.CENTER)

        self.grid = Gtk.Grid()
        self.add(self.grid)

        self.host = Gtk.Entry()
        self.host.set_placeholder_text('Host')
        self.grid.attach(self.host, 0, 0, 1, 1)

        self.port = Gtk.SpinButton.new_with_range(0, 65535, 1)
        self.port.set_placeholder_text('Port')
        self.grid.attach(self.port, 1, 0, 1, 1)

        self.passwd = Gtk.Entry()
        self.passwd.set_placeholder_text('Password')
        self.passwd.set_visibility(False)
        self.grid.attach(self.passwd, 2, 0, 1, 1)

        self.command = Gtk.Entry()
        self.command.set_placeholder_text('Command')
        self.grid.attach(self.command, 0, 1, 2, 1)

        self.button = Gtk.Button(label='Run')
        self.button.connect('clicked', self.on_button_clicked)
        self.grid.attach(self.button, 2, 1, 1, 1)

        self.result = Gtk.TextView()
        self.result.set_wrap_mode(Gtk.WrapMode.WORD)
        self.result.set_property('editable', False)
        self.grid.attach(self.result, 0, 2, 2, 1)

        self.savepw = Gtk.CheckButton(label='Save password')
        self.grid.attach(self.savepw, 2, 2, 1, 1)

        self.load_gui_settings()

    @property
    def client_cls(self) -> Type[BaseClient]:
        """Returns the client class."""
        return battleye.Client if self.args.battleye else source.Client

    @property
    def result_text(self) -> str:
        """Returns the result text."""
        if (buf := self.result.get_buffer()) is not None:
            start = buf.get_iter_at_line(0)
            end = buf.get_iter_at_line(buf.get_line_count())
            return buf.get_text(start, end, True)

        return ''

    @result_text.setter
    def result_text(self, text: str):
        """Sets the result text."""
        if (buf := self.result.get_buffer()) is not None:
            buf.set_text(text)

    @property
    def gui_settings(self) -> dict:
        """Returns the GUI settings as a dict."""
        json = {
            'host': self.host.get_text(),
            'port': self.port.get_value_as_int(),
            'command': self.command.get_text(),
            'result': self.result_text,
            'savepw': (savepw := self.savepw.get_active())
        }

        if savepw:
            json['passwd'] = self.passwd.get_text()

        return json

    @gui_settings.setter
    def gui_settings(self, json: dict):
        """Sets the GUI settings."""
        self.host.set_text(json.get('host', ''))
        self.port.set_value(json.get('port', 0))
        self.passwd.set_text(json.get('passwd', ''))
        self.command.set_text(json.get('command', ''))
        self.result_text = json.get('result', '')
        self.savepw.set_active(json.get('savepw', False))

    def load_gui_settings(self) -> None:
        """Loads the GUI settings from the cache file."""
        try:
            with CACHE_FILE.open('rb') as cache:
                self.gui_settings = load(cache)
        except FileNotFoundError:
            LOGGER.warning('Cache file not found: %s', CACHE_FILE)
        except PermissionError:
            LOGGER.error('Insufficient permissions to read: %s', CACHE_FILE)
        except ValueError:
            LOGGER.error('Cache file contains garbage: %s', CACHE_FILE)

    def save_gui_settings(self):
        """Saves the GUI settings to the cache file."""
        try:
            with CACHE_FILE.open('wb') as cache:
                dump(self.gui_settings, cache)
        except PermissionError:
            LOGGER.error('Insufficient permissions to read: %s', CACHE_FILE)

    def show_error(self, message: str):
        """Shows an error message."""
        message_dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        message_dialog.run()
        message_dialog.destroy()

    def run_rcon(self) -> str:
        """Returns the current RCON settings."""
        with self.client_cls(
                self.host.get_text().strip(),
                self.port.get_value_as_int(),
                timeout=self.args.timeout,
                passwd=self.passwd.get_text()
        ) as client:
            return client.run(*self.command.get_text().strip().split())

    def on_button_clicked(self, _):
        """Runs the client."""
        try:
            result = self.run_rcon()
        except ValueError as error:
            self.show_error(str(error))
        except gaierror as error:
            self.show_error(error.strerror)
        except ConnectionRefusedError:
            self.show_error('Connection refused.')
        except (TimeoutError, timeout):
            self.show_error('Connection timed out.')
        except WrongPassword:
            self.show_error('Wrong password.')
        except SessionTimeout:
            self.show_error('Session timed out.')
        else:
            self.result_text = result

    def terminate(self, *args, **kwargs):
        """Saves the settings and terminates the application."""
        self.save_gui_settings()
        Gtk.main_quit(*args, **kwargs)


def main() -> None:
    """Starts the GUI."""

    args = get_args()
    basicConfig(format=LOG_FORMAT, level=DEBUG if args.debug else INFO)
    win = GUI(args)
    win.connect('destroy', win.terminate)
    win.show_all()
    Gtk.main()
