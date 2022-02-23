"""
External code for bridging with AiiDA
"""
import pandas as pd

# pylint: disable=unexpected-keyword-arg, import-outside-toplevel


def make_aiida_calcfunction(row: pd.Series, group, dryrun: bool = False):
    """
    Perform and "fake" calculation to deposit the data in AiiDA's DAG

    Args:
        row (pd.Series): A slice of the collected database row
        group (Group): The group that the proxy Calcfunction should be placed into

    Return:
        A tuple of the output Dict and the proxy calculation itself
    """

    from aiida.engine import calcfunction
    from aiida.orm import StructureData, Dict

    output_items = [
        'energy_per_atom', 'energy', 'max_force', 'state', 'volume',
        'volume_per_fu', 'pressure', 'uuid', 'task_id'
    ]
    metadata_items = [
        'label', 'project_name', 'seed_name', 'unique_name', 'nform',
        'formula', 'struct_name'
    ]
    input_items = [
        'incar_entries',
        'functional',
        'potential_functional',
        'potential_mapping',
        'umap',
    ]

    # Build the input and output dictionary
    input_dict = {key: row[key] for key in input_items}
    input_dict['metadata'] = {key: row[key] for key in metadata_items}
    inputs = Dict(dict=input_dict)
    out_dict = Dict(dict={key: row[key] for key in output_items})

    structure_in = StructureData(pymatgen=row.pmg_struct).store()
    structure_out = StructureData(pymatgen=row.pmg_struct_relaxed)
    structure_in.label = row.label + ' SEARCH RAW'
    structure_out.label = row.label + ' RELAXED'

    @calcfunction
    def disp_atomate_calc(structure_in, inputs):
        _ = structure_in
        _ = inputs
        return {'output_structure': structure_out, 'misc': out_dict}

    if dryrun is True:
        return disp_atomate_calc(structure_in,
                                 inputs,
                                 metadata={'store_provenance': False})

    outputs = disp_atomate_calc(structure_in, inputs)
    calcfunc = outputs['misc'].get_incoming().one().node
    group.add_nodes(calcfunc)
    calcfunc.label = row.label + ' ATOMATE RELAX'
    return outputs, calcfunc
