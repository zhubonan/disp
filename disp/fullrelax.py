"""
Module for conducting fullrelax with castep
This replicate the castep_relax.pl based on previous implemented
fullrelax function in casteptool module
"""
import fileinput
import io
import json
import logging
import os
import re
import shutil
import subprocess

import slurmtools as stl

from .casteptools import push_cell
from .utils import filter_out_stream, trim_stream

try:
    from .common import RelaxError
except ImportError:

    class RelaxError(RuntimeError):
        pass


logger = logging.getLogger(__name__)
logger = stl.SlurmAdapter(logger, None)
logger.setLevel(logging.DEBUG)


class FullRelax:
    """
    Class for conducting self-consistent relaxation in CASTEP
    This is for treating variable cell relaxation in high throughput
    computing.
    We relax with fixed_npw and without finite_basis_corr for a small
    numer of cycle and keeps restart from final structure until too
    sucessive sucessful runs.
    """

    def __init__(self, exe, struct_name, maxit, initial_cycle=4, initial_length=4, alter_cell_cons=False):
        """
        Initialise a FullRelax instance

        Parameters
        ==========
        :param exe: executable name
        :param struct_name: name of the structure to relaxed
        :param maxit: maximum iteration
        :initial_cycle: number of initial short cycles
        :initial_length:number of iterations in the initial runs
        :alter_cell_cons: alternate cell constraints on and off
        """

        self.exe = exe
        self.struct_name = struct_name
        self.maxit = maxit
        self.initial_length = initial_length
        if maxit == 0:
            self._init_relax = 0
            self.success = 2  # Only one sucessful relaxation is needed
        else:
            self._init_relax = initial_cycle
            self.success = 3  # Two sucessful relaxation is required

        self.alter_cell_cons = alter_cell_cons

    @property
    def dot_castep(self):
        return self.struct_name + ".castep"

    @property
    def dot_param(self):
        return self.struct_name + ".param"

    @property
    def dot_cell(self):
        return self.struct_name + ".cell"

    @property
    def dot_cell_out(self):
        return self.struct_name + "-out.cell"

    def _run_castep(self, timeout=None):
        """
        This methods runs the CASTEP
        """
        args = " ".join([self.exe, self.struct_name])
        logger.debug(f"Calling subprocess '{args}'")
        subprocess.call(args, shell=True, timeout=timeout)
        logger.debug(f"Checking {self.dot_castep} for results")
        with open(self.dot_castep) as fh:
            line_container = []
            for line in fh:
                line_container.append(line)
                if len(line_container) > 20:
                    line_container.pop(0)

            # Use the 'Total time' as a sign of sucessful castep run
            if "Total time" not in "".join(line_container):
                raise RelaxError("CASTEP finished with error. " "struct_name: {}".format(self.struct_name))

    def _set_short_geom_iter(self):
        """Set the geom iteration for initial rough relaxation"""
        with fileinput.input(self.dot_param, inplace=True) as f:
            for line in f:
                if "geom_max_iter" in line.lower():
                    print("#" + line, end="")
                else:
                    print(line, end="")

        with open(self.dot_param, "a") as f:
            f.write(f"\ngeom_max_iter: {self.initial_length}#MARKED\n")

    def _recover_geom_iter(self):
        """Recover the geom_iteration supplied in the PARAM file"""
        with fileinput.input(self.dot_param, inplace=True) as f:
            for line in f:
                if line.startswith("#") and "geom_max_iter" in line.lower():
                    print(line[1:], end="")

                elif "#MARKED" in line:
                    continue
                else:
                    print(line, end="")

    def check_param(self):
        """Check the integrity of param file"""
        cell_out = False
        with open(self.dot_param, "r+") as f:
            for line in f:
                if "write_cell_structure" in line.lower():
                    cell_out = True
            if cell_out is False:
                f.write("write_cell_structure :  True")

        # Delete any provious markers
        # In case the relaxation stopped at the initial stage
        with fileinput.input(self.dot_param, inplace=True) as f:
            for line in f:
                if "#MARKED" in line:
                    pass
                elif line.startswith("#") and "geom_max_iter" in line.lower():
                    print(line[1:], end="")
                else:
                    print(line, end="")

    def to_dict(self):
        """Internal state as dictionary"""
        s_dict = {"_init_relax": self._init_relax, "success": self.success}

    def save_state(self):
        """Save the state"""
        s_dict = {"_init_relax": self._init_relax, "success": self.success}
        sfile = "." + self.struct_name + "-fr.json"
        logger.debug(f"Save state in file: {sfile}")
        with open(sfile, "w") as fh:
            json.dump(s_dict, fh)

    def load_state(self):
        """Load state from unfinished run"""

        # If the json file exists it means the run has not finished
        if os.path.isfile("." + self.struct_name + "-fr.json"):

            logger.debug(f"Reocvering from .{self.struct_name}-fr.json")
            with open("." + self.struct_name + "-fr.json") as fh:
                s_dict = json.load(fh)

            for key, value in s_dict.items():
                self.__setattr__(key, value)

        # Use the last geom file if exists
        self._cell_from_geom()

    def fixed_cell_off(self):
        """
        Turn on cell_constraint by removing any commented sections,
        remove fix_all_cell if there is any
        """

        with open(self.struct_name + ".cell") as f:
            lines = f.readlines()

        in_block = False
        new_lines = []
        for line in lines:

            # Delete the FIX_ALL_CELL KEY
            if "FIX_ALL_CELL" in line.upper():
                continue

            # Check if we are in block and uncomment
            if "%BLOCK CELL_CONSTRAINTS" in line.upper():
                in_block = True
            elif "%ENDBLOCK CELL_CONSTRAINTS" in line.upper():
                in_block = False
                if line[0] == "#":
                    new_lines.append(line[1:])
                else:
                    new_lines.append(line)
                continue

            # Remove comment symmbol
            if in_block:
                if line[0] == "#":
                    new_lines.append(line[1:])
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # Write out the line
        with open(self.struct_name + ".cell", "w") as f:
            f.write("".join(new_lines))

    def fixed_cell_on(self):
        """Turn off cell_constraint
        comment off all the cell_constraints block and
        add fix_all_cell keyword"""

        with open(self.struct_name + ".cell") as f:
            lines = f.readlines()

        in_block = False
        new_lines = []
        for line in lines:
            if "%BLOCK CELL_CONSTRAINTS" in line.upper():
                in_block = True
            elif "%ENDBLOCK CELL_CONSTRAINTS" in line.upper():
                in_block = False
                new_lines.append("#" + line)
                continue

            if in_block:
                new_lines.append("#" + line)
            else:
                new_lines.append(line)

        new_lines.append("\nFIX_ALL_CELL: TRUE\n")

        # Write out the line
        with open(self.struct_name + ".cell", "w") as f:
            f.write("".join(new_lines))

    def _cell_from_geom(self):
        """
        Push the cell and position from the last geom file to the cell file
        """
        # Check if there a geom file that we can re-start from
        struct_name = self.struct_name
        gfile = struct_name + ".geom"
        # If there is no geom file then just return
        if not os.path.isfile(gfile):
            logger.debug(f"No geom file found for {struct_name}")
            return

        logger.debug(f"Using structure from {struct_name}.geom")
        cin = open(struct_name + ".cell")
        old_rest = filter_out_stream(cin, r"^%BLOCK lat", r"^%ENDBLOCK lat")
        old_rest = filter_out_stream(old_rest, r"^%BLOCK pos", r"^%ENDBLOCK pos")
        cin.close()
        with open(struct_name + ".cell.tmp", "w") as f:
            cblock, pblock = geom_to_cell(gfile)
            f.write(cblock)  # Write the cell block
            f.write(pblock)  # Write the positions block
            f.write(old_rest.read())

        # Overwrite the original cell file
        shutil.move(struct_name + ".cell.tmp", struct_name + ".cell")

    def run(self, timeout=None):
        """
        Run the main logic

        :returns success: If success = 1 the process is finished,
        if success = -1 the maximum cycles has been exceeded
        """
        import time

        self.load_state()
        self.check_param()

        start = time.time()

        def new_time_out():
            return timeout - (time.time() - start)

        # Do the initial relaxation if necessary
        count = 1
        while self._init_relax > 0:
            logger.debug(f"Starting initial iteration {count}")
            self._set_short_geom_iter()
            self._run_castep(new_time_out())
            self._recover_geom_iter()

            push_cell(self.dot_cell_out, self.dot_cell)
            self._init_relax -= 1
            self.save_state()
            logger.debug(f"Finished initial iteration {count}")
            count += 1

        # Do the main logic
        count = 1
        while self.success > 1:
            logger.debug(f"Starting iteration {count}")

            if self.alter_cell_cons:
                if count % 2 == 1:
                    logger.debug("Remove fixed cell in {}".format(self.struct_name + ".cell"))
                    self.fixed_cell_off()
                else:
                    logger.debug("Turn partial cell constraints back on in {}".format(self.struct_name + ".cell"))
                    self.fixed_cell_on()

            self._run_castep(new_time_out())  # This calls the castep executable
            # This propagtes the <struct_name>-out.cell to <struct_name>.cell
            push_cell(self.dot_cell_out, self.dot_cell)

            # Set the state counter with relaxation results
            r_flag, i_count = check_relax_status(self.dot_castep)
            if r_flag is True:
                if self.success > 1:
                    self.success -= 1
            # Check if limit has been reached
            elif i_count > self.maxit:
                self.success = -1
            else:
                # Make the counter to be 3#
                # so another TWO sucessful ones are required
                self.success = 3

            logger.debug(f"Finished iteration {count}")
            logger.debug(f"success: {self.success}")
            self.save_state()
            count += 1

        os.remove("." + self.struct_name + "-fr.json")
        if self.success == 1:
            return "success"
        if self.success == -1:
            return "limit reached"

    def __repr__(self):
        return f"<FullRelax('exe'={self.exe}, 'struct_name'={self.struct_name})>"


def check_relax_status(dot_castep):
    """
    Check the dot_castep file
    Return (relax flag, total iterations)
    relax flag is True is the last relaxation is successful
    """
    geom_line = re.compile(r"Geometry optimization (\w+)")
    count = 0

    with open(dot_castep) as fh:
        for line in fh:
            m = geom_line.search(line)
            if m:
                g_res = m.group(1)
            if ": finished iteration" in line:
                count += 1

    if g_res == "completed":
        return (True, count)
    else:
        return (False, count)


########## For reading geom file ##############
units_CODATA2002 = {
    "hbar": 6.58211915e-16,  # eVs
    "Eh": 27.2113845,  # eV
    "kB": 8.617343e-5,  # eV/K
    "a0": 0.5291772108,  # A
    "c": 299792458,  # m/s
    "e": 1.60217653e-19,  # C
    "me": 5.4857990945e-4,
}  # u

# (common) derived entries
for d in (units_CODATA2002,):
    d["t0"] = d["hbar"] / d["Eh"]  # s
    d["Pascal"] = d["e"] * 1e30  # Pa
units = units_CODATA2002


def parse_geom_text_output(out_lines, input_dict=None):
    """
    Parse output of .geom file

    :param out_lines: a list of lines from the readline function
    :param input_dict: not in use at the moment

    :return parsed_data: key, value of the trajectories of cell, atoms,
    force etc
    """
    import numpy as np

    txt = out_lines
    Hartree = units["Eh"]
    Bohr = units["a0"]

    # Yeah, we know that...
    cell_list = []
    species_list = []
    geom_list = []
    forces_list = []
    energy_list = []
    temperature_list = []
    velocity_list = []

    current_pos = []
    current_species = []
    current_forces = []
    current_velocity = []
    current_cell = []
    in_header = False
    for i, line in enumerate(txt):
        if "begin header" in line.lower():
            in_header = True
            continue
        if "end header" in line.lower():
            in_header = False
            continue
        if in_header:
            continue  # Skip header lines

        sline = line.split()
        if "<-- E" in line:
            energy_list.append(float(sline[0]) * Hartree)
            continue
        elif "<-- h" in line:
            current_cell.append(list(map(float, sline[:3])))
            continue
        elif "<-- R" in line:
            current_pos.append(list(map(float, sline[2:5])))
            current_species.append(sline[0])
        elif "<-- F" in line:
            current_forces.append(list(map(float, sline[2:5])))
        elif "<-- V" in line:
            current_velocity.append(list(map(float, sline[2:5])))
        elif "<-- T" in line:
            temperature_list.append(float(sline[0]))
        elif not line.strip() and current_cell:
            cell_list.append(current_cell)
            species_list.append(current_species)
            geom_list.append(current_pos)
            forces_list.append(current_forces)
            current_cell = []
            current_species = []
            current_pos = []
            current_forces = []
            if current_velocity:
                velocity_list.append(current_velocity)
                current_velocity = []

    if len(species_list) == 0:
        raise RuntimeError("No data found in geom file")

    out = dict(
        cells=np.array(cell_list) * Bohr,
        positions=np.array(geom_list) * Bohr,
        forces=np.array(forces_list) * Hartree / Bohr,
        geom_energy=np.array(energy_list),
        symbols=species_list[0],
    )
    if velocity_list:
        out["velocities"] = np.array(velocity_list) * Bohr
    return out


def geom_to_cell(geom_file):
    """Convert last configuration of geom file to cell blocks
    :param geom_file: path to the goem file
    :output cell_block, pos_block: string of the new lattice_cart
     and positions_abs including the block enclosures"""

    with open(geom_file) as fh:
        glines = fh.read().split("\n")

    # glines is a list of lines
    g_info = parse_geom_text_output(glines)

    last_cell = g_info["cells"][-1]
    last_pos = g_info["positions"][-1]

    # Construct the position block
    pos_block = ["%BLOCK POSITIONS_ABS"]
    for specie, pos in zip(g_info["symbols"], last_pos):
        pos_block.append("{} {:.7f} {:.7f} {:.7f}".format(specie, *pos))
    pos_block.append("%ENDBLOCK POSITIONS_ABS\n")

    # Construct the cell block
    cell_block = ["%BLOCK LATTICE_CART"]
    for v in last_cell:
        cell_block.append("{:.7f} {:.7f} {:.7f}".format(*v))
    cell_block.append("%ENDBLOCK LATTICE_CART\n")

    return "\n".join(cell_block), "\n".join(pos_block)
