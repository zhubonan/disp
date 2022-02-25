"""
Utility module
"""
from pathlib import Path
from contextlib import contextmanager
import tempfile
import os
import shutil

DATASTORE_NAME = 'airss-datastore'


class FWPathManager:
    """
    Manager for managing the paths.

    The folder structure looks like:

      <BASE_PATH>
      |- config
         | - FW_config.yaml
      |- airss-datastore
         |- <PROJECT_NAME>
      |....
    The position of FW_config file is detected using the environmental
    variable FWPathManager, and the BASE_PATH is always one level above
    it. If FW_CONFIG_FILE is not set, or it points to $USER/.fireworks,
    BASE_PATH defaults to $HOME/disp-base.
    """
    def __init__(self, base_path=None):
        """Instantiate a FWPathManager"""
        self.base_path = None
        self._set_base_path(base_path)
        self.set_datastore_path()

    def _set_base_path(self, base_path):
        """Return the base directory for storing AIRSS related file data"""
        if base_path is None:
            fw_config = os.environ.get('FW_CONFIG_FILE')
            user = os.environ.get('USER')
            if not fw_config or f'{user}/.fireworks' in fw_config:
                base_path = Path.home() / 'disp-base'
            else:
                base_path = Path(fw_config).parent.parent
        else:
            base_path = Path(base_path)

        base_path.mkdir(parents=True, exist_ok=True)
        self.base_path = base_path

        return base_path

    def set_datastore_path(self):
        """Get the data storage path"""
        datastore = self.base_path / DATASTORE_NAME
        datastore.mkdir(parents=True, exist_ok=True)
        self.datastore_path = datastore
        return datastore

    def get_project_path(self, project_name):
        """Return the path to store data under a specific project"""

        datastore = self.datastore_path
        project_path = datastore / project_name
        project_path.mkdir(parents=True, exist_ok=True)
        return project_path

    def __repr__(self):
        return f'FWPathManager(base_path={self.base_path})'


@contextmanager
def isolated_filesystem():
    """A context manager that creates a temporary folder and changes
    the current working directory to it for isolated filesystem tests.
    """
    cwd = os.getcwd()
    target = tempfile.mkdtemp()
    os.chdir(target)
    try:
        yield target
    finally:
        os.chdir(cwd)
        try:
            shutil.rmtree(target)
        except OSError:
            pass
