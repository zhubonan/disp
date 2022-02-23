"""
Test fixtures
"""

import os
import tempfile
from pathlib import Path

import pytest
from fireworks.core.launchpad import LaunchPad
from fireworks import fw_config

from disp.database import SearchDB
import disp.fws.tasks

from mongoengine import disconnect

# pylint: disable=redefined-outer-name, too-many-instance-attributes, import-outside-toplevel
TESTDB_NAME = 'disp-db-testing'
TEST_COLLECTION = 'disp_entry'

MODULE_DIR = Path(__file__).parent
DATA_DIR = MODULE_DIR / 'test_data'


@pytest.fixture(scope='session')
def new_db():
    """A brand new database"""
    disconnect(alias='disp')
    searchdb = SearchDB(
        host='localhost',
        port=27017,
        database=TESTDB_NAME,
        collection=TEST_COLLECTION,
        user=None,
        password=None,
    )
    searchdb.collection.delete_many({})
    searchdb.set_identity(fw_id=1, uuid='UUID4')
    yield searchdb
    searchdb.collection.delete_many({})


@pytest.fixture
def clean_db(new_db):
    """A clean database"""
    new_db.collection.delete_many({})
    return new_db


@pytest.fixture
def get_data_dir():
    """Get the directory containing test data"""
    def _get_data_dir(name):
        """Return the Path pointing to the test data"""
        return DATA_DIR / name

    return _get_data_dir


@pytest.fixture(scope='session')
def launchpad():
    """Get a launchpad"""
    # Manually add the package to be included
    fw_config.USER_PACKAGES = [
        'fireworks.user_objects', 'fireworks.utilities.tests', 'fw_tutorials',
        'fireworks.features'
    ]
    lpd = LaunchPad(name=TESTDB_NAME, strm_lvl='ERROR')
    lpd.reset(password=None, require_password=False)
    disp.fws.DB_FILE = os.path.join(DATA_DIR, 'db_file.yaml')
    yield lpd
    lpd.connection.drop_database(TESTDB_NAME)


@pytest.fixture
def clean_launchpad(launchpad):
    """Get a launchpad in clean state"""
    launchpad.reset(password=None, require_password=False)
    return launchpad


@pytest.fixture
def temp_workdir():
    """Fixture for goining into a temporary directory"""
    tempdir = tempfile.mkdtemp()
    current_dir = os.getcwd()
    os.chdir(tempdir)
    yield Path(tempdir)
    os.chdir(current_dir)
