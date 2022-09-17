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
    click.echo(f"Using launchpad file at {lpad_file}")
    lpad = LaunchPad.from_file(lpad_file)

    db_file = ctx.obj.get("db_file")
    click.echo(f"Using db file at {db_file}")
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
@click.option("--seed")
@click.option("--project")
@click.option("--struct")
@click.option("--commit", is_flag=True, default=False)
@pass_db_obj
def delete_data(sdb, seed, project, struct, commit):
    """Delete DISP entries and associated workflows (Use with extreme caution)"""

    query = {}
    disp_query = {}
    if seed:
        query["metadata.seed_name"] = seed
        disp_query["seed_name"] = seed
    if project:
        query["metadata.project_name"] = project
        disp_query["project_name"] = project
    if struct:
        query["metadata.struct_name"] = struct
        disp_query["struct_name"] = struct
    if not query:
        click.echo("No selection condition is passed")
        raise click.Abort()
    lpad: LaunchPad = sdb.lpad
    wf_ids = lpad.get_wf_ids(query)

    ndisp_entries = ResFile.objects(**disp_query).count()
    ndisp_entries_init = InitialStructureFile.objects(**disp_query).count()
    project_names_to_delete = {x.project_name for x in ResFile.objects(**disp_query)}
    seed_names_to_delete = {x.seed_name for x in ResFile.objects(**disp_query)}

    click.echo(f"Number of workflows to be deleted: {len(wf_ids)}")
    click.echo(f"Number of SHELX entries and initial structures to be deleted: {ndisp_entries}/{ndisp_entries_init}")
    click.echo(f"Deletion involves seeds: {seed_names_to_delete}, projects: {project_names_to_delete}")

    if commit:
        ok = click.confirm(f"Are you sure you want to delete the data?\nThis operation cannot be reversed!", abort=True)
        if ok:
            for wf_id in wf_ids:
                lpad.delete_wf(wf_id)
            for doc in ResFile.objects(**disp_query):
                doc.delete()
            for doc in InitialStructureFile.objects(**disp_query):
                doc.delete()
            click.echo(f"Deletion completed.")
    else:
        click.echo(f"This is a dryrun - nothing has been deleted.")
