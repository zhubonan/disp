"""
Test the Object Document mapping
"""
from hashlib import md5
from pathlib import Path

import mongoengine.errors as merr
import pytest
from mongoengine import connect, disconnect

from disp.database.odm import (
    DispEntry,
    InitialStructureFile,
    ParamFile,
    ResFile,
    ResProperty,
    SeedFile,
)

L2FSDATA = (Path(__file__).parent / "data") / "2L2FS"


@pytest.fixture
def new_db():
    """
    Provide an new global connect instance
    """
    disconnect(alias="disp")
    db = connect("mongoenginetest", alias="disp", host="mongomock://localhost")
    yield db
    disconnect(alias="disp")


@pytest.fixture
def seed_l2fs():
    content = (L2FSDATA / "2L2FS.cell").read_text()
    seed = SeedFile(content=content, seed_name="2L2FS", project_name="2L2FS/run1")
    seed.md5hash = md5(content.encode("utf-8")).hexdigest()
    return seed


@pytest.fixture
def param_l2fs():
    content = (L2FSDATA / "2L2FS.param").read_text()
    param = ParamFile(content=content, seed_name="2L2FS", project_name="2L2FS/run1")
    return param


@pytest.fixture
def init_structure():
    content = (L2FSDATA / "2L2FS-200625-100846-0e5188-orig.cell").read_text()
    init = InitialStructureFile(content=content, seed_name="2L2FS", project_name="2L2FS/run1", struct_name="2L2FS-200625-100846-0e5188")
    return init


@pytest.fixture
def res_file():
    content = (L2FSDATA / "2L2FS-200625-100846-0e5188.res").read_text()
    init = ResFile(content=content, seed_name="2L2FS", project_name="2L2FS/run1", struct_name="2L2FS-200625-100846-0e5188")
    return init


def test_seed_entry(new_db):
    """Test Seed"""
    content = (L2FSDATA / "2L2FS.cell").read_text()
    seed = SeedFile(content=content, seed_name="2L2FS", project_name="2L2FS/run1")
    with pytest.raises(merr.ValidationError):
        seed.save()
    seed.md5hash = md5(content.encode("utf-8")).hexdigest()
    seed.save()

    seed2 = SeedFile(content=content, seed_name="2L2FS", project_name="2L2FS/run1")
    seed2.md5hash = seed.md5hash


def test_param_entry(new_db):
    """Test Seed"""
    content = (L2FSDATA / "2L2FS.param").read_text()
    param = ParamFile(content=content, seed_name="2L2FS", project_name="2L2FS/run1")
    param.md5hash = md5(content.encode("utf-8")).hexdigest()
    param.save()
    assert param.content
    param2 = ParamFile(content=content, seed_name="2L2FS", project_name="2L2FS/run1")
    param2.md5hash = md5(content.encode("utf-8")).hexdigest()


def test_init_structure(new_db, init_structure, seed_l2fs):
    """Test the initial structure"""
    init_structure.seed_file = seed_l2fs
    seed_l2fs.save()
    init_structure.save()
    assert init_structure.id
    assert init_structure.seed_file
    assert init_structure.struct_name


def test_res_entry(new_db, init_structure, seed_l2fs, res_file):
    """Test functionality of the Seed"""
    res_file.seed_file = seed_l2fs
    init_structure.seed_file = seed_l2fs
    res_file.init_structure_file = init_structure
    res_file.cascade_save()
    res_file.save()
    assert res_file.id
    assert res_file.seed_file
    assert res_file.content
