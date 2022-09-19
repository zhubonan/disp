"""
Administrative commands
"""
import click
from fireworks.core.launchpad import LaunchPad

from disp.database.api import SearchDB
from disp.database.odm import InitialStructureFile, ResFile

# Decorator of passing the SearchDB object
pass_db_obj = click.make_pass_decorator(SearchDB)


@click.group("admin")
@click.pass_context
def admin(ctx):
    """Admin commands"""

    lpad_file = ctx.obj.get("lpad_file")
    click.echo(f"Using launchpad file at {lpad_file}", err=True)
    lpad = LaunchPad.from_file(lpad_file)

    db_file = ctx.obj.get("db_file")
    click.echo(f"Using db file at {db_file}", err=True)
    sdb = SearchDB.from_db_file(db_file)
    # Pass the launch pad
    sdb.lpad = lpad

    ctx.obj = sdb


@admin.command("build-index")
@click.option("--disp-additional-field", multiple=True, help="Additional field to include.")
@click.option("--fw-additional-field", multiple=True, help="Additional field to include for fireworks.")
@click.option("--wf-additional-field", multiple=True, help="Additional field to include for fireworks's workflow collection.")
@pass_db_obj
def build_index(sdb, disp_additional_field, fw_additional_field, wf_additional_field):
    """
    Build the index for optimum query performance
    """
    click.echo(
        f"Requested to build the indices including additional fields: {disp_additional_field}, {fw_additional_field}, {wf_additional_field}."
    )
    sdb.build_indexes(
        additional_fields=disp_additional_field, wf_additional_fields=wf_additional_field, fw_additional_fields=fw_additional_field
    )


def update_spec(sdb, seed_name, project_name, spec_update, confirm):
    """Update the priority"""
    query = {"state": "READY"}
    if seed_name:
        query["spec.seed_name"] = seed_name
    if project_name:
        query["spec.project_name"] = project_name
    lpad: LaunchPad = sdb.lpad
    fw_ids = lpad.get_fw_ids(query)
    if confirm:
        ok = click.confirm(f"Update {len(fw_ids)} fireworks with {spec_update}?", abort=True)
    else:
        ok = True
    if ok:
        lpad.update_spec(fw_ids, spec_update)


@admin.command("update-priority")
@click.option("--seed")
@click.option("--project")
@click.option("--priority", type=int)
@pass_db_obj
def update_priority(sdb, seed, project, priority):
    """Update the priority"""
    if priority is not None:
        click.echo(f"Update with priority: {priority}")
        update_spec(sdb, seed, project, {"_priority": priority}, confirm=True)


@admin.command("update-category")
@click.option("--seed")
@click.option("--project")
@click.option("--category", help="Category to be updated to", multiple=True)
@pass_db_obj
def update_category(sdb, seed, project, category):
    """Update the category for the searches."""
    if category:
        category = list(category)
        click.echo(f"Update with category: {category}")
        update_spec(sdb, seed, project, {"_category": category}, confirm=True)


@admin.command("delete-entries")
@click.option("--project", required=True)
@click.option("--seed", required=False, help="Select seeds by regex")
@pass_db_obj
def delete_entries(db_obj, project, seed):
    """Delete entries in the data base"""
    from disp.database.api import ResFile

    if seed:
        qobj = ResFile.objects(project_name=project, seed_name=seed)
        qobj_i = InitialStructureFile.objects(project_name=project, seed_name=seed)
    else:
        qobj = ResFile.objects(project_name=project)
        qobj_i = InitialStructureFile.objects(project_name=project)

    click.echo(f"Number of DISP entries to be deleted for project {project}: {qobj.count()} ({qobj_i} initial structures)")

    # Checking fireworks
    lpad = db_obj.lpad
    # Search for the workflows
    wfs = lpad.workflows.find({"metadata.project_name": project}, {"nodes": 1})
    wf_ids = []
    fw_num_ids = []
    nwf = 0
    for wf in wfs:
        nwf += 1
        fw_num_ids.extend(wf["nodes"])
        wf_ids.append(wf["_id"])
    launch_ids = [entry["_id"] for entry in lpad.launches.find({"fw_id": {"$in": fw_num_ids}}, {"launch_id": 1})]

    click.echo(f"Number of workflows to be deleted from {lpad.name} @ {lpad.host}:")
    click.echo(f"Workflows  : {nwf} in collection {lpad.workflows.name}")
    click.echo(f"Fireworks  : {len(fw_num_ids)} in collection {lpad.fireworks.name}")
    click.echo(f"Launches   : {len(launch_ids)} in collection {lpad.launches.name}")

    # Search for related firworks
    # Search for related launches
    reply = click.confirm("Continue with deletion of DISP entries?")
    if reply is True:
        click.echo(f"Proceed with the deletion...")
        ndeleted = qobj.delete()
        click.echo(f"{ndeleted} SHELX entries deleted!")
        ndeleted = qobj_i.delete()
        click.echo(f"{ndeleted} initial structure entries deleted!")
    else:
        click.echo(f"Deletion of entries aborted.")

    reply = click.confirm("Continue with deletion of Fireworks entries?")
    if reply is True:
        click.echo(f"Proceed with the deletion...")
        ndeleted = lpad.workflows.delete_many({"_id": {"$in": wf_ids}})
        click.echo(f"{ndeleted.deleted_count} workflow entries deleted!")
        ndeleted = lpad.fireworks.delete_many({"fw_id": {"$in": fw_num_ids}})
        click.echo(f"{ndeleted.deleted_count} fireworks entries deleted!")
        ndeleted = lpad.launches.delete_many({"_id": {"$in": launch_ids}})
        click.echo(f"{ndeleted.deleted_count} launch entries deleted!")
    else:
        click.echo(f"Deletion of entries aborted.")
