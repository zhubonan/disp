"""
Module for gathering data from the atomate database/RES files
"""
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from pymatgen.core import Structure
from pymatgen.entries.computed_entries import ComputedEntry
from pymatgen.io.vasp.inputs import Poscar

from disp.analysis.airssutils import RESFile
from disp.database import SearchDB


class DataCollector:
    """
    Collect the useful data from atomate task document into a dataframe
    """

    BASE_PROJECTION = [
        "struct_name",
        "output.forces",
        "input.incar",
        "input.hubbards",
        "input.structure",
        "output.energy_per_atom",
        "output.energy",
        "output.structure",
        "output.stress",
        "seed_name",
        "state",
        "project_name",
        "input.xc_override",
        "input.pseudo_potential",
        "uuid",
        "unique_name",
        "completed_at",
        "task_id",
    ]

    def __init__(self, search_db: SearchDB, filters: dict, extra_projections=None, task_collection="atomate_tasks"):
        """
        Instantiate a data collector object.

        Args:
            search_db (SearchDB): A `SearchDB` instance
            filters (dict): filters to be used for the `find` method.
            projection (optional, list): A list of properties to be projected
        """
        self.filters = filters
        self.sdb = search_db
        self.atomate_collection = getattr(search_db.database, task_collection)
        self.raw_documents = []

        # Collect the extra projections
        if extra_projections is None:
            extra_projections = []
        self.projection = list(self.BASE_PROJECTION)
        self.projection.extend(extra_projections)

    def collect(self):
        """
        Collect the data into a dataframe from the MongoDB server
        """
        records = []
        at_coll = self.atomate_collection
        self.raw_documents = []

        docs = at_coll.find(self.filters, projection=self.projection)
        for entry in docs:
            # Record the raw dictionary document
            self.raw_documents.append(entry)
            # Compute the maximum force
            forces = np.array(entry["output"]["forces"])
            fmax = np.linalg.norm(forces, axis=1)
            # Note that this is the output structure
            structure = Structure.from_dict(entry["output"]["structure"])
            input_structure = Structure.from_dict(entry["input"]["structure"])

            # For INCAR items, enforce a lower case convention for the key names
            incar_entries = {key.lower(): value for key, value in entry["input"]["incar"].items()}
            stress = entry["output"]["stress"]
            if stress:
                pressure = get_pressure_gpa(stress)
            else:
                pressure = None

            poscar = Poscar(structure=structure)
            potcar_mapping = dict(zip(poscar.site_symbols, entry["input"]["pseudo_potential"]["labels"]))
            entry_dict = {
                "label": entry["struct_name"],
                "struct_name": entry["struct_name"],
                "energy_per_atom": entry["output"]["energy_per_atom"],
                "energy": entry["output"]["energy"],
                "max_force": fmax.max(),
                "state": entry["state"],
                "project_name": entry["project_name"],
                "seed_name": entry["seed_name"],
                "umap": entry["input"]["hubbards"],
                "functional": entry["input"]["xc_override"],
                "pmg_struct_relaxed": structure,
                "pmg_struct": input_structure,
                "volume": structure.volume,
                "volume_per_fu": structure.volume / structure.composition.get_reduced_composition_and_factor()[1],
                "nform": structure.composition.get_reduced_composition_and_factor()[1],
                "formula": structure.composition.reduced_formula,
                "pressure": pressure,
                "potential_functional": entry["input"]["pseudo_potential"]["functional"],
                "potential_mapping": potcar_mapping,
                "uuid": entry["uuid"],
                "task_id": entry["task_id"],
                "unique_name": entry["unique_name"],
                "completed_at": entry["completed_at"],
                "incar_entries": incar_entries,
                # Extend all other incar entries
                **incar_entries,
            }
            records.append(entry_dict)

        atomate_df = pd.DataFrame(records).sort_values("energy_per_atom")
        return atomate_df


# pylint: disable=too-many-arguments
def get_entry(
    dataframe: pd.DataFrame,
    pmg_col="pmg_struct",
    label_col="label",
    uuid_col="uuid",
    umap_col="umap",
    xc_col="functional",
    eng_col="energy",
) -> List[ComputedEntry]:
    """
    Create entry from the dataframe containing data, typically returned from the
    `get_relax_records` function.
    """
    pd_entries = []
    for idx, row in dataframe.iterrows():
        comp = row[pmg_col].composition
        attrs = {
            "struct_name": row[label_col],
            "entry_type": "MP" if "mp" in row[label_col] else "AIRSS",
            "structure_uuid": row[uuid_col],
            "calc_u": row[umap_col],
            "functional": row[xc_col],
            "volume": row[pmg_col].volume,
            "dataframe_idx": idx,  # Store the entry index in the original dataframe
        }
        pd_entries.append(ComputedEntry(comp, energy=row[eng_col], parameters=attrs))
    return pd_entries


def export_dataframe_as_res(dataframe: pd.DataFrame, comment: str = "VASP export", extra_comments: list = None, stress_key=None):
    """
    Write all of the structure in a dataframe into RES format for export and visualisation
    """
    comments = [comment, *extra_comments]
    for _, row in dataframe.iterrows():
        relaxed = row.pmg_struct_relaxed
        res = RESFile(
            relaxed,
            {
                "enthalpy": row.energy_per_atom * len(relaxed.sites),
                "volume": row.volume_per_fu * row.nform_refine,
                # The stress data may not existsk
                "pressure": 0.0 if stress_key in row.index or stress_key is None else row[stress_key],
                "label": row.label,
                "rem": comments + [f"{key} = {row[key]}" for key in row.index if "struct" not in key],
            },
        )
        content = "\n".join(res.to_res_lines())
        Path(f"exports/{row.label}.res").write_text(content)


def get_pressure_gpa(stress: list):
    """
    Convert the stress tensor to isostatic pressure in GPa
    """
    stress = np.asarray(stress)
    # 1 kBar = 0.1 GPa
    return np.trace(stress) * 0.1 / 3.0


def deposit_into_aiida(row, group, dryrun):
    """
    Deposit the results from atomate DataFrame into aiida by creating a "fake" calcfunction.

    The resulting calcfunction has the structure and input parameters of the underlying atomate
    task as the inputs, and have the output structure and computed properties as the outputs.

    Note: This function requires an aiida-core installation with a profile loaded.

    Args:
        row (pandas.Series): A single row of the DataFrame return by the Collector.
        group (aiida.orm.Group): A aiida.orm.Group instance that the calcfunctions should be added to.
        dryrun (bool): Wether to perform a dryrun

    Returns:
        A dictionary containing the output structure and computed properties.
        If not performing a dryrun, the CalcFunctionNode is also returned.
    """
    # pylint: disable=unexpected-keyword-arg
    from aiida.engine import (
        calcfunction,  # pylint: disable=import-outside-toplevel
    )
    from aiida.orm import (  # pylint: disable=import-outside-toplevel
        Dict,
        StructureData,
    )

    output_items = ["energy_per_atom", "energy", "max_force", "state", "volume", "volume_per_fu", "pressure", "uuid", "task_id"]
    metadata_items = ["label", "project_name", "seed_name", "unique_name", "nform", "formula", "struct_name"]
    input_items = [
        "incar_entries",
        "functional",
        "potential_functional",
        "potential_mapping",
        "umap",
    ]

    # Build the input and output dictionary
    input_dict = {key: row[key] for key in input_items}
    input_dict["metadata"] = {key: row[key] for key in metadata_items}
    inputs = Dict(dict=input_dict)
    out_dict = Dict(dict={key: row[key] for key in output_items})

    structure_in = StructureData(pymatgen=row.pmg_struct).store()
    structure_out = StructureData(pymatgen=row.pmg_struct_relaxed)
    structure_in.label = row.label + " INPUT"
    structure_out.label = row.label + " RELAXED"

    @calcfunction
    def disp_atomate_calc(structure_in, calc_inputs):
        _ = structure_in
        _ = calc_inputs
        return {"output_structure": structure_out, "misc": out_dict}

    if dryrun is True:
        return disp_atomate_calc(structure_in, inputs, metadata={"store_provenance": False})
    outputs = disp_atomate_calc(structure_in, inputs)
    calcfunc = outputs["misc"].get_incoming().one().node
    group.add_nodes(calcfunc)
    calcfunc.label = row.label + " ATOMATE RELAX"
    return outputs, calcfunc
