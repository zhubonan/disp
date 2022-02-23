"""
Utility Tasks
"""
import os
import shutil
from gzip import GzipFile

from fireworks import explicit_serialize, FiretaskBase


@explicit_serialize
class GzipDir(FiretaskBase):
    """
    Task to gzip the current working directory.
    """

    required_params = []
    optional_params = []

    def run_task(self, fw_spec=None):
        gzip_dir(os.getcwd())


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
        # Make sure we process only non-zipped filse
        if not fpath.lower().endswith('gz') and os.path.isfile(full_f):
            with open(full_f, 'rb') as f_in, \
                    GzipFile('{}.gz'.format(full_f), 'wb',
                             compresslevel=compresslevel) as f_out:
                shutil.copyfileobj(f_in, f_out)
            shutil.copystat(full_f, '{}.gz'.format(full_f))
            os.remove(full_f)
