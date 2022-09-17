"""
Tests for the utilities
"""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from disp.fws.utils import FWPathManager

# pylint: disable=redefined-outer-name


@pytest.fixture(scope="module")
def manager():
    tmpd = tempfile.mkdtemp()
    yield tmpd, FWPathManager(tmpd)
    shutil.rmtree(tmpd)


def test_base_path(manager):
    """Test the base path for FWPathManager"""
    tmpd, man = manager
    assert man.base_path == Path(tmpd)
    assert man.base_path.is_dir()

    os.environ.pop("FW_CONFIG_FILE", None)
    man = FWPathManager()
    assert man.base_path == Path.home() / "disp-base"

    os.environ["FW_CONFIG_FILE"] = str(Path.home() / ".fireworks/FW_config.yaml")
    man = FWPathManager()
    assert man.base_path == Path.home() / "disp-base"

    os.environ["FW_CONFIG_FILE"] = str(Path.home() / "disp2/config/FW_cofig.yaml")
    man = FWPathManager()
    assert man.base_path == Path.home() / "disp2"

    man.__repr__()


def test_datastore(manager):
    """Test the datastore path"""
    _, man = manager
    assert man.datastore_path.is_dir()


def test_project_path(manager):
    """Test project store path"""
    _, man = manager
    assert man.get_project_path("TEST/C2/run1").is_dir()
