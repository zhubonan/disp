"""
Module containing the database related CLI commands
"""
import json
import os
import subprocess
from collections import namedtuple
from pathlib import Path

import click
from fireworks.core.firework import Firework
from fireworks.core.launchpad import LaunchPad
from tabulate import tabulate
from tqdm import tqdm

from disp.database import DB_FILE, SearchDB

# pylint: disable=invalid-name,too-many-arguments,import-outside-toplevel


def common_query_options(func):
    """Added some common options to the function"""
    func = click.option("--project", help="Regex the project")(func)
    func = click.option("--seed", help="Regex of the seed")(func)
    func = click.option("--state", help="State of the FW", type=click.Choice(list(Firework.STATE_RANKS)))(func)
    func = click.option("--query", "-q", help="Raw query to use")(func)
    return func


def generate_fw_query(project, seed, state, query=None):
    """Helper function to generate query dictionary for filtering Fireworks"""
    if not query:
        query = {}

    if project:
        query["spec.project_name"] = {"$regex": project}

    if seed:
        query["spec.seed_name"] = {"$regex": seed}

    if state:
        query["state"] = state.upper()

    return query


@click.group("db")
@click.pass_context
def db(ctx):
    """Options for the database"""

    db_file = ctx.obj.get("db_file")
    click.echo(f"Using db file at {db_file}", err=True)
    ctx.obj = SearchDB.from_db_file(db_file)


# Decorator of passing the SearchDB object
pass_db_obj = click.make_pass_decorator(SearchDB)
pass_lpad_obj = click.make_pass_decorator(LaunchPad)


@db.command("list-projects")
@common_query_options
@pass_db_obj
def list_projects(db_obj, seed, project, state, query):
    """
    List the matching projects
    """
    collection = db_obj.database["fireworks"]
    query = generate_fw_query(project, seed, state, query)
    res = collection.distinct("spec.project_name", query)
    for item in res:
        print(item)


@db.command("list-seeds")
@common_query_options
@pass_db_obj
def list_seeds(db_obj, seed, project, state, query):
    """
    List the matching seeds
    """
    collection = db_obj.database["fireworks"]
    query = generate_fw_query(project, seed, state, query)
    res = collection.distinct("spec.seed_name", query)
    for item in res:
        print(item)


@db.command("summary")
@click.option("--workflows/--no-workflows", is_flag=True, default=True)
@click.option("--project-regex", "-pr", help="Project to include, supports regex.")
@click.option("--project", "-p", multiple=True, help="Project to include, supports multiple values.")
@click.option("--seed-regex", "-sr", help="Seeds to include, support regex")
@click.option("--seed", "-sr", multiple=True, help="Seeds to be included, support multiple values.")
@click.option("--state", multiple=True, type=click.Choice(list(Firework.STATE_RANKS)), help="Only include matches with these states")
@click.option("--show-priority", default=False, is_flag=True, help="Show the priority of workflows instead")
@click.option("--per-project", help="Summarise per project", is_flag=True, default=False)
@click.option("--no-res", is_flag=True, help="Do not query the search structure counts", default=False)
@click.option("--atomate", "-ato", is_flag=True, default=False, help="Show the results on the atomate collection instead.")
@click.option("--singlepoint", "-sp", is_flag=True, default=False, help="Show only singlepoint results instead.")
@click.option("--verbose", "-v", is_flag=True, default=False)
@click.option("--json", is_flag=True, default=False)
@pass_db_obj
def summary(
    db_obj,
    project,
    state,
    seed,
    per_project,
    workflows,
    show_priority,
    atomate,
    no_res,
    verbose,
    singlepoint,
    seed_regex,
    project_regex,
    json,
):
    """
    Display a summary of number of structures in the database
    """
    import pandas as pd

    df = db_obj.show_struct_counts(
        project_regex,
        seed_regex,
        state,
        include_workflows=workflows,
        include_atomate=atomate,
        show_priority=show_priority,
        include_res=not no_res,
        include_singlepoint=singlepoint,
        projects=project,
        seeds=seed,
        verbose=verbose,
    )
    if per_project:
        if not show_priority:
            df = df.groupby("project").sum()
        else:
            df = df.groupby("project").mean()

    if len(df) == 0:
        click.echo("No data available")
        return
    if json:
        click.echo(df.to_json())
        return
    with pd.option_context("display.max_rows", 99999, "display.max_colwidth", 120):
        click.echo(df)


@db.command("throughput")
@click.option(
    "--group-by",
    "-g",
    help="Group results with",
    default="project_name",
    type=click.Choice(["seed_name", "project_name", "worker_name", "uid"]),
)
@click.option("--projects", "-p", multiple=True, help="Filter by project names.")
@click.option("--seeds", "-s", multiple=True, help="Filter by seed names.")
@click.option("--aggregate", "-agg", default="H")
@click.option("--past-days", "-p", default=1, type=float, help="Include only the past N days")
@click.option("--plot/--no-plot", default=True, help="Show the bar plot or not.")
@click.option("--csv", is_flag=True, default=False, help="Print in CSV format.")
@click.option("--atomate", "-ato", is_flag=True, default=False, help="Show the results on the atomate collection instead.")
@pass_db_obj
def throughput(db_obj, group_by, past_days, projects, seeds, aggregate, plot, csv, atomate):
    """
    Summarise search throughput in certain past period
    """
    import sys

    import pandas as pd

    if atomate:
        dataframe = db_obj.throughput_summary_atomate(
            past_days=past_days, projects=projects, seeds=seeds, aggregate=aggregate, group_by=group_by, plot=plot
        )
    else:
        dataframe = db_obj.throughput_summary(
            past_days=past_days, projects=projects, seeds=seeds, aggregate=aggregate, group_by=group_by, plot=plot
        )
    if dataframe is None:
        click.echo(f"No results found for the past {24 * past_days:.0f} hours.")
        return

    cols = ["/".join(col.split("/")[-2:]) for col in dataframe.columns]
    dataframe.columns = cols
    dataframe.fillna(0.0, inplace=True)
    if csv:
        dataframe.to_csv(sys.stdout)
    else:
        with pd.option_context("display.max_rows", 99999, "display.max_colwidth", 120):
            print(dataframe)


def get_launch_info(fws, query):
    """
    Acquire information about the launches

    Here we use the aggregation pipline, which is much faster
    than the original fireworks interface....
    """

    fw_info = namedtuple("FWInfo", ["fw_id", "seed_name", "project_name", "state", "launch_dir"])

    res = fws.aggregate(
        [
            {"$match": query},
            {"$lookup": {"from": "launches", "localField": "fw_id", "foreignField": "fw_id", "as": "launches"}},
            {"$project": {"fw_id": 1, "spec.seed_name": 1, "spec.project_name": 1, "state": 1, "launches.launch_dir": 1}},
        ]
    )

    output = []
    for tmp in res:
        if tmp["launches"]:
            launch_dir = tmp["launches"][-1]["launch_dir"]
        else:
            launch_dir = None
        output.append(
            fw_info(
                seed_name=tmp["spec"]["seed_name"],
                project_name=tmp["spec"]["project_name"],
                fw_id=tmp["fw_id"],
                launch_dir=launch_dir,
                state=tmp["state"],
            )
        )

    return output


@db.command("launch-dirs")
@click.option("--raw", is_flag=True, help="Raw format, no header.")
@click.option("--pull", is_flag=True, help="Pull the data using rsync")
@click.option("--pull-mapping", help="A dictionary maps user names to remote machines names.")
@common_query_options
@pass_db_obj
def launch_dirs(db_obj, project, seed, query, state, raw, pull, pull_mapping):
    """
    Display information about the launch directories.

    Optionally, pull the working directory to the current local folder using
    rsync for inspection. For this to work a mapping between key words to the
    remote machines are needed. For example, if your username is "user1" on
    remote machine "remote1", pass `--pull-mapping '{"user1": "remote1"}'`.
    For this to work the user name must present in the full paths, which is
    usually the case. rsync will be used for data transfer.
    """

    # Here it assumed that the db collection is at the same as that of the
    # fireworks collection under the same mongodb 'database'
    query = generate_fw_query(project, seed, state, query)

    fws = db_obj.database.fireworks

    data = get_launch_info(fws, query)

    if raw:
        table = tabulate(data, tablefmt="plain")
    else:
        table = tabulate(data, headers="keys")

    if not pull:
        click.echo(table)
        return

    # Pull data to local directory
    click.echo("Pulling remote launch folders to the current directory...")
    mapping = json.loads(pull_mapping)  # pylint: disable=eval-used
    click.echo(f"Mapping of the remote hosts: {mapping}")

    # Group entry in to different machines
    machines_and_paths = {}
    for info in data:
        # Populate machine_and_paths dictionary
        for key, value in mapping.items():
            if key in info.launch_dir:
                if value not in machines_and_paths:
                    machines_and_paths[value] = []
                machines_and_paths[value].append(info.launch_dir)
                break

    # Call rsync to pull the working directories
    for key, value in machines_and_paths.items():
        click.echo(f"Pulling data from machine: {key}")
        cmd = ["rsync", "-av"]
        parent = os.path.split(value[0])[0]
        for path in value:
            dirname = os.path.split(path)[1]
            cmd.append(f"--include={dirname}/***")

        cmd.extend(["--exclude=*", f"{key}:{parent}/", "./"])
        subprocess.call(cmd)
    click.echo(table)


@db.command("launch-stats")
@common_query_options
@click.option("--cycles", type=int, help="Expected ionic steps for computing the projected time.")
@pass_db_obj
def launch_stats(db_obj, project, seed, query, state, cycles):
    """
    (experimental) Obtain statistics of the runs using snapshots pulled down to
    the local directory.
    """
    from glob import glob

    import pandas as pd

    from disp.castep_analysis import SCFInfo

    query = generate_fw_query(project, seed, state, query)
    # DataFrame contains the basic data
    dframe = pd.DataFrame(get_launch_info(db_obj.database.fireworks, query))
    dframe["workdir"] = dframe["launch_dir"].apply(lambda x: os.path.split(x)[1])

    summaries = []
    for _, row in dframe.iterrows():
        workdir = row.workdir
        castep_file = list(glob(workdir + "/*.castep"))
        if not castep_file:
            click.echo(
                ("WARNING: requested FW <{}> of <{}>-" "<{}> is not avalible locally").format(row.fw_id, row.project_name, row.seed_name)
            )
            continue
        castep_file = castep_file[0]
        _summary = SCFInfo(castep_file).get_summary()
        _summary["workdir"] = workdir
        _summary["castep_file"] = castep_file
        summaries.append(_summary)

    if not summaries:
        click.echo("No data to show - did you forget to pull runs using launch-dirs?")
        click.echo("Aborting...")
        return

    sdframe = pd.DataFrame(summaries)
    dframe = dframe.merge(sdframe, how="inner")
    dframe["suffix"] = dframe["castep_file"].apply(lambda x: x.split("-")[-1].replace(".castep", ""))
    dframe["total_time"] /= 3600

    columns = [
        "fw_id",
        "suffix",
        "seed_name",
        "project_name",
        "avg_ionic_time",
        "avg_elec_time",
        "avg_elec_steps",
        "ionic_steps",
        "total_time",
    ]

    if cycles:
        dframe["pj_time"] = dframe["avg_ionic_time"] * cycles / 3600
        columns.append("pj_time")
    to_show = dframe[columns].set_index("fw_id").sort_values("project_name")
    click.echo(tabulate(to_show, headers="keys"))


@db.command("retrieve-project")
@click.option("--project", required=True)
@click.option("--seed", required=False, help="Select seeds by regex")
@click.option("--struct-name", required=False, help="Select strucures by regex")
@click.option("--include-init-structure/--no-include-init-structure", default=False)
@click.option("--include-seed/--no-include-seed", default=False)
@click.option("--include-param/--no-include-param", default=False)
@pass_db_obj
def retrieve_project(db_obj, project, seed, struct_name, include_init_structure, include_seed, include_param):
    """
    Retrieve the RES files for a particular project
    """

    click.echo(f"Retrieving data for project: {project}")
    filters = {}
    if seed:
        filters["seed_name"] = {"$regex": seed}
    if struct_name:
        filters["struct_name"] = {"$regex": struct_name}
    results = db_obj.retrieve_project(
        project_name=project,
        additional_filters=filters,
        include_seed=include_seed,
        include_param=include_param,
        include_initial_structure=include_init_structure,
    )
    click.echo("Writing files to disk...")
    # Write data to the disk
    total = results.count()
    for res in tqdm(results, total=total):
        Path(res["struct_name"] + ".res").write_text(res.content)
        # Write additional contents
        if res.param_file:
            Path(res["struct_name"] + ".param").write_text(res.param_file.content)
        if res.init_structure_file:
            Path(res["struct_name"] + "-orig.cell").write_text(res.init_structure_file.content)
        if res.seed_file:
            Path(res["struct_name"] + "-seed.cell").write_text(res.seed_file.content)

    click.echo("Done")
