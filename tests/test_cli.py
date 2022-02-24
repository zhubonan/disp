"""
Tests for the commandline interface
"""
from pathlib import Path
import os
import shutil

import pytest
from click.testing import CliRunner
from disp.cli.cmd_disp import main

@pytest.fixture
def datapath():
    return Path(__file__).parent / 'test_data'

@pytest.fixture
def clean_environ():
    """Clean the environmental variables"""
    keys = ['FW_CONFIG_FILE', 'DISP_DB_FILE']
    import disp.database.api as dba
    db_back = dba.DISP_DB_FILE = None
    dba.DISP_DB_FILE = None
    import fireworks.core.launchpad as lp
    lp.LAUNCHPAD_LOC = None
    lp_back = dba.DISP_DB_FILE

    yield
    dba.DISP_DB_FILE = db_back
    lp.LAUNCHPAD_LOC = lp_back

@pytest.fixture
def isolated_dir(tmp_path, datapath, clean_environ):
    """Build and example directory with db and launchpad files"""
    shutil.copy2(datapath / 'my_launchpad.yaml', tmp_path / 'my_launchpad.yaml')
    shutil.copy2(datapath / 'disp_db.yaml', tmp_path / 'disp_db.yaml')
    cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(cwd)


def test_disp(datapath, clean_environ):
    """Test the main entry point"""

    runner = CliRunner()
    output = runner.invoke(main)
    assert output.exit_code == 0

def test_check_db(datapath, clean_environ):
    """Test the check sub command"""

    runner = CliRunner()
    args = ['--db-file', str(datapath / 'disp_db.yaml'), '--lpad-file', str(datapath / 'my_launchpad.yaml')]
    args.extend(['check', 'database'])
    output = runner.invoke(main, args)
    assert output.exit_code == 0

    # This should error
    with runner.isolated_filesystem():
        output = runner.invoke(main, ['check', 'database'])
    assert output.exit_code != 0

 
def test_check_airss(datapath, clean_environ):
    """Test the check sub command"""

    runner = CliRunner()
    args = ['check', 'airss']
    output = runner.invoke(main, args)
    assert output.exit_code == 0

def test_check_scheduler():

    runner = CliRunner()
    args = ['check', 'scheduler']
    output = runner.invoke(main, args)
    assert output.exit_code != 0

    args = ['check', 'scheduler', '--allow-dummy']
    output = runner.invoke(main, args)
    assert output.exit_code == 0

def test_db_commands(isolated_dir, new_db):
    """Test db commands"""

    runner = CliRunner()
    args = ['db', 'summary']
    output = runner.invoke(main, args)
    assert output.exit_code == 0

    args = ['db', 'build-index']
    output = runner.invoke(main, args)
    assert output.exit_code == 0

    args = ['db', 'throughput', '--no-plot', ]
    output = runner.invoke(main, args)
    assert output.exit_code == 0