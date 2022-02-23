"""
Deployment commands
"""
import subprocess
from pathlib import Path
from pprint import pformat

import click
from fireworks.core.firework import Workflow
from fireworks.core.launchpad import LaunchPad, LAUNCHPAD_LOC
from ase.io import read

from disp.fws.works import AirssSearchFW, RelaxFW
from disp.fws.utils import isolated_filesystem
from disp.tools.modcell import modify_cell

# pylint: disable=invalid-name, too-many-arguments, import-outside-toplevel, too-many-locals


@click.group('deploy')
@click.option('--lpad', type=click.Path(exists=True))
@click.pass_context
def deploy(ctx, lpad):
    """Deploy search/relaxation to the FireServer"""
    if lpad:
        ctx.obj = LaunchPad.from_file(lpad)
    elif Path('my_launchpad.yaml').is_file():
        ctx.obj = LaunchPad.from_file('my_launchpad.yaml')
        click.echo(
            'Using `my_launchpad.yaml` in the current working directory.')
    else:
        ctx.obj = LaunchPad.from_file(LAUNCHPAD_LOC)
        click.echo(f'Using launchpad file at `{LAUNCHPAD_LOC}`')


pass_lpad = click.make_pass_decorator(LaunchPad)


@deploy.command('info')
@pass_lpad
def info(lpad):
    """Print information"""
    click.echo('Information about the launchpad:')
    click.echo(pformat(lpad.as_dict()))


@deploy.command('search')
@click.option(
    '--wf-name',
    required=False,
    help=
    'How the workflow should be named. Project name will be used if not provided.'
)
@click.option(
    '--seed',
    required=True,
    help=
    'Name of the seed to be used, two files \'<seed>.cell\' and \'<seed>.param\' must present in the current directory.'
)
@click.option('--project', required=True, help='Name of the project.')
@click.option('--num',
              required=True,
              type=int,
              help='Number of structures to search for.')
@click.option('--priority', type=int, help='Priority for the fireworks.')
@click.option(
    '--category',
    multiple=True,
    help=
    'Category for the fireworks. Useful when the tasks should be run with specific workers.'
)
@click.option(
    '--exe',
    default='mpirun -np 8 castep.mpi',
    help=
    'Executable to be used, including the mpi runner part. The latter may be overriden by the worker.'
)
@click.option(
    '--modcell',
    type=str,
    help=
    ('If pressent will insert an AirssModcellTask task to the firework.'
     'Format: \'myfunc.py:myfunc\' to insert using a python file,'
     ' or \'mymodule.my_func\' to load a function that can be imported on the remote computer.'
     ))
@click.option('--cycles',
              default=200,
              type=int,
              show_default=True,
              help='Maximum optimisation steps per structure')
@click.option('--keep/--no-keep',
              default=True,
              show_default=True,
              help='Keep intermediate files.')
@click.option('--gzip/--no-gzip',
              default=True,
              show_default=True,
              help='Gzip the working directory in the end.')
@click.option('--dryrun', is_flag=True)
@click.option('--record-db/--no-record-db',
              show_default=True,
              help='Wether to record the result in to the database or not.',
              default=True)
@click.option(
    '--castep-code',
    show_default=True,
    default='default',
    help=
    'Alias for resolving the CASTEP executable, as define in the worker file.')
@pass_lpad
def deploy_search(lpad, seed, project, num, exe, cycles, keep, wf_name, dryrun,
                  priority, category, gzip, record_db, modcell, castep_code):
    """
    Deploy the search by uploading it to the Fireserver
    """

    seed_content = Path(seed + '.cell').read_text()
    param_content = Path(seed + '.param').read_text()
    wf_metadata = {
        'project_name': project,
        'seed_name': seed,
        'disp_type': 'search',
    }

    spec = {}
    if priority:
        spec['_priority'] = priority

    if category:
        category = list(category)
        spec['_category'] = category

    build_fws = []
    if wf_name is None:
        wf_name = f'{project}-{seed}'

    # Adding cell modificators
    if modcell is not None:
        tokens = modcell.split(':')
        if len(tokens) == 2:
            modcell_name = tokens[1]
            modcell_content = Path(tokens[0]).read_text()
        elif len(tokens) == 1:
            modcell_name = modcell
            modcell_content = None
    else:
        modcell_content = None
        modcell_name = None

    for idx in range(num):
        name = f'{wf_name}-{idx}'
        fw = AirssSearchFW(project_name=project,
                           seed_name=seed,
                           seed_content=seed_content,
                           param_content=param_content,
                           executable=exe,
                           gzip_folder=gzip,
                           record_db=record_db,
                           keep=keep,
                           cycles=cycles,
                           name=name,
                           modcell_content=modcell_content,
                           modcell_name=modcell_name,
                           castep_code=castep_code,
                           spec=spec)

        workflow = Workflow([fw], name=name)
        # Add project/seed information to the workflow
        workflow.metadata.update(wf_metadata)
        build_fws.append(workflow)

    # If we are doing dry runs, print the information only
    if dryrun:
        click.echo(
            f'Submitting {num} structures for project: {project}, seed name: {seed}'
        )
        click.echo(f'Priority: {priority}; Category: {category}')
        click.echo(seed_content)
        click.echo('And parameters:')
        click.echo(param_content)
        if keep:
            click.echo(f'The intermediate files will be kept.')
        else:
            click.echo(f'The intermediate files will not be kept.')

        click.echo(f'The default executable for tasks is: {exe}')
        click.echo(
            f'Each structure will be optimised for maximum {cycles} iterations'
        )
        click.echo(f'The WorkFlows/Fireworks will be named as {wf_name}-*')

        dryrun_seed(seed_content, workflow, modcell)
    else:
        lpad.bulk_add_wfs(build_fws)


@deploy.command('relax')
@click.option('--seed',
              help='Seed name to be used',
              default='USER-RELAX',
              show_default=True)
@click.option(
    '--base-cell',
    required=False,
    type=str,
    help=
    ('Base cell files to be used.'
     'The "cell" file passed will be only used to define the crystal structure.'
     ))
@click.option('--cell',
              required=True,
              type=str,
              help='Path the cell files - support globbing')
@click.option('--priority',
              type=int,
              help='Priority to be used for the workflow')
@click.option('--param',
              type=click.Path(exists=True),
              required=True,
              help='The param file to be used.')
@click.option('--project', required=True)
@click.option(
    '--exe',
    default='mpirun -np 8 castep.mpi',
    help=
    'Executable to be used, including the mpi part. The latter may be override by the worker.'
)
@click.option(
    '--extra-cell-file',
    type=click.Path(exists=True),
    required=False,
    help=
    'Path to a file containing the extra lines to be appended to the cell files sent for relaxation.'
)
@click.option('--cycles',
              default=200,
              type=int,
              help='Maximum optimisation steps per structure')
@click.option('--category', multiple=True, help='Category for the fireworks')
@click.option('--keep/--no-keep',
              default=True,
              help='Keep intermediate files.')
@click.option('--dryrun', is_flag=True)
@click.option('--gzip/--no-gzip',
              show_default=True,
              default=True,
              help='Gzip the working directory in the end.')
@click.option('--record-db/--no-record-db',
              help='Wether to record the result in to the database or not.',
              default=True)
@click.option(
    '--castep-code',
    show_default=True,
    default='default',
    help=
    'Alias for resolving the CASTEP executable, as define in the worker file.')
@pass_lpad
def deploy_relax(lpad, seed, cell, base_cell, param, project, exe, cycles,
                 keep, dryrun, priority, gzip, record_db, category,
                 extra_cell_file, castep_code):
    """
    Deploy a workflow to do relaxation of a particular structure
    """
    # Read the inputs
    param_content = Path(param).read_text()

    spec = {}

    wf_metadata = {
        'project_name': project,
        'seed_name': seed,
        'disp_type': 'relax',
    }

    if priority:
        spec['_priority'] = priority

    if category:
        category = list(category)
        spec['_category'] = category

    # Support multiple input structures
    cells = Path('.').glob(cell)
    workflows = []

    # Extra lines to be appended to the cell files used as inputs
    if extra_cell_file is not None:
        extra_cell_content = Path(extra_cell_file).read_text()
    else:
        extra_cell_content = None

    for cell_path in cells:
        struct_name = cell_path.stem
        name = struct_name + '-relax'

        # If there is a base cell file - combine it with the passed cell
        if base_cell is not None:
            atoms = read(str(cell_path))
            cell_content = '\n'.join(modify_cell(base_cell, atoms)) + '\n'
        else:
            cell_content = cell_from_file(str(cell_path))

        # Apply extra cell lines if necessary
        if extra_cell_content:
            cell_content += '\n' + extra_cell_content

        fw = RelaxFW(
            project_name=project,
            struct_name=struct_name,
            struct_content=cell_content,
            param_content=param_content,
            executable=exe,
            gzip_folder=gzip,
            record_db=record_db,
            keep=keep,
            existing_spec=spec,
            cycles=cycles,
            name=name,
            seed_name=seed,
            castep_code=castep_code,
        )

        wflow = Workflow([fw], name=name)
        wflow.metadata.update(wf_metadata)
        wflow.metadata['struct_name'] = struct_name
        workflows.append(wflow)

    # If we are doing dry runs, print the information only
    if dryrun:
        click.echo(f'TOTAL NUMBER OF STRUCTURES: {len(workflows)}')
        click.echo(
            f'Submitting structure {struct_name} for project: {project} (seed: {seed})'
        )
        click.echo(f'Priority: {priority}; Category: {category}')
        click.echo(cell_content)
        click.echo('And parameters:')
        click.echo(param_content)
        if keep:
            click.echo(f'The intermediate files will be kept.')
        else:
            click.echo(f'The intermediate files will not be kept.')

        click.echo(f'The default executable for tasks is: {exe}')
        click.echo(
            f'Each structure will be optimised for maximum {cycles} iterations'
        )
        click.echo(f'The WorkFlows/Fireworks will be named as {name}')
    else:
        lpad.bulk_add_wfs(workflows)


def cell_from_file(fname):
    """
    Read a cell file, convert to cell format if necessary.
    """
    if fname.endswith('.cell'):
        return Path(fname).read_text()
    suffix = fname.split('.')[-1]
    with open(fname) as fh:
        content = subprocess.check_output(['cabal', suffix, 'cell'],
                                          stdin=fh,
                                          universal_newlines=True)
    return content


def dryrun_seed(seed_content: str, workflow: Workflow, modcell: bool):
    """
    Perform dryrun of a given seed and workflow
    """

    with isolated_filesystem():
        with open('SEED-NAME.cell', 'w') as fhandle:
            fhandle.write(seed_content)

        click.echo("""
###################################################
#                                                 #
#                RUNNING buildcell                #
#                                                 #
###################################################

""")

        subprocess.run('buildcell < SEED-NAME.cell > SEED-OUT.cell',
                       shell=True,
                       check=True)
        orig = Path('SEED-OUT.cell').read_text()
        click.echo("""
###################################################
#                                                 #
#                Example Structure                #
#                                                 #
###################################################

{}""".format(orig))

        # Test applying cell modifications
        if modcell is not None:
            fw = workflow.fws[0]
            mod_task = fw.tasks[1]
            dummy_spec = {
                'struct_name': 'SEED-OUT',
            }
            mod_task.run_task(dummy_spec)
            outcome = Path('SEED-OUT.cell').read_text()

            click.echo("""
###################################################
#                                                 #
#               Modified Structure                #
#                                                 #
###################################################

{}""".format(outcome))
