"""
Toolkit for working with AIRSS style SHELX files

Collection of function to work with AIRSS
"""
import re
from collections import namedtuple
from subprocess import check_output

import pandas as pd
import numpy as np

from ase import Atoms
from ase.geometry import cellpar_to_cell

from pymatgen.entries.computed_entries import ComputedStructureEntry
from pymatgen import Structure
from pymatgen.io.ase import AseAtomsAdaptor
from tqdm import tqdm

from disp.database.odm import ResFile

# TITL 2LFP-11212-7612-5 -0.0373 309.998985 -1.21516192E+004 16.0000 16.2594 28 (P-1) n - 1
#              0             1        2            3             4       5    6   7   8 9 10
TITLE_KEYS = [
    'label', 'pressure', 'volume', 'enthalpy', 'spin', 'spin_abs', 'natoms',
    'symm', 'flag1', 'flag2', 'flag3'
]
TitlInfo = namedtuple('TitlInfo', TITLE_KEYS)

RES_COORD_PATT = re.compile(
    r"""(\w+)\s+
                            ([0-9]+)\s+
                            ([0-9\-\.]+)\s+
                            ([0-9\-\.]+)\s+
                            ([0-9\-\.]+)\s+
                            ([0-9\-\.]+)""", re.VERBOSE)
RES_COORD_PATT_WITH_SPIN = re.compile(
    r"""(\w+)\s+
                            ([0-9]+)\s+
                            ([0-9\-\.]+)\s+
                            ([0-9\-\.]+)\s+
                            ([0-9\-\.]+)\s+
                            ([0-9\-\.]+)\s+
                            ([0-9\-\.]+)""", re.VERBOSE)


def parse_titl(line):
    """Parse titl and return a TitlInfo Object"""
    tokens = line.split()[1:]
    return TitlInfo(
        label=tokens[0],
        pressure=float(tokens[1]),
        volume=float(tokens[2]),
        enthalpy=float(tokens[3]),
        spin=float(tokens[4]),
        spin_abs=float(tokens[5]),
        natoms=int(tokens[6]),
        symm=tokens[7],
        flag1=tokens[8],
        flag2=tokens[9],
        flag3=tokens[10],
    )


def read_titl(lines):
    """
    Read the TITL entry only, skip the structure
    """
    for line in lines:
        if 'TITL' in line:
            return parse_titl(line)
    return None


def _read_res(lines):
    """
    Reads a res file from a string

    Args:
        lines (str): A list of lines containing Res data.

    Returns:
        dictionary of parsed lines
    """
    abc = []
    ang = []
    species = []
    coords = []

    line_no = 0
    title_items = []
    rem_lines = []
    spins = []
    while line_no < len(lines):
        line = lines[line_no]
        tokens = line.split()
        if not tokens:
            line_no += 1
            continue

        if tokens[0] == 'TITL':
            # Skip the TITLE line, the information is not used
            # in this package
            title_items = parse_titl(line)

        elif tokens[0] == 'CELL' and len(tokens) == 8:
            abc = [float(tok) for tok in tokens[2:5]]
            ang = [float(tok) for tok in tokens[5:8]]
        elif tokens[0] == 'SFAC':
            for atom_line in lines[line_no:]:
                if line.strip() == 'END':
                    break

                match = RES_COORD_PATT_WITH_SPIN.search(atom_line)
                if match:
                    has_spin = True
                else:
                    has_spin = False
                    match = RES_COORD_PATT.search(atom_line)
                if match:
                    species.append(match.group(1))  # 1-indexed
                    xyz = match.groups()[2:5]
                    coords.append([float(c) for c in xyz])
                    if has_spin:
                        spins.append(float(match.group(7)))
                line_no += 1  # Make sure the global is updated
        elif tokens[0] == 'REM':
            rem_lines.append(line[4:].strip())
        line_no += 1

    out = {
        'titl': title_items,
        'species': species,
        'scaled_positions': coords,
        'cellpar': list(abc) + list(ang),
        'rem_lines': rem_lines,
        'spins': spins,
    }

    return out


def _get_res_lines(titl,
                   species,
                   scaled_positions,
                   cellpar,
                   rem_lines=None,
                   spins=None):
    """
    Write a SHELX file using given data

    Args:
        titl: A list of title items
        species: A list of species for each site
        scaled_positions: Scaled (fractional) atomic potentials
        cellpara: Cell parameters in a, b, c, alpha, beta, gamma
        rem_lines: Lines for the REM information
        spins: A list of spins to be added to each site if given

    Returns:
        A list of lines for the SHELX file
    """
    # Write the title
    lines = []

    if len(titl) != 11:
        raise ValueError('TITL must be a list of length 11.')
    titl = '{} {:.3f} {:.3f} {:.4f} {:.2f} {:.2f} {} ({}) {} {} {}'.format(
        *titl)
    lines.append('TITL ' + titl)

    if rem_lines:
        for line in rem_lines:
            lines.append('REM ' + line)

    lines.append(
        'CELL 1.0 {:<12.6f} {:<12.6f} {:<12.6f} {:<12.6f} {:<12.6f} {:<12.6f}'.
        format(*cellpar))
    lines.append('LATT -1')
    unique_speices = unique(species)
    lines.append('SFAC ' + ' '.join(unique_speices))
    look_up = {s: i + 1 for i, s in enumerate(unique_speices)}
    for i, (symbol, pos) in enumerate(zip(species, scaled_positions)):
        line = '{:<4} {:<2} {:>20.13f} {:>20.13f} {:>20.13f} 1.0'.format(
            symbol, look_up[symbol], *pos)
        if spins:
            line = line + ' {:>8.3f}'.format(spins[i])
        lines.append(line)
    lines.append('END')
    return lines


def unique(items):
    """Get a list of ordered unique items"""
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def read_res_atoms(lines):
    """Read a res file, return as (TitlInfo, ase.Atoms)"""
    out = _read_res(lines)
    return out['titl'], Atoms(symbols=out['species'],
                              scaled_positions=out['scaled_positions'],
                              cell=cellpar_to_cell(out['cellpar']),
                              pbc=True)


def read_res_pmg(lines):
    """Read a res file, return as (TitlInfo, pymatgen.Structure)"""
    out = _read_res(lines)
    cell = cellpar_to_cell(out['cellpar'])
    structure = Structure(cell,
                          out['species'],
                          out['scaled_positions'],
                          coords_are_cartesian=False)
    return out['titl'], out['rem_lines'], structure, out['spins']


def read_stream(stream):
    """
    Read from a stream of RES file contents, and resturn a
    list of System object
    """
    lines = []
    atoms_list = []
    in_file = False
    titl_list = []
    for line in stream:
        line = line.strip()
        # Skip any empty lines
        if not line:
            continue
        if 'TITL' in line:
            if in_file is True:
                # read the current file
                titl, atoms = _read_res(lines)
                titl_list.append(titl)
                atoms_list.append(atoms)
                lines = []
            in_file = True
        if in_file:
            lines.append(line.strip())
    # Reached the end parse the last file
    titl, atoms = _read_res(lines)
    titl_list.append(titl)
    atoms_list.append(atoms)
    return titl_list, atoms_list


class RESFile:
    """
    Class represent a res file

    The SHELX file contains both the structure and the computed properties as
    well as some metadata.
    """
    def __init__(self, structure, data, lines=None, metadata=None):
        """
        Initialise an RESFile object base on pymatgen.Structure.

        The most cases it is best to initialise using class methods such as
        `from_file` or `from_lines`.

        Args:
            structure: `pymatgen.Structure` instance
            data: A dictionary contains the underlying data
            lines: A list of raw lines of the RESFile

        """
        self.structure = structure
        self.lines = lines

        if 'volume' not in data:
            data['volume'] = structure.volume if structure else None

        if 'natoms' not in data:
            data['natoms'] = len(structure)

        if 'symm' not in data:
            data['symm'] = structure.get_space_group_info(
            )[0] if structure else None
        self._data = data  # pylint: disable=protected-access
        self.metadata = metadata if metadata else {}

    @property
    def rem(self):
        return self._data.get('rem')

    @property
    def atoms(self):
        """Returns a ``ase.atoms`` object"""
        return AseAtomsAdaptor.get_atoms(self.structure)

    @property
    def data(self):
        """Underlying data of the object"""
        return self._data

    @property
    def label(self):
        """Label of the structure"""
        return self._data.get('label')

    @property
    def name(self):
        """Alias for label"""
        return self.label

    @property
    def enthalpy(self):
        """Enthalpy as reported"""
        return self._data.get('enthalpy')

    @property
    def volume(self):
        """Volume as reported"""
        return self._data.get('volume')

    @property
    def pressure(self):
        """External pressure as reported"""
        return self._data.get('pressure', 0.0)

    @property
    def natoms(self):
        """Number of atoms"""
        return self._data.get('natoms')

    @property
    def symm(self):
        """Symmetry as reported"""
        return self._data.get('symm')

    @property
    def spin(self):
        """Spin as reported"""
        return self._data.get('spin', 0.0)

    @property
    def spins(self):
        """Spin as reported"""
        return self._data.get('spins', [])

    @property
    def spin_abs(self):
        """Absolute integrated spin"""
        return self._data.get('spin_abs', 0.0)

    @property
    def composition(self):
        """Composition of the structure"""
        return self.structure.composition if self.structure else None

    @classmethod
    def from_string(cls, string):
        """
        Construct from a string.

        Args:
            string (str): Content of the SHELX file
        """
        return cls.from_lines(string.split('\n'))

    @classmethod
    def from_lines(cls, lines, include_structure=True, only_titl=False):
        """
        Construct from lines


        Args:
            lines (list of str): Content of the SHELX file
            no_structure (bool, optional): Wether to parse the structure of not. Default to False.
        """
        if include_structure:
            titls, rem_lines, structure, spins = read_res_pmg(lines)
            data = {
                'rem': rem_lines,
                'spins': spins,
                **titls._asdict(),
            }

        elif only_titl:
            titls = read_titl(lines)
            structure = None
            data = titls._asdict()
        else:
            output = _read_res(lines)
            data = {
                'rem_line': output['rem_lines'],
                'spins': output['spins'],
                **output['titl']._asdict(),
            }
            structure = None

        obj = cls(structure, data, lines=lines)
        return obj

    def load_structure(self):
        """Load structure from the lines"""
        new_obj = self.from_lines(self.lines, include_structure=True)
        self.structure = new_obj.structure
        self._data = new_obj.data

    @classmethod
    def from_file(cls, fname, include_structure=True, only_titl=False):
        """Construct from a file"""
        with open(fname) as fhandle:
            return cls.from_lines(fhandle.readlines(),
                                  include_structure=include_structure,
                                  only_titl=only_titl)

    def __repr__(self):
        string = '<RESFile with label={}, formula={}, enthalpy={}...>'
        return string.format(self.label, self.formula, self.enthalpy)

    @property
    def formula(self):
        """Formula of the structure"""
        return self.composition.formula.replace(' ', '')

    @property
    def reduced_formula(self):
        """Reduced formula of the structure"""
        return self.composition.reduced_formula

    @property
    def n_formula_units(self):
        """Number of formula units"""
        return self.composition.get_reduced_formula_and_factor()[1]

    def to_computed_entry(self):
        """Obtained the ComputedEntry"""
        return ComputedStructureEntry(self.structure,
                                      self.enthalpy,
                                      data=self.data)

    def to_res_lines(self):
        """Get the raw RES representation of this object"""

        species = [site.symbol for site in self.structure.species]
        frac_pos = [row.tolist() for row in self.structure.frac_coords]
        cellpar = self.structure.lattice.parameters

        titl = [
            self.label, self.pressure, self.volume, self.enthalpy, self.spin,
            self.spin_abs, self.natoms, self.symm, 'n', '-', '1'
        ]

        lines = _get_res_lines(titl, species, frac_pos, cellpar, self.rem,
                               self.spins)
        # Make sure we add an newline in the end
        lines.append('')
        return lines

    def get_minsep(self, string=False):
        """Return specie-wise minimum separations"""
        minsep = get_minsep(self.structure.species,
                            self.structure.distance_matrix)
        if string:
            return format_minsep(minsep)
        return minsep


def read_ca(lines):
    """
    Read results from `ca` into a DataFrame

    Args:
        lines (list): String lines as returned by `ca` command.

    Returns:
        pandas.DataFrame: A DataFrame contains the parsed data.
    """
    records = []
    ntokens = len(lines[0].split())
    for line in lines:
        if not line:
            continue
        tokens = line.split()
        # If has spin
        if ntokens == 10:
            records.append(
                dict(label=tokens[0],
                     press=float(tokens[1]),
                     volume=float(tokens[2]),
                     H=float(tokens[3]),
                     spin=float(tokens[4]),
                     aspin=float(tokens[5]),
                     nform=int(tokens[6]),
                     formula=tokens[7],
                     symm=tokens[8],
                     nseen=int(tokens[9])))
        else:
            records.append(
                dict(label=tokens[0],
                     press=float(tokens[1]),
                     volume=float(tokens[2]),
                     H=float(tokens[3]),
                     nform=int(tokens[4]),
                     formula=tokens[5],
                     symm=tokens[6],
                     nseen=int(tokens[7])))

    dataframe = pd.DataFrame.from_records(records)

    # Fix the H field
    dataframe.iloc[1:, 3] += dataframe.iloc[0, 3]
    return dataframe


def collect_results_in_df(norm_mode='per_atom',
                          include_doc=False,
                          qset=None,
                          **cond) -> pd.DataFrame:
    """
    Collect the results based on the selections conditions and return a dataframe

    Args:
        norm_mode (str): Mode of normalisation for energy and volume
        **cond: Selection condictions for selecting the files from the database

    Returns:
        A ``pandas.DataFrame`` object contains the information for convenient further processing.
            the original ``RESFile`` objects are stored in the ``res`` column.
    """
    records = []
    if qset is None:
        qset = ResFile.objects(**cond)  # pylint: disable=no-member
    nentries = qset.count()
    for doc in tqdm(qset, total=nentries):
        res = RESFile.from_string(doc.content)
        res.metadata = {
            'project_name': doc.project_name,
            'seed_name': doc.seed_name,
            'struct_name': doc.struct_name,
        }
        if include_doc:
            res.metadata['doc'] = doc

        dtmp = dict(res.data)
        dtmp.update(res.metadata)
        dtmp['res'] = res
        dtmp['chemsys'] = res.composition.chemical_system
        # Added addititional infromation
        dtmp.update({
            'nform': res.n_formula_units,
            'reduced_formula': res.reduced_formula
        })
        records.append(dtmp)

    dframe = pd.DataFrame(records)

    # Normalise the energy and volumes
    if norm_mode == 'per_atom':
        dframe['H'] = dframe['enthalpy'] / dframe['natoms']
        dframe['V'] = dframe['volume'] / dframe['natoms']
    else:
        dframe['H'] = dframe['enthalpy'] / dframe['nform']
        dframe['V'] = dframe['volume'] / dframe['nform']
    dframe.sort_values('H', inplace=True)

    return dframe


def collect_res_in_df(res_collection, norm_mode='per_atom'):
    """
    Collect a list of res files into a `DataFrame"

    Args:
        res_collection (list):  A collection of the RESFile objects
        norm_mode (str): Normalisation model of the energy. The default is `per_atom`.

    Returns:
        A `pandas.DataFrame` object contains the data collected from the collection
        of RESFile objects.
    """

    records = []
    for res in res_collection:
        entry = {}
        entry.update(res.data)
        entry['formula'] = res.formula
        entry['reduced_formula'] = res.reduced_formula
        entry['nform'] = res.n_formula_units
        entry['res'] = res
        entry['chemsys'] = res.composition.chemical_system
        records.append(entry)

    dframe = pd.DataFrame(records)
    # Normalise the energy and volumes
    if norm_mode == 'per_atom':
        dframe['H'] = dframe['enthalpy'] / dframe['natoms']
        dframe['V'] = dframe['volume'] / dframe['natoms']
    else:
        dframe['H'] = dframe['enthalpy'] / dframe['nform']
        dframe['V'] = dframe['volume'] / dframe['nform']
    dframe.sort_values('H', inplace=True)

    return dframe


def combine_res_cryan(dframe, thres=0.1, ntop=30):
    """
    Reduce simular structure using `cryan -u `

    Args:
        df (DataFrame): DataFrame with `res` column
        thres (float): Threshold for combining structures
        ntop (int): The number of top structures to be returned

    Returns:
        A dataframe of output from the `cryan` command.
    """
    lines = []
    for _, row in dframe.iterrows():
        lines.extend(row.res.lines)
    if lines[0].endswith('\n'):
        join_base = ''
    else:
        join_base = '\n'
    inpd = join_base.join(lines)
    cryan_out = check_output(  # pylint: disable=unexpected-keyword-arg
        ['cryan', '-u', str(thres), '-r', '-t',
         str(ntop), '-l'],
        text=True,
        input=inpd).split('\n')
    cadf = read_ca(cryan_out)

    return cadf


def get_minsep(species, distance_matrix):
    """
    Obtain the minimum separations given a list of
    species and distance_matrix

    Args:
        species (list, np.ndarray): A list of the species
        distance_matrix (np.ndarray): The distance matrix

    Returns:
        a dictionary of {set(s1, s2): minsep}
    """

    species = np.asarray(species)

    nspec = distance_matrix.shape[0]
    all_minseps = {}

    for i in range(nspec):
        for j in range(i + 1, nspec):
            dist = distance_matrix[i, j]
            spair = sorted([str(species[i]), str(species[j])])
            pair = f'{spair[0]}-{spair[1]}'
            if pair in all_minseps:
                if all_minseps[pair] > dist:
                    all_minseps[pair] = dist
            else:
                all_minseps[pair] = dist
    return all_minseps


def get_minsep_range(minseps, cap=None):
    """
    Create ranged minseps from an ensemble of minsep entries

    Args:
        minseps (list): A list of minsep dictionaries
        cap (tuple): Minimum-maximum caps

    Returns:
        minsep (dict): A minsep where values are minimum and maximum values
    """

    base = {key: [value, value] for key, value in minseps[0].items()}
    for minsep in minseps:
        for key, value in minsep.items():
            # If the key exists (it should)
            if key in base:
                existing = base[key]
                # Expand the minimum and maximum values
                if cap and (value < cap[0]):
                    existing[0] = cap[0]
                elif cap and (value > cap[1]):
                    existing[1] = cap[1]
                elif existing[0] > value:
                    existing[0] = value
                elif existing[1] < value:
                    existing[1] = value
            # add the pairs if needed
            else:
                base[key] = [value, value]
    return base


def format_minsep(minsep):
    """
    Returns string representation of the minsep
    """

    string = ''
    for key, value in minsep.items():
        if isinstance(value, (list, tuple)):
            string += f'{key}={value[0]:.2f}-{value[1]:.2f} '
        else:
            string += f'{key}={value:.2f} '
    return string
