"""
Deployment commands
"""
import subprocess
from pathlib import Path
from pprint import pformat

import click
from ase.io import read
from fireworks.core.firework import Workflow
from fireworks.core.launchpad import LaunchPad

from disp.fws.utils import isolated_filesystem
from disp.fws.works import AirssSearchFW, RelaxFW, SinglePointFW
from disp.tools.modcell import modify_cell

# pylint: disable=invalid-name, too-many-arguments, import-outside-toplevel, too-many-locals

SUFFIX_MAP = {
    "castep": ".param",
    "gulp": ".lib",
    "pp3": ".pp",
}


@click.group("deploy")
@click.pass_context
def deploy(ctx):
    """Deploy search/relaxation to the FireServer"""
    lpad_file = ctx.obj["lpad_file"]
    ctx.obj = LaunchPad.from_file(lpad_file)
    click.echo(f"Using launchpad file at `{lpad_file}`")


pass_lpad = click.make_pass_decorator(LaunchPad)


@deploy.command("info")
@pass_lpad
def info(lpad):
    """Print information"""
    click.echo("Information about the launchpad:")
    click.echo(pformat(lpad.as_dict()))


@deploy.command("search")
@click.option("--wf-name", required=False, help="How the workflow should be named. Project name will be used if not provided.")
@click.option(
    "--seed",
    required=True,
    help="Name of the seed to be used, two files '<seed>.cell' and '<seed>.param' must present in the current directory.",
)
@click.option("--project", required=True, help="Name of the project.")
@click.option("--num", required=True, type=int, help="Number of structures to search for.")
@click.option("--priority", type=int, help="Priority for the fireworks.")
@click.option("--category", multiple=True, help="Category for the fireworks. Useful when the tasks should be run with specific workers.")
@click.option(
    "--exe",
    default="mpirun -np 8 castep.mpi",
    help="Executable to be used, including the mpi runner part. The latter may be overridden by the worker.",
)
@click.option(
    "--modcell",
    type=str,
    help=(
        "If present will insert an AirssModcellTask task to the firework."
        "Format: 'myfunc.py:myfunc' to insert using a python file,"
        " or 'mymodule.my_func' to load a function that can be imported on the remote computer."
    ),
)
@click.option("--cycles", default=200, type=int, show_default=True, help="Maximum optimisation steps per structure")
@click.option("--keep/--no-keep", default=True, show_default=True, help="Keep intermediate files.")
@click.option("--gzip/--no-gzip", default=True, show_default=True, help="Gzip the working directory in the end.")
@click.option("--dryrun", is_flag=True)
@click.option("--record-db/--no-record-db", show_default=True, help="Wether to record the result in to the database or not.", default=True)
@click.option("--code", show_default=True, help="Code to use for relaxation", default="castep")
@click.option(
    "--castep-code", show_default=True, default="default", help="Alias for resolving the CASTEP executable, as define in the worker file."
)
@click.option("--cluster", is_flag=True, default=False)
@pass_lpad
def deploy_search(
    lpad, code, seed, project, num, exe, cycles, keep, wf_name, dryrun, priority, category, gzip, record_db, modcell, castep_code, cluster
):
    """
    Deploy the search by uploading it to the Fireserver
    """

    seed_content = Path(seed + ".cell").read_text()
    param_content = Path(seed + SUFFIX_MAP[code]).read_text()

    if code == "gulp" and "castep" in exe:
        exe = "ggulp"
    if code == "pp3" and "castep" in exe:
        exe = "pp3"

    wf_metadata = {
        "project_name": project,
        "seed_name": seed,
        "disp_type": "search",
    }

    spec = {}
    if priority:
        spec["_priority"] = priority

    if category:
        category = list(category)
        spec["_category"] = category

    build_fws = []
    if wf_name is None:
        wf_name = f"{project}-{seed}"

    # Adding cell modifications
    if modcell is not None:
        tokens = modcell.split(":")
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
        name = f"{wf_name}-{idx}"
        fw = AirssSearchFW(
            project_name=project,
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
            code=code,
            cluster=cluster,
            spec=spec,
        )

        workflow = Workflow([fw], name=name)
        # Add project/seed information to the workflow
        workflow.metadata.update(wf_metadata)
        build_fws.append(workflow)

    # If we are doing dry runs, print the information only
    if dryrun:
        click.echo(f"Submitting {num} structures for project: {project}, seed name: {seed}")
        click.echo(f"Priority: {priority}; Category: {category}")
        click.echo(seed_content)
        click.echo("And parameters:")
        click.echo(param_content)
        if keep:
            click.echo("The intermediate files will be kept.")
        else:
            click.echo("The intermediate files will not be kept.")

        click.echo(f"The default executable for tasks is: {exe}")
        click.echo(f"Each structure will be optimised for maximum {cycles} iterations")
        click.echo(f"The WorkFlows/Fireworks will be named as {wf_name}-*")

        dryrun_seed(seed_content, workflow, modcell)
    else:
        lpad.bulk_add_wfs(build_fws)


@deploy.command("singlepoint")
@click.option("--seed", help="Seed name to be used", default="UESR-SP", show_default=True)
@click.option("--category", multiple=True, help="Category for the fireworks. Useful when the tasks should be run with specific workers.")
@click.option(
    "--base-cell",
    required=False,
    type=str,
    help=(
        "Base cell files to be used."
        "If supplied, the"
        ' "cell" file passed will be only used to define the crystal structure as read using ASE.'
        "Hence, any ASE-supported geometry file can be used for defining the structures to be relaxed."
    ),
)
@click.option(
    "--cell",
    required=True,
    type=str,
    help=(
        "Path the cell files - support globbing. If `--base-cell` is supplied, "
        "any ase-support format may be used, otherwise only CASTEP .cell files are allowed."
    ),
)
@click.option("--priority", type=int, help="Priority to be used for the workflow")
@click.option("--param", type=click.Path(exists=True), required=True, help="The param file to be used.")
@click.option("--project", required=True)
@click.option("--record-db/--no-record-db", show_default=True, help="Wether to record the result in to the database or not.", default=True)
@click.option(
    "--exe",
    default="mpirun -np 8 castep.mpi",
    help="Executable to be used, including the mpi part. The latter may be override by the worker.",
)
@click.option(
    "--extra-cell-file",
    type=click.Path(exists=True),
    required=False,
    help="Path to a file containing the extra lines to be appended to the cell files sent for relaxation.",
)
@click.option("--keep/--no-keep", default=False, help="Keep intermediate files, e.g. do no clean the workding directory.")
@click.option("--dryrun", is_flag=True)
@click.option(
    "--castep-code", show_default=True, default="default", help="Alias for resolving the CASTEP executable, as define in the worker file."
)
@click.option("--code", show_default=True, help="Code to use for relaxation", default="castep")
@click.option(
    "--modcell",
    help="Function to be used to modified to cell file. Such function should receives a list of lines and return a new list of lines.",
)
@click.option("--cluster", is_flag=True, default=False)
@pass_lpad
def deploy_singlepoint(
    lpad,
    code,
    seed,
    cell,
    base_cell,
    param,
    project,
    exe,
    keep,
    dryrun,
    priority,
    category,
    record_db,
    cluster,
    extra_cell_file,
    castep_code,
    modcell,
):
    """
    Deploy a workflow to do singlepoint calculation of a particular structure
    """
    # Read the inputs
    param_content = Path(param).read_text()
    spec = {}

    wf_metadata = {
        "project_name": project,
        "seed_name": seed,
        "disp_type": "singlepoint",
    }

    if priority:
        spec["_priority"] = priority

    if category:
        category = list(category)
        spec["_category"] = category

    # Support multiple input structures
    cells = Path(".").glob(cell)
    workflows = []

    # Extra lines to be appended to the cell files used as inputs
    if extra_cell_file is not None:
        extra_cell_content = Path(extra_cell_file).read_text()
    else:
        extra_cell_content = None

    for cell_path in cells:
        struct_name = cell_path.stem
        name = struct_name + "-sp"

        # If there is a base cell file - combine it with the passed cell
        if base_cell is not None:
            atoms = read(str(cell_path))
            cell_content = "\n".join(modify_cell(base_cell, atoms)) + "\n"
        else:
            cell_content = cell_from_file(str(cell_path))

        # Allow a custom python function to be used to modified the cell
        if modcell is not None:
            cell_content = apply_modcell(modcell, cell_content)

        # Apply extra cell lines if necessary
        if extra_cell_content:
            cell_content += "\n" + extra_cell_content

        fw = SinglePointFW(
            project_name=project,
            struct_name=struct_name,
            struct_content=cell_content,
            param_content=param_content,
            executable=exe,
            clean_dir=not keep,
            existing_spec=spec,
            name=name,
            record_db=record_db,
            seed_name=seed,
            castep_code=castep_code,
            code=code,
            cluster=cluster,
        )

        wflow = Workflow([fw], name=name)
        wflow.metadata.update(wf_metadata)
        wflow.metadata["struct_name"] = struct_name
        workflows.append(wflow)

    # If we are doing dry runs, print the information only
    if dryrun:
        click.echo(f"TOTAL NUMBER OF STRUCTURES: {len(workflows)}")
        click.echo(f"Submitting structure {struct_name} for project: {project} (seed: {seed})")
        click.echo(f"Priority: {priority}; Category: {category}")
        click.echo(cell_content)
        click.echo("And parameters:")
        click.echo(param_content)
        if keep:
            click.echo("The intermediate files will be kept.")
        else:
            click.echo("The intermediate files will not be kept.")

        click.echo(f"The default executable for tasks is: {exe}")
        click.echo(f"The WorkFlows/Fireworks will be named as {name}")
    else:
        lpad.bulk_add_wfs(workflows)


@deploy.command("relax")
@click.option("--seed", help="Seed name to be used", default="USER-RELAX", show_default=True)
@click.option(
    "--base-cell",
    required=False,
    type=str,
    help=(
        "Base cell files to be used."
        "If supplied, the"
        ' "cell" file passed will be only used to define the crystal structure as read using ASE.'
        "Hence, any ASE-supported geometry file can be used for defining the structures to be relaxed."
    ),
)
@click.option(
    "--cell",
    required=True,
    type=str,
    help=(
        "Path the cell files - support globbing. If `--base-cell` is supplied, "
        "any ase-support format may be used, otherwise only CASTEP .cell files are allowed."
    ),
)
@click.option("--priority", type=int, help="Priority to be used for the workflow")
@click.option("--param", type=click.Path(exists=True), required=True, help="The param file to be used.")
@click.option("--project", required=True)
@click.option(
    "--exe",
    default="mpirun -np 8 castep.mpi",
    help="Executable to be used, including the mpi part. The latter may be override by the worker.",
)
@click.option(
    "--extra-cell-file",
    type=click.Path(exists=True),
    required=False,
    help="Path to a file containing the extra lines to be appended to the cell files sent for relaxation.",
)
@click.option("--cycles", default=200, type=int, help="Maximum optimisation steps per structure")
@click.option("--category", multiple=True, help="Category for the fireworks")
@click.option("--keep/--no-keep", default=True, help="Keep intermediate files.")
@click.option("--dryrun", is_flag=True)
@click.option("--gzip/--no-gzip", show_default=True, default=True, help="Gzip the working directory in the end.")
@click.option("--record-db/--no-record-db", help="Wether to record the result in to the database or not.", default=True)
@click.option(
    "--castep-code", show_default=True, default="default", help="Alias for resolving the CASTEP executable, as define in the worker file."
)
@click.option("--code", show_default=True, help="Code to use for relaxation", default="castep")
@click.option(
    "--modcell",
    help="Function to be used to modified to cell file. Such function should receives a list of lines and return a new list of lines.",
)
@click.option("--cluster", is_flag=True, default=False)
@pass_lpad
def deploy_relax(
    lpad,
    code,
    seed,
    cell,
    base_cell,
    param,
    project,
    exe,
    cycles,
    keep,
    dryrun,
    priority,
    gzip,
    record_db,
    category,
    cluster,
    extra_cell_file,
    castep_code,
    modcell,
):
    """
    Deploy a workflow to do relaxation of a particular structure
    """
    # Read the inputs
    param_content = Path(param).read_text()
    spec = {}

    wf_metadata = {
        "project_name": project,
        "seed_name": seed,
        "disp_type": "relax",
    }

    if priority:
        spec["_priority"] = priority

    if category:
        category = list(category)
        spec["_category"] = category

    # Support multiple input structures
    cells = Path(".").glob(cell)
    workflows = []

    # Extra lines to be appended to the cell files used as inputs
    if extra_cell_file is not None:
        extra_cell_content = Path(extra_cell_file).read_text()
    else:
        extra_cell_content = None

    for cell_path in cells:
        struct_name = cell_path.stem
        name = struct_name + "-relax"

        # If there is a base cell file - combine it with the passed cell
        if base_cell is not None:
            atoms = read(str(cell_path))
            cell_content = "\n".join(modify_cell(base_cell, atoms)) + "\n"
        else:
            cell_content = cell_from_file(str(cell_path))

        # Allow a custom python function to be used to modified the cell
        if modcell is not None:
            tokens = modcell.split(":")
            if len(tokens) == 2:
                func_name = tokens[1]
                mod = __import__(tokens[0].replace(".py", ""), globals(), locals(), [str(func_name)], 0)
                modfunc = getattr(mod, func_name)
            else:
                raise ValueError("--modcell options should be in the format of `filename:func`.")
            # Apply the function
            cell_content = "\n".join(modfunc(cell_content.split("\n")))

        # Apply extra cell lines if necessary
        if extra_cell_content:
            cell_content += "\n" + extra_cell_content

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
            code=code,
            cluster=cluster,
        )

        wflow = Workflow([fw], name=name)
        wflow.metadata.update(wf_metadata)
        wflow.metadata["struct_name"] = struct_name
        workflows.append(wflow)

    # If we are doing dry runs, print the information only
    if dryrun:
        click.echo(f"TOTAL NUMBER OF STRUCTURES: {len(workflows)}")
        click.echo(f"Submitting structure {struct_name} for project: {project} (seed: {seed})")
        click.echo(f"Priority: {priority}; Category: {category}")
        click.echo(cell_content)
        click.echo("And parameters:")
        click.echo(param_content)
        if keep:
            click.echo("The intermediate files will be kept.")
        else:
            click.echo("The intermediate files will not be kept.")

        click.echo(f"The default executable for tasks is: {exe}")
        click.echo(f"Each structure will be optimised for maximum {cycles} iterations")
        click.echo(f"The WorkFlows/Fireworks will be named as {name}")
    else:
        lpad.bulk_add_wfs(workflows)


def cell_from_file(fname):
    """
    Read a cell file, convert to cell format if necessary.
    """
    if fname.endswith(".cell"):
        return Path(fname).read_text()
    suffix = fname.split(".")[-1]
    with open(fname) as fh:
        content = subprocess.check_output(["cabal", suffix, "cell"], stdin=fh, universal_newlines=True)
    return content


def dryrun_seed(seed_content: str, workflow: Workflow, modcell: bool):
    """
    Perform dryrun of a given seed and workflow
    """

    with isolated_filesystem():
        with open("SEED-NAME.cell", "w") as fhandle:
            fhandle.write(seed_content)

        click.echo(
            """
###################################################
#                                                 #
#                RUNNING buildcell                #
#                                                 #
###################################################

"""
        )

        subprocess.run("buildcell < SEED-NAME.cell > SEED-OUT.cell", shell=True, check=True)
        orig = Path("SEED-OUT.cell").read_text()
        click.echo(
            """
###################################################
#                                                 #
#                Example Structure                #
#                                                 #
###################################################

{}""".format(
                orig
            )
        )

        # Test applying cell modifications
        if modcell is not None:
            fw = workflow.fws[0]
            mod_task = fw.tasks[1]
            dummy_spec = {
                "struct_name": "SEED-OUT",
            }
            mod_task.run_task(dummy_spec)
            outcome = Path("SEED-OUT.cell").read_text()

            click.echo(
                """
###################################################
#                                                 #
#               Modified Structure                #
#                                                 #
###################################################

{}""".format(
                    outcome
                )
            )


def apply_modcell(modcell, cell_content):
    tokens = modcell.split(":")
    if len(tokens) == 2:
        func_name = tokens[1]
        mod = __import__(tokens[0].replace(".py", ""), globals(), locals(), [str(func_name)], 0)
        modfunc = getattr(mod, func_name)
    else:
        raise ValueError("`modcell` should be in the format of `filename:func`.")
    # Apply the function
    cell_content = "\n".join(modfunc(cell_content.split("\n")))
    return cell_content
