"""
Collection of useful tools
"""
import click
from ase.io import read
from disp.tools.modcell import modify_cell


@click.group('tools')
@click.pass_context
def tools(ctx):
    """Collection of tools"""
    _ = ctx


@tools.command('modcell')
@click.argument('base_cell')
@click.argument('other_cell')
def modcell(base_cell, other_cell):
    """Modify the structure of a CELL file using another"""
    click.echo('\n'.join(modify_cell(base_cell, read(other_cell))))
