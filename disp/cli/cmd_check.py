"""
Commands for checking the environment
"""
from datetime import timedelta, datetime
import subprocess
from pathlib import Path

import click
from fireworks.core.launchpad import LaunchPad, LAUNCHPAD_LOC

from disp.scheduler import Scheduler, Dummy
from disp.database.api import DB_FILE, SearchDB, ResFile


@click.group('check')
def check():
    """Check environment"""
@check.command('scheduler')
@click.option('--allow-dummy',
              is_flag=True,
              default=False,
              type=bool,
              help='Allow dummpy scheduler')
def scheduler(allow_dummy):
    """
    Check the status of the scheduler
    """
    obj = Scheduler.get_scheduler()
    if isinstance(obj, Dummy) and not allow_dummy:
        raise ValueError('Not in a scheduler environment')
    click.echo(f'Scheduler: {obj}')
    click.echo(f'JOB ID:    {obj.job_id}')
    click.echo(f'USERNAME:   {obj.user_name}')
    click.echo(f'SECONDS LEFT:   {obj.get_remaining_seconds()}')


@check.command('airss')
def airss():
    """
    Check the status of the AIRSS package installation.
    """
    click.echo(f'LOCATION of essential AIRSS scripts:')
    is_ok = True
    missing = []
    for name in ['buildcell', 'cabal', 'castep_relax']:
        try:
            loc = subprocess.check_output(['which', 'cabal'],
                                          universal_newlines=True).strip()
        except subprocess.CalledProcessError:
            click.echo(f'Tool `{name}` is not found')
            is_ok = False
        else:
            click.echo(f'Tool `{name}` is located at: {loc}')
            missing.append(name)
    if is_ok:
        click.echo('All GOOD!')
    else:
        click.echo(f'Found missing scripts: {missing}')
    return is_ok


@check.command('database')
@click.option('--lpad', type=click.Path(exists=True))
def database(lpad):
    """Check launchpad information"""

    # Initialise and check the launch pad
    if lpad:
        obj = LaunchPad.from_file(lpad)
    elif Path('my_launchpad.yaml').is_file():
        obj = LaunchPad.from_file('my_launchpad.yaml')
        click.echo(
            'Using `my_launchpad.yaml` in the current working directory.')
    else:
        obj = LaunchPad.from_file(LAUNCHPAD_LOC)
        click.echo(f'Using launchpad file at `{LAUNCHPAD_LOC}`')

    click.echo(f'LaunchPad name: {obj.name}')

    # Check the DB interface
    click.echo(f'DISP database specification file located at: {DB_FILE}')
    sdb = SearchDB.from_db_file(DB_FILE)
    for key in ['host', 'user', 'port', 'db_name']:
        value = getattr(sdb, key)
        click.echo(f'{key:<15}: {value}')

    # Basic status
    click.echo(f'\nTotal number of SHELX entries: {ResFile.objects.count()}')  # pylint: disable=no-member
    now = datetime.utcnow()
    cutoff = now - timedelta(days=1)
    pipeline = [
        {
            '$match': {
                'created_on': {
                    '$gt': cutoff
                }
            }
        },
        {
            '$group': {
                '_id': {
                    'project': '$project_name'
                },
                'count': {
                    '$sum': 1
                }
            }
        },
    ]

    click.echo(f'\nNew structures in the last 24 hours:')
    for entry in ResFile.objects().aggregate(pipeline):  # pylint: disable=no-member
        idt = entry['_id']
        count = entry['count']
        click.echo(f"{idt['project']:<40} {count}")
