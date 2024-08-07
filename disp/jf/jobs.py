"""
Module defining the jobflow.Job for AIRSS operations
"""
import logging
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Tuple, Union

from castepinput.inputs import CastepInput, CellInput, ParamInput
from jobflow import Maker, Response, job
from pymatgen.core import Structure

from disp.casteptools import get_rand_cell_name
from disp.database import get_hash


class RelaxOutcome(Enum):
    """Outcome of a relaxation"""

    FINISHED = 0
    TIMEDOUT = 1
    ERRORED = 2
    UNDETERMINED = 3
    CYCLE_EXCEEDED = 4
    INSUFFICIENT_TIME = 5


def run_buildcell(seed_name: str, seed_content: str, build_timeout: int = 30, write_seed: bool = True):
    """Run the buildcell executable to generate a random structure."""
    logging.info("Start building a random structure...")
    attempt = 3
    while attempt > 0:
        try:
            proc = subprocess.Popen(
                "buildcell",
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                universal_newlines=True,
            )
            stdout, stderr = proc.communicate(seed_content, timeout=build_timeout)
        except subprocess.TimeoutExpired:
            attempt -= 1
        else:
            break
    if attempt <= 0:
        msg = "Warning - random structure generation timedout"
        logging.error(msg)
        return Response(stop_children=True, output={"message": msg})

    logging.info("Random structure building completed")

    stdout = stdout.decode("utf-8") if isinstance(stdout, bytes) else stdout
    stderr = stderr.decode("utf-8") if isinstance(stderr, bytes) else stderr

    cell_name = get_rand_cell_name(seed_name)
    struct_name = cell_name.replace(".cell", "")

    # Write down the seed file, if requested
    if write_seed:
        Path(seed_name + ".cell").write_text(seed_content)

    # Write down the structure file
    Path(cell_name).write_text(stdout)

    # Write the original, unrelaxed cell structure as '-orig.cell'
    Path(struct_name + "-orig.cell").write_text(stdout)

    output_data = {"struct_name": struct_name, "seed_name": seed_name, "seed_hash": get_hash(seed_content), "struct_content": stdout}
    return output_data


@dataclass
class AirssValidateMaker(Maker):
    """Maker to validate AIRSS calculations"""

    additional_exes: Tuple[str] = tuple()
    required_exes: Tuple[str] = ("buildcell", "castep_relax", "castep2res")
    name = "airss validate"

    @job
    def make(self):
        """Generate a job to validate AIRSS installation"""

        exes_to_check = self.additional_exes + self.required_exes
        not_found = []
        for exe_name in exes_to_check:
            try:
                subprocess.run(["which", exe_name], check=True)
            except subprocess.CalledProcessError:
                not_found.append(exe_name)

        if not_found:
            self.logger.error("AIRSS installation incomplete, these executables are not found:\n" "{}".format(not_found))
            return Response(stop_jobflow=True)
        return None


@dataclass
class AirssBuildcellMaker(Maker):
    """Maker to build AIRSS cells"""

    name = "airss buildcell"
    upload: bool = True
    write_seed = True
    build_timeout: int = 60

    @job
    def make(self, seed_name, project_name, seed_content):
        """Generate a job to build an random cell using AIRSS buildcell"""

        output_data = run_buildcell(seed_name, seed_content, build_timeout=self.build_timeout, write_seed=self.write_seed)
        output_data["project_name"] = project_name

        return Response(output=output_data)


class AirssCastepSinglePointRunner:
    def __init__(self, executable="castep.mpi"):
        self.executable = executable
        self.logger = logging.getLogger(self.__class__.__name__)

    def prepare_inputs(self, struct_name, cellinput: CellInput, paraminput: ParamInput):
        """Write the input files"""
        cell_name = struct_name + ".cell"
        param_name = struct_name + ".param"

        # Convert to string
        if isinstance(cellinput, CastepInput):
            cellinput = cellinput.get_string()
        if isinstance(paraminput, CastepInput):
            paraminput = paraminput.get_string()

        with open(cell_name, "w") as fhandle:
            fhandle.write(cellinput)

        with open(param_name, "w") as fhandle:
            fhandle.write(paraminput)

    def run(self, struct_name, cellinput, paraminput):
        """Perform a singlepoint calculation"""

        paraminput["task"] = "singlepoint"
        self.prepare_inputs(struct_name=struct_name, cellinput=cellinput, paraminput=paraminput)
        output = subprocess.run(self.executable.split() + [struct_name], check=False)
        if output.returncode != 0:
            return 1
        return 0


class AirssCastepRelaxRunner(AirssCastepSinglePointRunner):  # pylint: disable=too-many-instance-attributes
    """
    Runner for CASTEP relaxation
    """

    def __init__(self, executable="castep.mpi", cycles=4, max_fails=2, max_iterations=200):

        super().__init__(executable=executable)
        self.cycles = cycles
        self.logger = logging.getLogger(self.__class__.__name__)
        self.max_fails = max_fails
        self.max_iterations = max_iterations

    def run(self, struct_name, cellinput, paraminput):
        """Perform cyclic relaxation"""

        paraminput["task"] = "geometryoptimization"
        paraminput["write_cell_structure"] = True

        self.prepare_inputs(struct_name=struct_name, cellinput=cellinput, paraminput=paraminput)
        fail_counter = 0
        cycle = 1
        success_counter = 0
        iter_counter = 0
        while cycle <= self.cycles:
            if fail_counter > self.max_fails:
                return 1
            output = subprocess.run(self.executable.split() + [struct_name], check=False)
            if output.returncode != 0:
                fail_counter += 1
                continue
            # Zero the fail counter
            fail_counter = 0
            # Check if the relaxation is successful
            result = None
            max_iter = 0
            with open(struct_name + ".castep") as fhandle:
                for line in fhandle:
                    match = re.search(r"Geometry optimization ([a-z]+)", line)
                    if match is not None:
                        if match.group(1) == "completed":
                            result = True
                        elif match.group(1) == "failed":
                            result = False
                    match = re.search(r"Finished iteration +(\d+)", line)
                    if match is not None:
                        max_iter = int(match.group(1))
            iter_counter += max_iter
            # Relaxation is successful rerun again with the same structure
            if result is True:
                success_counter += 1
            if result is False:
                success_counter = 0

            # Two successive successful relaxations - break the loop
            if success_counter >= 2:
                break
            # Exceeded the total number of iterations to be run
            if iter_counter >= self.max_iterations:
                break

            # Copy the structure from the output file to the input file
            out_cell = CellInput.from_file(struct_name + "-out.cell")
            in_cell = CellInput.from_file(struct_name + ".cell")
            in_cell.set_cell(out_cell.get_cell())
            in_cell.set_positions(*out_cell.get_positions())
            in_cell.save(struct_name + ".cell")
            cycle += 1

        if success_counter >= 2:
            return 0
        return 1


@dataclass
class AirssCastepRelaxMaker(Maker):
    """Maker to perform AIRSS CASTEP relaxation"""

    name = "airss castep relax"
    executable: str = "castep.mpi"
    cycles: int = 4
    max_fails: int = 2
    max_iterations: int = 200
    stop_if_not_converged: bool = False

    @job
    def make(self, structure: Structure, struct_name: str, cellinput: CellInput, paraminput: ParamInput):
        """Generate a job to perform AIRSS CASTEP relaxation"""

        runner = AirssCastepRelaxRunner(
            executable=self.executable, cycles=self.cycles, max_fails=self.max_fails, max_iterations=self.max_iterations
        )

        # Set the lattice, element and the positions
        cellinput.set_positions([str(elem) for elem in structure.species], structure.cart_coords)
        cellinput.set_cell(structure.lattice.matrix)
        return_code = runner.run(struct_name, cellinput, paraminput)
        task_doc = compose_task_doc(struct_name)

        if return_code != 0 and self.stop_if_not_converged:
            stop = True
        else:
            stop = False
        return Response(stop_children=stop, output=task_doc)


class AirssBuildandRelaxMaker(Maker):
    """Maker to perform AIRSS CASTEP relaxation"""

    name = "airss build and relax"
    write_seed = True
    build_timeout: int = 60
    executable: str = "castep.mpi"
    cycles: int = 4
    max_fails: int = 2
    max_iterations: int = 200
    stop_if_not_converged: bool = False

    @job
    def make(self, seed_name, project_name, seed_content, paraminput: ParamInput):
        """Generate a job to run build cell then relax AIRSS CASTEP relaxation"""

        buildcell_output = run_buildcell(seed_name, seed_content, build_timeout=self.build_timeout, write_seed=self.write_seed)
        buildcell_output["project_name"] = project_name
        struct_name = buildcell_output["struct_name"]
        runner = AirssCastepRelaxRunner(
            executable=self.executable, cycles=self.cycles, max_fails=self.max_fails, max_iterations=self.max_iterations
        )

        # Set the lattice, element and the positions
        cellinput = CellInput.from_file(struct_name + ".cell")
        return_code = runner.run(struct_name, cellinput, paraminput)
        task_doc = compose_task_doc(struct_name)
        task_doc.update(buildcell_output)

        if return_code != 0 and self.stop_if_not_converged:
            stop = True
        else:
            stop = False
        return Response(stop_children=stop, output=task_doc)


@dataclass
class AirssCastepSinglePointMaker(Maker):
    """Maker to perform AIRSS CASTEP relaxation"""

    name = "airss castep singlepoint"
    executable: str = "castep.mpi"

    @job
    def make(self, structure: Structure, struct_name: str, cellinput: CellInput, paraminput: ParamInput):
        """Generate a job to perform AIRSS CASTEP relaxation"""

        runner = AirssCastepSinglePointRunner(executable=self.executable)

        # Set the lattice, element and the positions
        cellinput.set_positions([str(elem) for elem in structure.species], structure.cart_coords)
        cellinput.set_cell(structure.lattice.matrix)
        return_code = runner.run(struct_name, cellinput, paraminput)
        task_doc = compose_task_doc(struct_name)
        return Response(stop_children=return_code != 0, output=task_doc)


def compose_task_doc(struct_name):
    """Compose the task document for the relaxation"""

    from ase import Atoms
    from pymatgen.io.ase import AseAtomsAdaptor

    from ..restools import save_airss_res

    energy = None
    pressure = None
    efficiency = None
    spin = 0.0
    modspin = 0.0
    spin_moms = []
    in_spin_group = False
    with open(struct_name + ".castep") as fhandle:
        for line in fhandle:
            if "NB est. 0K energy" in line:
                energy = float(line.split()[-2])
            if "Pressure: " in line:
                pressure = float(line.split()[-2])
            if "Overall parallel efficiency" in line:

                match = re.search(r"(\d+)%", line)
                if match:
                    efficiency = float(match.group(1)) / 100.0
            if "Spin den" in line:
                spin = float(line.split()[-2])
            if "|Spin den" in line:
                modspin = float(line.split()[-2])
            # Record the spin moments
            if " Total  Charge(e)   Spin(hbar/2)" in line:
                in_spin_group = True
                spin_moms = []
            if " Length (A)" in line:
                in_spin_group = False
            if in_spin_group:
                tokens = line.split()
                if re.match(r"^ +[A-Za-z]+ ", line):
                    spin_moms.append(float(tokens[-1]))

    if Path(struct_name + "-out.cell").is_file():
        cell = CellInput.from_file(struct_name + "-out.cell")
    else:
        cell = CellInput.from_file(struct_name + ".cell")
    elements, positions, tags = cell.get_positions()
    atoms = Atoms(symbols=elements, positions=positions, cell=cell.get_cell(), pbc=True)

    info = {"uid": struct_name, "H": energy}
    save_airss_res(atoms, info, fname=struct_name + ".res", force_write=True)
    structure = AseAtomsAdaptor.get_structure(atoms)
    if spin_moms:
        structure.add_spin_by_site(spin_moms)
    doc = {
        "structure": structure,
        "volume": structure.volume,
        "reduced_formula": structure.reduced_formula,
        "composition": structure.composition,
        "num_sites": structure.num_sites,
        "n_elems": structure.n_elems,
        "label": struct_name,
        "energy": energy,
        "spin": spin,
        "mod_spin": modspin,
        "pressure": pressure,
        "parallel_efficiency": efficiency,
        "energy_per_atom": energy / len(atoms),
        "res_content": Path(struct_name + ".res").read_text(),
    }
    return doc
