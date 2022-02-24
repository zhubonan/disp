"""
Tests for the commandline interface
"""
from pathlib import Path
import os
import shutil
from this import d

import pytest
from click.testing import CliRunner
from disp.cli.cmd_disp import main


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
    yield tmp_path.absolute()
    os.chdir(cwd)

@pytest.fixture
def isolated_project_dir(isolated_dir, datapath):
    """Directory with search seed prepared"""
    shutil.copy2(datapath / 'Si2.cell', isolated_dir / 'Si2.cell')
    shutil.copy2(datapath / 'Si2.param', isolated_dir / 'Si2.param')
    # For the pp3 case
    shutil.copy2(datapath / 'pp3_relax/Al.cell', isolated_dir / 'Al.cell')
    shutil.copy2(datapath / 'pp3_relax/Al.pp', isolated_dir / 'Al.pp')
    return isolated_dir


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


def test_deploy_search(isolated_project_dir):
    """
    Test deploy as search from CLI
    """
    from fireworks.core.launchpad import LaunchPad
    runner = CliRunner()
    args = ['--db-file', 'disp_db.yaml', '--lpad-file', 'my_launchpad.yaml', 'deploy', 'search']
    args.extend(['--seed', 'Si2', '--num', '5', '--project', 'testproject'])
    output = runner.invoke(main, args)
    assert output.exit_code == 0

    args.extend(['--dryrun'])
    output = runner.invoke(main, args)
    assert output.exit_code == 0

    # PP3 search
    args = ['--db-file', 'disp_db.yaml', '--lpad-file', 'my_launchpad.yaml', 'deploy', 'search', '--code', 'pp3']
    args.extend(['--seed', 'Al', '--num', '5', '--project', 'testproject'])
    output = runner.invoke(main, args)
    assert output.exit_code == 0

@pytest.fixture
def deploy_and_run(isolated_project_dir, new_db, clean_launchpad):
    """
    Test deploy as search from CLI
    """
    from subprocess import run
    runner = CliRunner()

    # PP3 search
    args = ['--db-file', 'disp_db.yaml', '--lpad-file', 'my_launchpad.yaml', 'deploy', 'search', '--code', 'pp3']
    args.extend(['--seed', 'Al', '--num', '5', '--project', 'testproject'])
    output = runner.invoke(main, args)
    assert output.exit_code == 0

    # Launch the search
    return_code = run(['rlaunch',  '-l', 'my_launchpad.yaml', 'rapidfire'])
    assert return_code.returncode == 0

    # retrieve project
    args = ['--db-file', 'disp_db.yaml', '--lpad-file', 'my_launchpad.yaml', 'db', 'retrieve-project', '--project', 'testproject']
    output = runner.invoke(main, args)
    assert output.exit_code == 0
    assert len(list(Path().glob('*.res'))) == 5
    return isolated_project_dir


def test_db_post_run(deploy_and_run):
    """Test analysis command post run"""

    runner = CliRunner()

    args = ['--db-file', 'disp_db.yaml', '--lpad-file', 'my_launchpad.yaml', 'db', 'summary', '--project', 'testproject']
    output = runner.invoke(main, args)
    assert output.exit_code == 0
    lines = output.stdout.splitlines()
    assert any([ '5' in line for line in  lines])
    assert any([ 'testproject' in line for line in  lines])

    # Throughput command
    args = ['--db-file', 'disp_db.yaml', '--lpad-file', 'my_launchpad.yaml', 'db', 'throughput', '--no-plot']
    output = runner.invoke(main, args)
    assert output.exit_code == 0
    assert (Path() / 'throughput.csv').is_file()


    # The launch dir command
    for cmd in ['list-projects', 'list-seeds', 'build-index']:
        args = ['--db-file', 'disp_db.yaml', '--lpad-file', 'my_launchpad.yaml', 'db', cmd]
        output = runner.invoke(main, args)
        assert output.exit_code == 0