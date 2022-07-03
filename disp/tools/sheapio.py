"""
Wrapper for using SHEAP
"""
from pathlib import Path
from typing import List, Union
from collections import namedtuple
from copy import deepcopy
from io import StringIO

from subprocess import Popen, PIPE, DEVNULL
from ase.io import read
from ase import Atoms

import numpy as np

import pandas as pd

SHEAP_OPT_MAP = dict(
    format_in='-read',
    metadata_file='-m',
    verbose='-v',
    quiet='-q',
    dim='-dim',
    scale='-scale',
    similarity_threshold='-st',
    cost_threshold='-et',
    use_tsne='-tsne',
    use_umap='-umap',
    perplexity='-p',
    knn='-k',
    uniform_random='-up',
    uniform_random_packing='-f',
    compression_factor='-pca',
    kl_divergence_loss='-kl',
    cross_entropy_loss='-ce',
    hard_sphere='-hs',
    hard_sphere_core_strength='-cs',
    hard_sphere_steps='-gs',
    hard_sphere_tol='-grtol',
    sphere_radius='-rs',
)


class SheapParams:
    """Parameters for SHEAP"""

    # Default parameters that we use here
    _default = {
        'format_in': 'vec',
        'metadata_file': None,
        'verbose': False,
        'dim': 2,
        'quiet': False,
        'scale': True,
        'similarity_threshold': 0.0,
        'cost_threshold': 0.0,
        'use_tsne': False,
        'use_umap': False,
        'perplexity': 15.0,
        'knn': 15,
        'uniform_random': False,
        'uniform_random_packing': False,
        'compression_factor': 10.0,
        'kl_divergence_loss': False,
        'cross_entropy_loss': True,
        'hard_sphere': False,
        'hard_sphere_core_strength': 1.0,
        'hard_sphere_steps': 500,
        'hard_sphere_tol': 2.0,
        'sphere_radius': 0.02
    }

    # Programs default
    _program_default = {
        'format_in': 'xyz',
        'metadata_file': None,
        'verbose': False,
        'dim': 0,
        'quiet': False,
        'scale': True,
        'similarity_threshold': 0.0,
        'cost_threshold': 0.0,
        'use_tsne': False,
        'use_umap': False,
        'perplexity': 15.0,
        'knn': 15,
        'uniform_random': False,
        'uniform_random_packing': False,
        'compression_factor': 10.0,
        'kl_divergence_loss': False,
        'cross_entropy_loss': True,
        'hard_sphere': False,
        'hard_sphere_core_strength': 1.0,
        'hard_sphere_steps': 500,
        'hard_sphere_tol': 2.0,
        'sphere_radius': 0.02
    }

    def __init__(self, params):
        self.parameters = deepcopy(self._default)
        for key, value in params.items():
            if key not in self._default:
                raise ValueError(
                    f'Key: {key} is not a valid input option for SHEAP')
            self.parameters[key] = value

    def get_cmdline_args(self) -> List[str]:
        """
        Return a list of command line argument to be passed to SHEAP
        """
        output = ['sheap']
        for name, value in self.parameters.items():
            # Using default value - just skip passing this argument
            # this simulate the usage without the wrapper
            if value == self._program_default[name]:
                continue

            if value is False or value is None:
                continue
            if value is True:
                output.append(SHEAP_OPT_MAP[name])
                continue
            output.append(SHEAP_OPT_MAP[name])
            output.append(str(value))
        return output

    def __repr__(self) -> str:
        output = 'SheapParam(' + self.parameters.__repr__() + ')'
        return output


SheapMetadata = namedtuple(
    'SheapMetadata',
    ('label', 'natoms', 'form', 'sym', 'volume', 'enthalpy', 'nfound'),
    defaults=('SHEAP-IN', 1, 'Al', 'P1', -0.1, -0.1, 1))


def write_sheap_vec(handle,
                    vecs: Union[np.array, List[np.array]],
                    metadata=None):
    """
    Write the inputs of SHEAP to a file-like object
    """
    if metadata is None:
        metadata = [SheapMetadata() for i in range(len(vecs))]
    for meta, vec in zip(metadata, vecs):
        # Size of the vector
        handle.write(str(len(vec)) + '\n')
        # Main vector
        handle.write('\t'.join(map(str, vec)))
        handle.write('\n')
        # Metadata
        line = f'{meta.label}\t{meta.natoms:d}\t{meta.form}\t\"{meta.sym}\"\t{meta.volume}\t{meta.enthalpy}\t{meta.nfound:d}\n'
        handle.write(line)


SheapOut = namedtuple('SheapOut',
                      ('labels', 'nforms', 'form', 'sym', 'volume', 'enthalpy',
                       'nfound', 'radius', 'coords', 'nitems', 'cost'))


def run_sheap(vectors: Union[np.ndarray, List[np.ndarray]],
              sheap_param: SheapParams,
              metadata: bool = None,
              no_stdout: bool = False,
              dump_output=False) -> SheapOut:
    """Run SHEAP and get the results back"""

    cmdline = sheap_param.get_cmdline_args()

    # Silence the stderr?
    stderr = DEVNULL if no_stdout else None

    with Popen(cmdline,
               stdin=PIPE,
               stdout=PIPE,
               universal_newlines=True,
               stderr=stderr) as popen:
        # Write to stdin
        input_buffer = StringIO()
        write_sheap_vec(input_buffer, vectors, metadata)
        input_buffer.seek(0)
        lines = input_buffer.read()

        output, _ = popen.communicate(lines)
    if dump_output:
        with open('sheap.out', 'w') as fhandle:
            fhandle.write(output)
    return parse_sheap_output(output.splitlines())


def parse_sheap_output(indata) -> SheapOut:
    """Parse the output data of SHEAP"""
    coords = []
    form = []
    labels = []
    nforms = []
    sym = []
    volume = []  # pylint: disable=invalid-name
    enthalpy = []  # pylint: disable=invalid-name
    nfound = []
    radius = []
    offset = 0
    errors = []
    for i, line in enumerate(indata):

        # Try to parse the first line, sometimes sheap emits errors into STDOUT - so we deal with it
        if offset == i:
            try:
                nitems = int(line.strip())
            except ValueError:
                offset += 1
                errors.append(line)
            else:
                if len(errors) > 0:
                    print('There are errors emitted in STDOUT')
            continue

        if i == offset + 1:
            tokens = line.strip().split()
            dim = int(tokens[1])
            cost = float(tokens[-1])
            continue

        # Reading the main body of the data
        tokens = line.strip().split()
        coords.append([float(tokens[d + 1]) for d in range(dim)])

        labels.append(tokens[1 + dim])
        nforms.append(int(tokens[2 + dim]))
        form.append(tokens[3 + dim])
        sym.append(tokens[4 + dim])
        volume.append(float(tokens[5 + dim]))
        enthalpy.append(float(tokens[6 + dim]))
        nfound.append(int(tokens[7 + dim]))
        radius.append(float(tokens[8 + dim]))

    return SheapOut(labels, nforms, form, sym, volume, enthalpy, nfound,
                    radius, coords, nitems, cost)


def get_sheap_metadata(dataframe: pd.DataFrame) -> List[SheapMetadata]:
    """
    Assemble a list of SheapMetadata objects based an dataframe
    """
    metadata = []
    for _, row in dataframe.iterrows():
        metadata.append(
            SheapMetadata(label=row.label,
                          natoms=row.natoms,
                          form=row.reduced_formula,
                          enthalpy=row.enthalpy,
                          sym=row.symm,
                          volume=row.volume))
    return metadata


def sheap_to_dict(sheapout: SheapOut, structure_path: Union[dict, str, Path]):
    """
    Convert the output of SHEAP to JSON dictionary format for Chemiscope
    """

    outdict = {
        'meta': {
            'name': 'SHEAP',
            'description': 'Map generated with SHEAP'
        },
    }
    outdict['properties'] = {}
    outdict['properties']['volume'] = {
        'target': 'structure',
        'values': sheapout.volume
    }
    outdict['properties']['count'] = {
        'target': 'structure',
        'values': sheapout.nfound
    }
    outdict['properties']['radius'] = {
        'target': 'structure',
        'values': sheapout.radius
    }
    # Compute the sizes
    sizes = np.array(sheapout.radius)**2 * np.pi
    outdict['properties']['size'] = {
        'target': 'structure',
        'values': sizes.tolist()
    }
    outdict['properties']['energy'] = {
        'target': 'structure',
        'values': sheapout.enthalpy
    }
    outdict['properties']['label'] = {
        'target': 'structure',
        'values': sheapout.labels
    }

    coords = sheapout.coords
    dims = len(sheapout.coords[0])
    for dim in range(dims):
        outdict['properties'][f'sheap{dim+1}'] = {
            'target': 'structure',
            'values': [entry[dim] for entry in coords]
        }

    structures = []
    spacegroups = []
    # Include structures
    for label in sheapout.labels:
        # Locate the file
        if isinstance(structure_path, dict):
            atoms = structures[label]
        else:
            # Load the atoms
            atoms = read(str(Path(structure_path) / f'{label}.res'))
        spacegroups.append(atoms.info.get('spacegroup'))
        structures.append(atoms_to_json(atoms))
    outdict['structures'] = structures

    # Spacegroups - detected
    if spacegroups:
        outdict['properties']['spacegroup'] = {
            'target': 'structure',
            'values': spacegroups
        }
    return outdict


def atoms_to_json(atoms: Atoms) -> dict:
    """
    Convert ase.Atoms to the JSON serialization format used by Chemiscope

    Returns a dictionary of the representation.
    """
    data = {}
    data['size'] = len(atoms)
    data['names'] = list(atoms.symbols)
    data['x'] = [float(value) for value in atoms.positions[:, 0]]
    data['y'] = [float(value) for value in atoms.positions[:, 1]]
    data['z'] = [float(value) for value in atoms.positions[:, 2]]

    if (atoms.cell.lengths() != [0.0, 0.0, 0.0]).all():
        data['cell'] = list(np.concatenate(atoms.cell))

    return data
