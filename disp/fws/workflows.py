"""
Module for generating workflows.

These are primarily for running VASP relaxation using `atomate`
"""
from warnings import warn
from uuid import uuid4

from pymatgen import Structure
from pymatgen.io.vasp.inputs import Kpoints
from atomate.vasp.powerups import (add_modify_incar, set_execution_options,
                                   add_priority, add_common_powerups, Workflow,
                                   preserve_fworker,
                                   add_additional_fields_to_taskdocs)
from atomate.vasp.fireworks.core import OptimizeFW, StaticFW

from disp.database.odm import ResFile
from disp.analysis.airssutils import RESFile

from disp.utils import calc_kpt_tuple_recip

# pylint: disable=too-many-arguments, too-many-branches, too-many-statements, too-many-locals


def add_to_fw_spec(original_wf, metadata):
    """
    Add metadata to fireworks to make them easy for querying.

    Arags:
        original_wf (Workflow)
        metadata (dict): metadata to be added to "spec"

    Returns:
        modified workflows
    """
    for fwork in original_wf.fws:
        for key, value in metadata.items():
            fwork.spec[key] = value
    return original_wf


def get_relax_wf_std(structure,
                     kpoints_spacing,
                     incar_overrides,
                     potcar_overrides=None,
                     inset_extra_params=None,
                     name=None,
                     metadata=None,
                     category='atomate-wt',
                     walltime=3600 * 12,
                     job_type='full_opt_run',
                     priority=50):
    """
    Construct a relaxation workflow to be run though `atomate`.

    This is mainly for performing final high precision calculation and obtain
    high quality energy values.

    Args:
        structure (``Structure``, ``ResFile`` or ``RESFile``): input structure to be relaxed
        kpoints_sapcing (float): kpoints spacing the CASTEP convention (without the 2pi factor).
        incar_overrides (dict): Overrides for the input set ``MPRelaxSet``.
        potcar_overrides (dict): Overrides for the potcars of the input set ``MPRelaxSet``.
        inset_extra_params (dict): Extra keyword parameters to be passed for ``MPRelaxSet``.
        name (str, optional): Name for the relaxation, must given if a raw ``Structure`` is used.
        metadata (dict, optional): A dictionary of metadata to be attached. This dictionary applied to the
          ``metadata`` of the Workflow, ``spec`` of the firework and act as additional fields for the task documents.
        category (list, str): Category to be set for the fireworks for correct run time placement.
            Default to ``atomate``.

    Returns:
        Workflow: assembled ``Workflow`` object ready to be launched by the lanchpad or used for
            fruther processing.
    """

    default_metadata = {'disp_type': 'atomate-relax'}
    if isinstance(structure, RESFile):
        name = structure.label if not name else name
        structure = structure.structure
    elif isinstance(structure, ResFile):
        res_doc = structure
        res = RESFile.from_string(res_doc.content)
        name = res.label if not name else name
        structure = res.structure
        default_metadata['project_name'] = res_doc.project_name
        default_metadata['seed_name'] = res_doc.seed_name
        default_metadata['struct_name'] = res_doc.struct_name

    elif isinstance(structure, Structure):
        pass
    else:
        raise ValueError('Unsupported structure input: {}'.format(
            type(structure)))

    if name is None:
        raise RuntimeError('Must give a name for the structure for provenance')

    kpoints = Kpoints(
        kpts=(calc_kpt_tuple_recip(structure, kpoints_spacing), ))
    # Optimisation workflow
    inset_extra_params = {} if inset_extra_params is None else inset_extra_params
    opt = OptimizeFW(structure,
                     name=name + ' RELAX',
                     max_force_threshold=None,
                     job_type=job_type,
                     override_default_vasp_params={
                         'user_potcar_functional': 'PBE_54',
                         'user_incar_settings': incar_overrides,
                         'user_kpoints_settings': kpoints,
                         'user_potcar_settings': potcar_overrides,
                         **inset_extra_params,
                     })
    # Static workflow after the optimisation - using the same calculation folder
    # Note that we have to override the potcars as the MPStaticSet is dumb enough
    # to not ensure POTCAR consistentcy!!!!
    # Without this it will use the MPRelaxSet with the default functional/mappings
    static = StaticFW(parents=opt,
                      name=name + ' STATIC',
                      vasp_input_set_params={
                          'user_potcar_functional': 'PBE_54',
                          'user_potcar_settings': potcar_overrides,
                      })

    # Assemble in to a workflow
    wfl = Workflow([opt, static], name=name + ' RELAX')
    # Add common powerups - what dose this do
    wfl = add_common_powerups(wfl)

    # Modify incar task is always needed for applying machine specfic setings
    if 'ISMEAR' in incar_overrides:
        # Sepectral treatment - keep the same ISMEAR as in relax
        # The MPStaticSet tends to use ISMEAR=-5 - we don't always want that to take place for
        # all cases, this also gives wrong forces/stresses in the static calculation, making it difficult
        # to judge the quality of the relaxation
        incar_modify = {
            'incar_update':
            '>>incar_update<<',  # Taking incar update from the worker specific settings
            'incar_dictmod': {
                '_set': {
                    'ISMEAR': incar_overrides.get('ISMEAR')
                }
            },
        }
        wfl = add_modify_incar(wfl, modify_incar_params=incar_modify)
    else:
        wfl = add_modify_incar(wfl)

    # Ensure we start from atomic charges - applying the MAGMOM in the INCAR
    # This is because we don't write the WAVECAR, but sometime VASP fails to reset ICHARG when the
    # INCAR is invalid.....
    wfl = add_modify_incar(wfl,
                           modify_incar_params={'incar_update': {
                               'ICHARG': 2
                           }},
                           fw_name_constraint='STATIC')

    # Add executation options - limit to specific categories
    wfl = set_execution_options(wfl, category=category)

    # Set the metadata
    metadata = {} if metadata is None else metadata
    # Update the default metadata with the existing metadata
    default_metadata.update(metadata)
    # Swap it around
    metadata = default_metadata

    if not metadata:
        warn(
            'No metadata is set - workflow identification solely relying on name of the structure'
        )
        unique_name = None
    else:
        project_name = metadata.get('project_name')
        if project_name is None:
            warn('No `project_name` for the structure.')
        seed_name = metadata.get('seed_name')
        if seed_name is None:
            warn('No `seed_name` for the structure.')
        struct_name = metadata.get('struct_name')
        if struct_name is None:
            warn('No `struct_name` for the structure.')
        unique_name = '{}:{}:{}'.format(project_name, seed_name, struct_name)

    # Set a uuid for metadata - unique link between the workflow and the task document
    # otherwise integer task_id may not work after export/import
    metadata['uuid'] = str(uuid4())
    if unique_name:
        metadata['unique_name'] = unique_name

    # Add metadata to workflows
    wfl.metadata.update(metadata)
    # Make sure task document includes the metadata as well
    wfl = add_additional_fields_to_taskdocs(wfl, update_dict=metadata)

    # Add metadata to fireworks
    metadata['_walltime_seconds'] = walltime
    wfl = add_to_fw_spec(wfl, metadata)

    # Add priority - children priority is higher to bias towards finishing each workflow
    wfl = add_priority(wfl, priority, child_priority=priority + 1)

    # This is needed so the static calcualtion takes place with the same worker
    wfl = preserve_fworker(wfl)
    return wfl


# STANDARD INCAR OVERRIDES - not all fields are needed. Taken from SMTG wiki
# Modified to use U=4.0 for Fe, consistent with the Wang et al. 2006
# Use PBE functional
def get_incar_overrides_base():
    """Returns a base modification set for the INCAR"""
    base_overrides = {
        'ALGO': 'Normal',
        'LASPH': True,
        'EDIFFG': -0.03,
        'LMAXMIX': 4,
        'EDIFF_PER_ATOM': 1e-6,
        'KPAR': 2,
        'NELMIN': 6,
        'ENMAX': 520,
        'ENCUT': 520,
        'IBRION': 2,
        'ICHARG': 1,
        'ISIF': 3,
        'ISMEAR': 0,
        'ISPIN': 2,
        'LDAU': True,
        'LDAUJ': {
            'F': {
                'Co': 0,
                'Cr': 0,
                'Fe': 0,
                'Mn': 0,
                'Mo': 0,
                'Ni': 0,
                'V': 0,
                'W': 0,
                'Cu': 0
            },
            'O': {
                'Co': 0,
                'Cr': 0,
                'Fe': 0,
                'Mn': 0,
                'Mo': 0,
                'Ni': 0,
                'V': 0,
                'W': 0,
                'Cu': 0
            }
        },
        'LDAUL': {
            'F': {
                'Co': 2,
                'Cr': 2,
                'Fe': 2,
                'Mn': 2,
                'Mo': 2,
                'Ni': 2,
                'V': 2,
                'W': 2,
                'Cu': 2
            },
            'O': {
                'Co': 2,
                'Cr': 2,
                'Fe': 2,
                'Mn': 2,
                'Mo': 2,
                'Ni': 2,
                'V': 2,
                'W': 2,
                'Cu': 2
            }
        },
        'LDAUTYPE': 2,
        'LDAUPRINT': 1,
        'GGA': 'PE',
        'LDAUU': {
            'F': {
                'Co': 3.32,
                'Cr': 3.7,
                'Fe': 4.0,
                'Mn': 3.9,
                'Mo': 4.38,
                'Ni': 6.2,
                'V': 3.25,
                'W': 6.2,
                'Cu': 5.17
            },
            'O': {
                'Co': 3.32,
                'Cr': 3.7,
                'Fe': 4.0,
                'Mn': 3.9,
                'Mo': 4.38,
                'Ni': 6.2,
                'V': 3.25,
                'W': 6.2,
                'Cu': 5.17
            }
        },
        'LORBIT': 11,
        'LREAL': False,
        'LWAVE': False,
        'NELM': 200,
        'NSW': 100,
        'PREC': 'Accurate',
        'SIGMA': 0.05,
        'MAGMOM': {
            'Ce': 5,
            'Ce3+': 1,
            'Co': 5,
            'Co3+': 0.6,
            'Co4+': 1,
            'Cr': 5,
            'Dy3+': 5,
            'Er3+': 3,
            'Eu': 10,
            'Eu2+': 7,
            'Eu3+': 6,
            'Fe': 5,
            'Gd3+': 7,
            'Ho3+': 4,
            'La3+': 0.6,
            'Lu3+': 0.6,
            'Mn': 5,
            'Mn3+': 4,
            'Mn4+': 3,
            'Mo': 5,
            'Nd3+': 3,
            'Ni': 5,
            'Pm3+': 4,
            'Pr3+': 2,
            'Sm3+': 5,
            'Tb3+': 6,
            'Tm3+': 2,
            'V': 5,
            'W': 5,
            'Yb3+': 1
        }
    }
    return base_overrides
