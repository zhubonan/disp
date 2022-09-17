"""
This file contatins castep related untility functions
"""

import io
import os
import platform
import re
import shutil
import time
import uuid

import ase.io
import numpy as np
import spglib

from .utils import filter_out_stream, trim_stream

# pylint: disable=too-many-function-args, invalid-name


class CastepRunError(RuntimeError):
    """Error when castep produced no result"""


def parse_param(seed):
    """Parse the paramfile, return a dictionary
    Keys are converted to lower case.
    Values should be left along
    seed : name of the seed
    """
    dict_out = {}
    # Compile seperator
    spliter = re.compile(r"[ :=]+")
    with open(seed + ".param") as seedfile:
        for line in seedfile:
            if "#" in line:
                continue
            # Forcing lower case
            pair = line.strip()
            # Split and filter out empty strings
            pair = list(filter(None, spliter.split(pair, 1)))
            if pair:
                dict_out.update({pair[0].lower(): pair[1]})
    return dict_out


pattern_geom = r"""
^\ *
(?P<name>[A-Z]+):          # Optimisation name
\ +finished\ iteration
\ +(?P<number>[0-9]+)             # iteration number
\ +with\ enthalpy=
\ +(?P<H>[+-.E0-9]+)        # Enthalpy
\ +(?P<unit>[a-zA-Z]+)          # Enthalpy unit
\ *$
"""

pattern_time = r"""
^\ +
[0-9]+                      # Loop number
\ +
[+-.E0-9]+                   # Energy
\ +
[+-.E0-9]+                   # Fermi Energy
\ +
[+-.E0-9]+                   # Energy gain per atom
\ +
([.0-9]+)                      # Timer
\ +
<--\ SCF
$
"""


def parse_dot_castep(fb, aggregate=False):  # pylint: disable=too-many-locals
    """Parse information from an castep file based on a file handle
    Extract information of geometry convergence
    Return a dictionary with keys:
        H: enthalpy
        iter_num: raw numer of iteration
        name: Name of the method
        unit: unit for enthalpy
    """
    iter_start = re.compile(r" Starting \w+ iteration")
    sfc_line = re.compile(pattern_time, re.VERBOSE)
    match_geom = re.compile(pattern_geom, re.VERBOSE)

    # Storage space for capture properties
    eng = []  # Enthalpy list
    iter_num = []  # Raw iteration array
    iter_times = []  # Raw timing of finished iteration
    save_times = []  # Raw timing of saves
    save_iter = []  # Iteration in which writing checkpoint took place
    geom_name, unit = None, None

    # In loop variables
    last_time = 0
    current_iter = 0

    # Iterate through the file
    for line in fb:
        # Capture the start of iteration
        if iter_start.match(line):
            current_iter += 1
            continue

        # Capture timing of save and iteration numbers(current)
        if "Writing model" in line:
            save_times.append(last_time)
            save_iter.append(current_iter)

        # Capture timing of SFC
        scf_match = sfc_line.match(line)
        if scf_match:
            last_time = float(scf_match.group(1))
            continue

        # Capture the end of gemo iteration
        geom_match = match_geom.match(line)
        if geom_match:
            eng.append(float(geom_match.group("H")))
            iter_num.append(int(geom_match.group("number")))
            iter_times.append(float(last_time))
            geom_name = geom_match.group("name")
            unit = geom_match.group("unit")
            continue

    out = dict(H=eng, iter_num=iter_num, name=geom_name, unit=unit, time=iter_times, save_iter=save_iter, save_times=save_times)
    if aggregate:
        # Need to aggregate the timer
        timer_array = np.array(iter_times)
        last_record = 0
        for i, time_record in enumerate(iter_times):
            if time_record < last_record:
                timer_array[i:] = timer_array[i:] + last_record
            last_record = time_record
        out.update(time=timer_array)
    return out


# For performing RASH
def RASH_prepare_seed(seed, relaxed, amp):
    """
    Prepare the seed for performing seed for RASH relation

    seed -- the ORIGINAL seed of the search
    relaxed -- the name(uid) of the relaxed structure
    output -- name of the output
    amp -- amplitude of shape (positive float)

    Return: An StringIO object of the cell for RASH
    """
    rlx_cell = open(relaxed + ".cell")
    seed_cell = open(seed + ".cell")
    # Capture the new lattice from the out cell
    rlx_lattice = trim_stream(rlx_cell, r"^%BLOCK [Ll][Aa][Tt]", r"^%ENDBLOCK [Ll][Aa][Tt]", "FIX_VOL", "ANG").read()
    rlx_lattice = rlx_lattice.replace("%ENDBLOCK", "#FIX\nENDBLOCK")
    # Get the position block
    rlx_pos = trim_stream(rlx_cell, r"^%BLOCK [Pp][Oo][Ss]", r"^%ENDBLOCK [Pp][Oo][Ss]").read()
    # Preserve what is in between two blocks
    seed_rest = filter_out_stream(seed_cell, r"^%BLOCK [Ll][Aa][Tt]", r"^%ENDBLOCK [Ll][Aa][Tt]")
    # Take out the pos block and get rid of unwanted AIRSS parameters
    seed_rest = filter_out_stream(
        seed_rest, r"^%BLOCK [Pp][Oo][Ss]", r"^%ENDBLOCK [Pp][Oo][Ss]", "#POSAMP=", "#SYMMOPS=", "#NFORM=", "#SUPER"
    ).read()
    out_string = io.StringIO()
    out_string.write(rlx_lattice + "\n")
    out_string.write(rlx_pos + "\n")
    out_string.write(seed_rest + "\n" + "#POSAMP=" + str(amp))
    out_string.seek(0)
    return out_string


class CastepSkip(RuntimeError):
    pass


class CastepManualTimedout(RuntimeError):
    pass


def extract_REM(seed):
    """
    Construct the REM lines
    Input: seed
    Return: a dictionary of the REM information
    """
    rem = {}
    his = open(seed + ".history")
    get_pspot = False
    pspot = []
    for line in his:
        if " Welcome to " in line:
            rem.update(version=line.strip(" |\n").split()[-1])
        if " from code version " in line:
            rem.update(fromcode=line.strip(" |\n"))
        if " Run started: " in line:
            rem.update(rundate=line.strip(" |\n"))
        if " using functional " in line:
            xc = line.split(":")[1].strip()
            rem.update(functional="Functional  " + xc)
        if " relativistic treatment " in line:
            rem.update(relativity=" Relativity " + line.split(":")[-1].strip())
        if " DFT+D: Semi-empirical dispersion correction " in line:
            pass
        if " plane wave basis set cut-off " in line:
            rem.update(cutoff="Cut-off " + line.split(":")[-1].strip())
        if " size of standard grid " in line:
            rem.update(gridscale=" Grid scale " + line.split(":")[-1].strip())
        if " size of   fine   gmax " in line:
            rem.update(gmax=" Gmax " + line.split(":")[-1].strip())
        if " finite basis set correction  " in line:
            rem.update(fbsc=" FBSC" + line.split(":")[-1].strip())
        if " MP grid size for SCF calculation is " in line:
            rem.update(mpgrid="MP grid " + " ".join(line.strip().split()[-3:]))
        if " with an offset of  " in line:
            rem.update(offset=" Offset " + " ".join(line.strip().split()[-3:]))
        if " Number of kpoints used = " in line:
            rem.update(nkpts=" No. kpts " + line.split("=")[-1].strip())
        if not pspot and " Files used for pseudopotential" in line:
            get_pspot = True
        if get_pspot and "-------------------------------" in line:
            get_pspot = False
        if get_pspot:
            pspot.append("REM " + line.strip() + "\n")
    his.close()
    # Join pspot into a single string for storing as StrDict
    # Remove any : or ; in case of comfilict
    pspot_str = "".join(pspot).replace(":", " ")
    rem.update(pspot=pspot_str)
    # Cell file data
    cell = open(seed + ".cell")
    for line in cell:
        if "KPOINTS_MP_SPACING" in line:
            # More robust splitting in cell file -
            # people use different styles
            rem.update(spacing=" Spacing " + re.split(r"[:=\s]+", line.strip())[-1])
            break
    if "spacing" not in rem:
        rem.update(spacing="Spacing Unspecified")

    cell.close()
    # Other information
    rem.update(projectdir=os.getcwd())
    rem.update(host=platform.node())
    return rem


def extract_result(seed):
    """
    Extract and save the results as atrribute from castep or history file
    Return a dictionary object with P,V,H and sym as keywords
    """
    results = {}
    with open(seed + ".history") as res_file:
        for line in res_file:
            if "Pressure:" in line:
                results["pl"] = line
            if "Final free" in line or "Final Enthalpy" in line:
                results["hl"] = line
            if "Current cell volume =" in line:
                results["cl"] = line

    # Split the line and strip extra marks
    pl = results.get("pl")
    if pl is not None:
        P_str = pl.split(":")[1].strip("|*\n ")
    else:
        # logger.warning('Pressure is not found in {}.history'.format(seed))
        P_str = "0"

    # To match energy and volume, first split with = then split again and
    # take the 1st element which has to be the numerical value
    if "hl" not in results or "cl" not in results:
        # logger.error('Energy or cell volume has not being calculated'
        #             ' in {}.history'.format(seed))
        raise RuntimeError(f"Energy or cell volume not found in {seed}.history")
    H_str = results["hl"].split("=")[1].split()[0].strip()
    V_str = results["cl"].split("=")[1].split()[0].strip()

    P = float(P_str)
    H = float(H_str)
    V = float(V_str)
    # Store the results
    # Get symmetry - the direct way, use a large tol same as symm script
    # Might need to
    atoms = ase.io.read(seed + ".cell")
    sg = spglib.get_spacegroup(atoms, 0.1)
    sg = sg.split()[0]  # split number from name
    sg = "(" + sg + ")"  # (SG) is the format for cryan       self.V = V
    nat = atoms.get_number_of_atoms()
    chem_formula = atoms.get_chemical_formula()
    return {"P": P, "H": H, "V": V, "sym": sg, "nat": nat, "chem_formula": chem_formula}


def write_converge(seed, suffix="castep"):
    """
    Write convergence information to a .conv file
    """
    with open(seed + "." + suffix) as fb:
        conv_info = parse_dot_castep(fb, aggregate=True)
    out_file = open(seed + ".gconv", "w")
    out_file.write("# Geometry Optimisation convergence")
    out_file.write("# Written by Bonan Zhu bz240@cam.ac.uk")
    out_file.write("# Method:  " + conv_info["name"] + "\n")
    out_file.write("# Energy Unit:  " + conv_info["unit"] + "\n")
    num = range(len(conv_info["H"]))
    for i, value, iter_num, timer in zip(num, conv_info["H"], conv_info["iter_num"], conv_info["time"]):
        out_file.write(f"{i:<5d}{value:<20.5f}{iter_num:<10d}{timer:.2f}\n")
    out_file.close()


def get_rand_cell_name(seed_name):
    """Return a string for naming the randomly generated cell"""
    timestamp = time.strftime("%y%m%d-%H%M%S")
    return seed_name + "-" + timestamp + "-" + str(uuid.uuid4())[:6] + ".cell"


def castep_finish_ok(dot_castep):
    """Check for the hint of CASTEP finshed OK"""
    if not os.path.isfile(dot_castep):
        return False

    with open(dot_castep) as fhandle:
        lines = fhandle.readlines()

    last_few = lines[-20:]
    ok = False
    for line in last_few:
        if "Total time" in line:
            ok = True
            break
    return ok


def castep_geom_count(dot_castep):
    """Count the number of geom cycles"""
    count = 0
    with open(dot_castep) as fhandle:
        for line in fhandle:
            if "starting iteration" in line:
                count += 1
    return count


def push_cell(cellout, cell):
    """
    Move the structure from 'cellout' to 'cell' by copying the relavant blocks
    """
    with open(cellout) as fhout, open(cell) as fcell, open(str(cell) + ".tmp", "w") as ftmp:

        # get the new lattice from the out cell
        new_lattice = trim_stream(fhout, r"^%BLOCK [Ll][Aa][Tt]", r"^%ENDBLOCK [Ll][Aa][Tt]", ["FIX_VOL", "ANG"])
        new_pos = trim_stream(fhout, r"^%BLOCK [Pp][Oo][Ss]", r"^%ENDBLOCK [Pp][Oo][Ss]")
        ftmp.write(new_lattice.read())
        ftmp.write("\n")
        ftmp.write(new_pos.read())
        # Do it twice to preserve what is in between two blocks
        old_rest = filter_out_stream(fcell, r"^%BLOCK [Ll][Aa][Tt]", r"^%ENDBLOCK [Ll][Aa][Tt]")
        old_rest = filter_out_stream(old_rest, r"^%BLOCK [Pp][Oo][Ss]", r"^%ENDBLOCK [Pp][Oo][Ss]")
        ftmp.write(old_rest.read())

    # return the success_count - this will be implemented later for symmetrize
    # on the fly
    # Move the temp cell to replace the original cell
    shutil.move(str(cell) + ".tmp", cell)
    os.remove(cellout)


def gulp_relax_finish_ok(dot_castep):
    """Check the relaxation of gulp_relax"""
    if not os.path.isfile(dot_castep):
        return False

    with open(dot_castep) as fh:
        content = fh.read()

    mathch = re.search(r"Final Enthalpy += ([-e0-9\.]+)", content)
    if mathch:
        return True
    return False
