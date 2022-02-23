"""
The commandline interface for Distributed Structure Prediction
"""
# pylint: disable=invalid-name, too-many-arguments, import-outside-toplevel, too-many-locals

import click

from disp import __version__
from .cmd_deploy import deploy
from .cmd_db import db
from .cmd_check import check
from .cmd_tools import tools


@click.group('disp')
@click.version_option(version=__version__, prog_name='disp')
def main():
    """Command-line interface for Distributed Structure Prediction (DISP)"""


main.add_command(deploy)
main.add_command(db)
main.add_command(check)
main.add_command(tools)
