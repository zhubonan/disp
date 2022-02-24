"""
Test for the database module
"""
# pylint: disable=redefined-outer-name, too-many-instance-attributes, import-outside-toplevel
from pathlib import Path
import pytest

from disp.database import SearchDB, SeedFile, ResFile, InitialStructureFile, ParamFile

TEST_DB_NAME = 'disp-db-testing'
TEST_COLLECTION = 'airss-test'

MODULE_DIR = Path(__file__).parent
DATA_DIR = MODULE_DIR / 'test_data'


def test_from_db_file():
    """Test instantiate SearchDB from a yaml file"""
    searchdb = SearchDB.from_db_file(DATA_DIR / 'db_file.yaml')
    assert searchdb.user is None
    assert searchdb.host == 'localhost'
    assert searchdb.database


@pytest.fixture
def seed():
    """A string of the seed"""
    text = """
#SPECIES=C
#NATOMS=10
#VARVOL=10
"""
    return text


@pytest.fixture
def param():
    """A string of the parameters"""
    text = """
task: singlepoint
xc_funtional: pbe
"""
    return text


def test_build_index(clean_db):
    """Test index creation functionality"""
    clean_db.build_indexes(['param_hash'])
    info = clean_db.collection.index_information()

    for idx_name in clean_db.INDICIES:
        assert any([idx_name in key for key in info.keys()])
    assert any(['param_hash' in key for key in info.keys()])


def test_insert_seed(clean_db, seed):
    """Test insertion of seed document"""
    seed1 = clean_db.insert_seed(project_name='test/run1',
                                 seed_name='C10',
                                 seed_content=seed)
    seed2 = clean_db.insert_seed(project_name='test/run1',
                                 seed_name='C10',
                                 seed_content=seed)
    assert seed1.id == seed2.id
    assert SeedFile.objects.count() == 1

    assert seed1.creator.uuid == 'UUID4'
    assert seed1.creator.fw_id == 1


def test_insert_param(clean_db, param):
    """Test insertion of seed document"""
    param1 = clean_db.insert_param(project_name='test/run1',
                                   param_content=param,
                                   seed_name='TEST')
    param2 = clean_db.insert_param(project_name='test/run1',
                                   param_content=param,
                                   seed_name='TEST')
    assert param1 == param2
    assert ParamFile.objects.count() == 1


def test_insert_record(clean_db, seed, param):
    """Test inserting a full record"""
    res = """
TITL 0 0 0 0
BLA
"""

    clean_db.insert_search_record(project_name='test/run1',
                                  struct_name='C10-TEST-1',
                                  res_content=res,
                                  param_content=param,
                                  seed_name='C10',
                                  seed_content=seed)

    clean_db.insert_search_record(project_name='test/run1',
                                  struct_name='C10-TEST-2',
                                  res_content=res,
                                  param_content=param,
                                  seed_name='C10',
                                  seed_content=seed)

    assert ParamFile.objects.count() == 1
    assert SeedFile.objects.count() == 1
    assert ResFile.objects.count() == 2

    results = clean_db.retrieve_project('test/run1',
                                        include_seed=True,
                                        include_param=True)
    # Check relavent field are populated
    assert results[0].param_file.content
    assert results[0].seed_file.content

    results = clean_db.retrieve_project('test/run1',
                                        include_seed=False,
                                        include_param=False)
    assert len(results) == 2
    assert results[0].param_file is None
    assert results[0].seed_file is None


def test_insert_init_structure(clean_db, seed, param):
    """Test inserting a full record"""
    res = """
TITL 0 0 0 0
BLA
"""
    init = seed + 'init'
    clean_db.insert_initial_structure(project_name='test/run1',
                                      struct_name='C10-TEST-1',
                                      seed_name='C10',
                                      struct_content=init,
                                      seed_content=seed)

    clean_db.insert_search_record(project_name='test/run1',
                                  struct_name='C10-TEST-1',
                                  res_content=res,
                                  param_content=param,
                                  seed_name='C10',
                                  seed_content=seed)

    assert InitialStructureFile.objects(project_name='test/run1').count() == 1

    results = clean_db.retrieve_project('test/run1',
                                        include_seed=True,
                                        include_param=True,
                                        include_initial_structure=True)
    # Check relavent field are populated
    assert results[0].param_file.content
    assert results[0].seed_file.content
    assert results[0].init_structure_file.content


def test_upoad_dot_castep(clean_db, temp_workdir):
    """Test upload the downloading .castep files"""
    content = 'CASTEP 19'
    struct_name = 'test'
    seed_name = 'test_seed'
    project_name = 'test_project'
    Path(struct_name + '.castep').write_text(content)

    clean_db.upload_dot_castep(struct_name, seed_name, project_name)

    with pytest.raises(FileExistsError):
        clean_db.upload_dot_castep(struct_name, seed_name, project_name)

    # Test retrieving
    Path(struct_name + '.castep').unlink()
    clean_db.retrieve_dot_castep(struct_name, seed_name, project_name)
    assert Path(struct_name + '.castep').read_text() == content

    # Test deletion
    clean_db.delete_dot_castep(struct_name, seed_name, project_name)
    with pytest.raises(FileNotFoundError):
        clean_db.retrieve_dot_castep(struct_name, seed_name, project_name)
