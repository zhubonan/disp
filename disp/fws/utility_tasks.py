"""
Utility Tasks
"""
import os
import shutil
from gzip import GzipFile
from pathlib import Path

from fireworks import FiretaskBase, explicit_serialize
from fireworks.utilities.fw_utilities import get_fw_logger


@explicit_serialize
class GzipDir(FiretaskBase):
    """
    Task to gzip the current working directory.
    """

    required_params = []
    optional_params = []

    def run_task(self, fw_spec=None):
        gzip_dir(os.getcwd())


@explicit_serialize
class CleanDir(FiretaskBase):
    """
    Task to clean all files in the directory
    """

    required_params = []
    optional_params = []
    extensions = [".castep", ".cell", ".param", ".bib", ".usp", ".res", ".recpot", ".conv"]

    def run_task(self, fw_spec=None):
        extensions = list(self.extensions)
        # Check if we are indeed cleaning the working directory
        if not fw_spec.get("clean_dir"):
            return

        # Modify the cleaning list
        if fw_spec.get("clean_dir_included"):
            extensions.extend(fw_spec.get("clean_dir_included"))

        if fw_spec.get("clean_dir_excluded"):
            for key in fw_spec.get("clean_dir_excluded"):
                extensions.remove(key)

        # Clean all files with pre-defined extensions
        for path in Path(os.getcwd()).glob("*"):
            if path.is_file() and any(str(path).endswith(ext) for ext in extensions):
                path.unlink()


@explicit_serialize
class USPCopyTask(FiretaskBase):
    """Task for copying any USP files into the working directory"""

    logger = get_fw_logger(__name__, l_dir=None, stream_level="INFO")

    def run_task(self, fw_spec=None):
        """
        Run the task
        """
        pots = set()

        def gather_pots(content, pots):
            for line in content.split("\n"):
                if ".usp" in line or ".recpot" in line or ".upf" in line:
                    pots.add(line.split()[-1])

        # Find a list of required potential files in the current working directory
        for cell_file in Path().glob("*.cell"):
            content = cell_file.read_text()
            gather_pots(content, pots)

        # Check the structure content in the spec that is yet to be written to the disk
        if "struct_content" in fw_spec:
            content = fw_spec["struct_content"]
            gather_pots(content, pots)

        # Check the seed content in the spec that is yet to be written to the disk
        if "seed_content" in fw_spec:
            content = fw_spec["seed_content"]
            gather_pots(content, pots)

        # No copying is needed
        if not pots:
            self.logger.info("No required potential files")
            return
        self.logger.info("Looking for potential files: {pots}")

        # Copy from the POSPOT directory
        pspot = fw_spec.get("_fw_env", {}).get("PSPOT_DIR")
        if pspot is None:
            # Do we have a system PSPOT_DIR set?
            pspot = os.environ.get("PSPOT_DIR")
            if pspot is None:
                raise RuntimeError("PSPOT must be defined for file-based pseudpotentials to work!")
            self.logger.info(f"PSPOT_DIR already exists: {pspot}")
            # Nothing to do as CASTEP will consult PSPOT_DIR itself
            return
        self.logger.info(f"PSPOT_DIR from worker environment: {pspot}")

        pspot = Path(pspot)
        # Copy the potential file to the current folder
        for potname in pots:
            if not (pspot / potname).is_file():
                raise RuntimeError("Missing file {potname} from the potential directory {pspot}")
            shutil.copy2(str(pspot / potname), potname)
            self.logger.info(f"Copied potential file: {potname}")


def gzip_dir(path, compresslevel=6):
    """
    Gzips all files in a directory. Note that this is different from
    shutil.make_archive, which creates a tar archive. The aim of this method
    is to create gzipped files that can still be read using common Unix-style
    commands like zless or zcat.

    No action is performed for folders in the directory.

    Args:
        path (str): Path to directory.
        compresslevel (int): Level of compression, 1-9. 9 is default for
            GzipFile, 6 is default for gzip.
    """
    for fpath in os.listdir(path):
        full_f = os.path.join(path, fpath)
        # Make sure we process only non-zipped files
        if not fpath.lower().endswith("gz") and os.path.isfile(full_f):
            with open(full_f, "rb") as f_in, GzipFile(f"{full_f}.gz", "wb", compresslevel=compresslevel) as f_out:
                shutil.copyfileobj(f_in, f_out)
            shutil.copystat(full_f, f"{full_f}.gz")
            os.remove(full_f)
