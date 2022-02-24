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
    if not is_ok:
        raise click.ClickException("Some airss components are missing")


@check.command('database')
@click.option('--past-days', '-p', help='New structures to be counted in the past N days.', default=1, type=int)
@click.pass_context
def database(ctx, past_days):
    """Check launchpad information"""

    # Initialise and check the launch pad
    lpad = ctx.obj.get('lpad_file', LAUNCHPAD_LOC)
    obj: LaunchPad = LaunchPad.from_file(lpad)
    try:
        ids = obj.get_fw_ids({}, limit=1)
    except:
        click.echo("Cannot connect to the LaunchPad server")
    out = obj.fw_id_assigner.find({}).count()
    click.echo("Confection to the LaunchPad server successful: OK\n")

    if out == 0:
        click.echo("ERROR: Fireworks not initialised - `lpad reset` needs to be run.\n")

    click.echo(f'Default launchpad file located at: {LAUNCHPAD_LOC}')
    click.echo(f'Current launchpad file: {Path(lpad).absolute()}')

    # Check the DB interface
    db = ctx.obj.get('db_file', DB_FILE)
    sdb = SearchDB.from_db_file(db)
    click.echo(f'Default database file located at: {DB_FILE}')
    click.echo(f'Current database file: {Path(db).absolute()}\n')

    for key in ['host', 'user', 'port', 'db_name']:
        value = getattr(sdb, key)
        click.echo(f'{key:<15}: {value}')

    # Basic status
    click.echo(f'\nTotal number of SHELX entries: {ResFile.objects.count()}')  # pylint: disable=no-member
    now = datetime.utcnow()
    cutoff = now - timedelta(days=past_days)
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

    click.echo(f'\nNew structures in the last {24 * past_days} hours:')
    for entry in ResFile.objects().aggregate(pipeline):  # pylint: disable=no-member
        idt = entry['_id']
        count = entry['count']
        click.echo(f"{idt['project']:<40} {count}")
