"""
The commandline interface for Distributed Structure Prediction
"""
# pylint: disable=invalid-name, too-many-arguments, import-outside-toplevel, too-many-locals

from pathlib import Path
import click

from disp import __version__
from disp.database.api import DB_FILE
from .cmd_deploy import deploy
from .cmd_db import db
from .cmd_check import check
from .cmd_tools import tools


@click.group('disp')
@click.version_option(version=__version__, prog_name='disp')
@click.pass_context
@click.option('--lpad-file', type=click.Path(), default='my_launchpad.yaml')
@click.option('--db-file', type=click.Path(), default='disp_db.yaml')
def main(ctx, lpad_file, db_file):
    """Command-line interface for Distributed Structure Prediction (DISP)"""
    if lpad_file is None:
        from fireworks.core.launchpad import LAUNCHPAD_LOC
        if not Path(lpad_file).is_file:
            lpad_file = LAUNCHPAD_LOC
    if db_file is None:
        if not Path(db_file).is_file:
            db_file = DB_FILE
    ctx.obj = {'db_file': db_file, 'lpad_file': lpad_file}


main.add_command(deploy)
main.add_command(db)
main.add_command(check)
main.add_command(tools)
