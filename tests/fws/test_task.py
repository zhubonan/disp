"""
Test the FireTasks
"""
import tarfile
import os
import subprocess
from pathlib import Path
import contextlib

import pytest

from fireworks.core.firework import Firework, Workflow
from fireworks.core.rocket_launcher import launch_rocket
from fireworks.core.fworker import FWorker
from disp.fws.tasks import AirssBuildcellTask, AirssPp3RelaxTask, AirssValidateTask, AirssGulpRelaxTask, AirssCastepRelaxTask, RelaxOutcome, DbRecordTask
from disp.scheduler import Dummy

# pylint: disable=redefined-outer-name, too-many-instance-attributes, import-outside-toplevel, unused-argument, protected-access

# Some global variables
MODULE = __name__


def has_exe(exe):
    """Check whether a exe is in the path"""
    return_code = subprocess.call(['which', exe])
    if return_code == 0:
        return True
    return False


need_gulp = pytest.mark.skipif(  # pylint: disable=invalid-name
    not (has_exe('gulp_relax') and has_exe('gulp'))
    or bool(os.environ.get('CI')),
    reason='GULP is not avalaible')
need_castep = pytest.mark.skipif(  # pylint: disable=invalid-name
    not has_exe('castep.mpi') or bool(os.environ.get('CI')),
    reason='CASTEP is not avalaible')
need_buildcell = pytest.mark.skipif(  # pylint: disable=invalid-name
    not has_exe('buildcell'),
    reason='Buildcell is not avalaible')

need_pp3 = pytest.mark.skipif(  # pylint: disable=invalid-name
    not has_exe('pp3'),
    reason='Pp3 is not avalaible')


def _modcell(cell_in):
    """Modify the cell"""
    out = []
    for line in cell_in:
        out.append(line.replace(' C ', ' Si '))
    return out


@contextlib.contextmanager
def backup_path():
    """Backup the content in PATH"""
    path_backup = os.environ.get('PATH')
    # Remove AIRSS related stuff in the PATH
    yield os.environ.get('PATH')
    os.environ['PATH'] = path_backup


@need_buildcell
def test_buildcell_task(clean_launchpad, temp_workdir, get_data_dir, new_db, datapath):
    """Test the buildcell task"""
    with open(get_data_dir('buildcell') / 'C2.cell') as fhandle:
        seed_content = fhandle.read()

    btask = AirssBuildcellTask(seed_content=seed_content,
                               seed_name='C2',
                               deposit_init_structure=True,
                               project_name='TEST/C')
    fwk = Firework([btask], spec={'db_file': str(datapath / 'disp_db.yaml')})
    wkf = Workflow.from_Firework(fwk)
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd)

    struct_paths = [p.stem for p in temp_workdir.glob('C2-*.cell')]
    struct_name = lpd.get_launch_by_id(1).action.stored_data['struct_name']
    assert struct_name in struct_paths
    assert Path('C2.cell').is_file()

    # Check the initial structure is deposited
    entry = new_db.collection.find_one({'struct_name': struct_name})
    assert entry['seed_name'] == 'C2'
    assert entry['seed_file']

    Path('C2.cell').unlink()
    btask = AirssBuildcellTask(seed_content=seed_content,
                               seed_name='C2',
                               keep_seed=False,
                               project_name='TEST/C')
    fwk = Firework([btask])
    wkf = Workflow.from_Firework(fwk)
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd)
    assert not Path('C2.cell').is_file()


@need_buildcell
def test_airss_validation_task(clean_launchpad, temp_workdir):
    """Test the validation task"""
    del temp_workdir
    btask = AirssValidateTask()
    fwk = Firework([btask])
    wkf = Workflow([fwk])
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd)
    action = lpd.get_launch_by_id(1).action
    assert action.defuse_children is False

    # Remove any AIRSS related entry in PATH
    # NOTE: It is assumed that such entries contain the work 'airss'
    with backup_path() as current_path:
        paths = current_path.split(':')
        # Remove AIRSS related stuff in the PATH
        new_paths = ':'.join(
            [path for path in paths if 'airss' not in path.lower()])
        os.environ['PATH'] = new_paths
        lpd.add_wf(wkf)
        launch_rocket(lpd)
        action = lpd.get_launch_by_id(2).action

    assert action.defuse_children


@need_gulp
def test_gulp_relax_task(clean_launchpad, temp_workdir, get_data_dir):
    """Test the buildcell task"""
    with open(get_data_dir('gulp_relax') / 'C2-RAND.cell') as fhandle:
        struct_content = fhandle.read()

    with open(get_data_dir('gulp_relax') / 'C2.lib') as fhandle:
        param_content = fhandle.read()

    btask = AirssGulpRelaxTask(
        param_content=param_content,
        cycles=100,
        executable='gulp',
    )
    # project_name = 'TEST/C2'
    fwk = Firework(
        [btask],
        spec={
            'struct_name': 'C2-TEST',
            'struct_content': struct_content,
            'seed_name': 'C2',
            'pressure': 100,
        })

    wkf = Workflow([fwk])
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd)

    assert Path('C2-TEST.castep').is_file
    assert len(list(temp_workdir.glob('C2-TEST.res'))) == 1
    assert lpd.get_launch_by_id(
        1).action.stored_data['relax_status'] == RelaxOutcome.FINISHED.name


@need_gulp
def test_full_gulp(clean_launchpad, temp_workdir, get_data_dir):
    """Test the buildcell task followed by gulp"""
    with open(get_data_dir('gulp_relax') / 'C2.cell') as fhandle:
        seed_content = fhandle.read()

    with open(get_data_dir('gulp_relax') / 'C2.lib') as fhandle:
        param_content = fhandle.read()

    btask = AirssBuildcellTask(seed_content=seed_content,
                               seed_name='C2',
                               project_name='TEST/C2')
    rtask = AirssGulpRelaxTask(
        param_content=param_content,
        cycles=100,
        executable='gulp',
    )

    fwb = Firework([btask])
    fwr = Firework([rtask])
    wkf = Workflow([fwb, fwr], links_dict={fwb: [fwr]})
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd)
    launch_rocket(lpd)

    assert Path('C2.cell').is_file
    assert len(list(temp_workdir.glob('C2-*.res'))) == 1


@need_gulp
def test_full_gulp_comb(clean_launchpad, temp_workdir, get_data_dir):
    """Test the buildcell task followed by gulp, packaged in the same FW"""
    with open(get_data_dir('gulp_relax') / 'C2.cell') as fhandle:
        seed_content = fhandle.read()

    with open(get_data_dir('gulp_relax') / 'C2.lib') as fhandle:
        param_content = fhandle.read()

    btask = AirssBuildcellTask(seed_content=seed_content,
                               seed_name='C2',
                               store_content=False,
                               project_name='TEST/C2')
    rtask = AirssGulpRelaxTask(
        param_content=param_content,
        cycles=100,
        executable='gulp',
    )

    fwb = Firework([btask, rtask])
    wkf = Workflow([fwb])
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd, pdb_on_exception=True)

    assert len(list(temp_workdir.glob('C2-*.res'))) == 1


@need_pp3
def test_pp3_relax(clean_launchpad, temp_workdir, get_data_dir):
    """Test the buildcell task followed by pp3, packaged in the same FW"""
    with open(get_data_dir('pp3_relax') / 'Al.cell') as fhandle:
        seed_content = fhandle.read()

    with open(get_data_dir('pp3_relax') / 'Al.pp') as fhandle:
        param_content = fhandle.read()

    btask = AirssBuildcellTask(seed_content=seed_content,
                               seed_name='Al',
                               store_content=False,
                               project_name='TEST/Al')
    rtask = AirssPp3RelaxTask(
        param_content=param_content,
        executable='pp3',
        cycles=100,
    )

    fwb = Firework([btask, rtask])
    wkf = Workflow([fwb])
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd, pdb_on_exception=True)

    assert len(list(temp_workdir.glob('Al-*.res'))) == 1


def test_modcell_task(clean_launchpad, temp_workdir, get_data_dir):
    """Test the Modcell task"""
    del temp_workdir
    from disp.fws.tasks import AirssModcellTask
    with open(get_data_dir('gulp_relax') / 'C2-RAND.cell') as fhandle:
        struct_content = fhandle.read()

    func_lines = """
def modcell(cell_in):
    out = []
    for line in cell_in:
        out.append(line.replace(' C ', ' Si '))
    return out
"""
    task = AirssModcellTask(func='modcell', func_content=func_lines)
    fwm = Firework([task], spec={'struct_content': struct_content})
    wkm = Workflow([fwm])
    lpd = clean_launchpad
    lpd.add_wf(wkm)
    launch_rocket(lpd)

    action = lpd.get_launch_by_id(1).action
    new_content = action.update_spec['struct_content']
    assert ' Si ' in new_content
    assert ' C ' not in new_content

    # Check the operation of import mode
    task = AirssModcellTask(func=MODULE + '._modcell')
    fwm = Firework([task], spec={'struct_content': struct_content})
    wkm = Workflow([fwm])
    lpd.add_wf(wkm)
    launch_rocket(lpd)

    action = lpd.get_launch_by_id(2).action
    new_content2 = action.update_spec['struct_content']
    assert new_content == new_content2

    # Test operation of file passing
    struct_name = 'C2-42'
    with open(struct_name + '.cell', 'w') as fhandle:
        fhandle.write(struct_content)

    task = AirssModcellTask(func='modcell', func_content=func_lines)
    # In this case we only pass struct_name
    fwm = Firework([task], spec={'struct_name': struct_name})
    wkm = Workflow([fwm])
    lpd.add_wf(wkm)
    launch_rocket(lpd)

    with open(struct_name + '.cell') as fhandle:
        new_content3 = fhandle.read()

    action = lpd.get_launch_by_id(3).action
    assert not action.update_spec
    assert new_content == new_content3


def test_data_transfer(clean_launchpad, temp_workdir):
    """Test data tansfer task"""
    from disp.fws.tasks import AirssDataTransferTask
    from disp.fws.utils import FWPathManager
    task = AirssDataTransferTask(base_path=temp_workdir)
    fwt = Firework(
        [task],
        spec={
            'struct_name': 'C2-TEST',
            'project_name': 'tests/c2/run1',
            'seed_name': 'C2',
        })
    wkm = Workflow([fwt])
    clean_launchpad.add_wf(wkm)

    # Create the files
    touch = lambda x: (Path(temp_workdir) / x).touch()
    touch('C2-TEST.res')
    touch('C2.cell')
    touch('C2-TEST.castep')
    touch('C2-TEST.cell')
    touch('C2-TEST-out.cell')

    launch_rocket(clean_launchpad)

    fman = FWPathManager(temp_workdir)
    ftmp = fman.get_project_path('tests/c2/run1')
    assert (ftmp / 'C2-TEST.res').is_file()
    assert (ftmp / 'C2.cell').is_file()

    # Test the keep mode
    task = AirssDataTransferTask(base_path=temp_workdir,
                                 keep=True,
                                 additional_types=['.castep'])
    fwt = Firework([task],
                   spec={
                       'struct_name': 'C2-TEST',
                       'project_name': 'tests/c2/run2'
                   })
    wkm = Workflow([fwt])
    clean_launchpad.add_wf(wkm)
    launch_rocket(clean_launchpad)

    ftmp = fman.get_project_path('tests/c2/run2')

    assert (ftmp / 'C2-TEST.castep').is_file()
    assert (ftmp / 'C2-TEST_data.tar.gz').is_file()
    with tarfile.open(ftmp / 'C2-TEST_data.tar.gz', mode='r:gz') as archive:
        objs = archive.getmembers()
        assert len(objs) == 5

def test_insufficient_time(clean_launchpad, temp_workdir, get_data_dir):
    """Test the buildcell task"""
    del temp_workdir
    with open(get_data_dir('pp3_relax') / 'Al.cell') as fhandle:
        struct_content = fhandle.read()

    with open(get_data_dir('pp3_relax') / 'Al.pp') as fhandle:
        param_content = fhandle.read()

    # Only 10s left, but gulp needs 20 seconds
    Dummy.DEFAULT_REMAINING_TIME = 20
    AirssPp3RelaxTask.MINIMUM_RUN_TIME = 20
    AirssPp3RelaxTask.SHCEUDLER_TIME_OFFSET = 10

    btask = AirssPp3RelaxTask(
        param_content=param_content,
        cycles=100,
        executable='pp3',
    )
    # project_name = 'TEST/C2'
    fwk = Firework(
        [btask],
        spec={
            'struct_name': 'Al-TEST',
            'struct_content': struct_content,
            'seed_name': 'Al',
            'pressure': 100,
        })

    wkf = Workflow([fwk])
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd)
    action = lpd.get_launch_by_id(1).action

    assert action.stored_data[
        'relax_status'] == RelaxOutcome.INSUFFICIENT_TIME.name
    assert action.stored_data['_insufficient_time_left'] is True
    Dummy.DEFAULT_REMAINING_TIME = 9999


def test_record_upload(temp_workdir, clean_launchpad, new_db, datapath):
    """Test the record upload task"""

    seed_name = 'C2'
    project_name = 'test/C2'
    struct_name = 'C2-TEST-1'
    touch = lambda x: (Path(temp_workdir) / x).touch()
    for name in [
            seed_name + '.cell', struct_name + '.cell', struct_name + '.res'
    ]:
        touch(name)
    spec = {
        'struct_name': struct_name,
        'project_name': project_name,
        'seed_name': seed_name,
        'db_file': str(datapath / 'disp_db.yaml')
    }

    sdb = new_db

    task = DbRecordTask(include_param=False)
    clean_launchpad.add_wf(Firework([task], spec=spec))
    launch_rocket(clean_launchpad)

    assert len(sdb.retrieve_project(project_name)) == 1

    Path(temp_workdir / (seed_name + '.cell')).unlink()
    spec = {
        'struct_name': 'C2-TEST-2',
        'project_name': project_name,
        'seed_name': seed_name,
        'seed_content': 'THIS IS A SEED',
        'db_file': str(datapath / 'disp_db.yaml')
    }
    touch('C2-TEST-2.res')

    task = DbRecordTask(include_param=False)
    clean_launchpad.add_wf(Firework([task], spec=spec))
    launch_rocket(clean_launchpad)
    results = sdb.retrieve_project(
        project_name,
        include_seed=True,
        additional_filters={'struct_name': 'C2-TEST-2'})
    assert results[0].seed_file


@need_pp3
def test_upload_record_task(clean_launchpad, temp_workdir, get_data_dir,
                            new_db, datapath):
    """Test the buildcell task followed by gulp, packaged in the same FW"""

    with open(get_data_dir('pp3_relax') / 'Al.cell') as fhandle:
        seed_content = fhandle.read()

    with open(get_data_dir('pp3_relax') / 'Al.pp') as fhandle:
        param_content = fhandle.read()

    btask = AirssBuildcellTask(seed_content=seed_content,
                               seed_name='Al',
                               store_content=False,
                               project_name='TEST/Al')
    rtask = AirssPp3RelaxTask(
        param_content=param_content,
        cycles=100,
        executable='pp3',
    )
    db_file = str(datapath / 'disp_db.yaml')
    upload_task = DbRecordTask(db_file=db_file)

    fwb = Firework([btask, rtask, upload_task])
    wkf = Workflow([fwb])
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd, pdb_on_exception=True)

    assert len(list(temp_workdir.glob('Al-*.res'))) == 1
    results = new_db.retrieve_project(project_name='TEST/Al',
                                      include_seed=True,
                                      include_param=True)
    assert len(results) == 1


@need_castep
def test_castep_relax_task(clean_launchpad, temp_workdir, get_data_dir):
    """Test the buildcell task"""
    with open(get_data_dir('castep_relax') / 'C2-RAND.cell') as fhandle:
        struct_content = fhandle.read()

    with open(get_data_dir('castep_relax') / 'C2-RAND.param') as fhandle:
        param_content = fhandle.read()

    btask = AirssCastepRelaxTask(
        param_content=param_content,
        cycles=100,
        executable='mpirun -np 2 castep.mpi',
    )
    # project_name = 'TEST/C2'
    fwk = Firework(
        [btask],
        spec={
            'struct_name': 'C2-TEST',
            'struct_content': struct_content,
            'seed_name': 'C2',
            'pressure': 100,
        })

    wkf = Workflow([fwk])
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd)

    assert Path('C2-TEST.castep').is_file()
    assert len(list(temp_workdir.glob('C2-TEST.res'))) == 1
    assert lpd.get_launch_by_id(
        1).action.stored_data['relax_status'] == RelaxOutcome.FINISHED.name


@need_castep
def test_castep_code_selection(clean_launchpad, temp_workdir, get_data_dir):
    """Test selecting CASTEP worker"""

    with open(get_data_dir('castep_relax') / 'C2-RAND.cell') as fhandle:
        struct_content = fhandle.read()

    with open(get_data_dir('castep_relax') / 'C2-RAND.param') as fhandle:
        param_content = fhandle.read()

    # This should fail because the required code 1911 does not exist
    btask = AirssCastepRelaxTask(
        param_content=param_content,
        cycles=100,
        executable='mpirun -np 2 castep.mpi',
        castep_code='1911',
    )
    # project_name = 'TEST/C2'
    fwk = Firework(
        [btask],
        spec={
            'struct_name': 'C2-TEST',
            'struct_content': struct_content,
            'seed_name': 'C2',
            'pressure': 100,
        })

    wkf = Workflow([fwk])
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd)

    assert not Path('C2-TEST.castep').is_file()

    # Make temporary CASTEP
    subprocess.run('ln -s `which castep.mpi` `pwd`/castep',
                   shell=True,
                   check=True)
    pwd = Path().resolve()
    worker = FWorker(
        env={'castep_codes': {
            '1911': f'mpirun -np 2 {pwd}/castep'
        }})
    wkf = Workflow([fwk])
    lpd.add_wf(wkf)
    launch_rocket(lpd, fworker=worker)

    assert Path('C2-TEST.castep').is_file()
    assert len(list(temp_workdir.glob('C2-TEST.res'))) == 1
    assert lpd.get_launch_by_id(
        2).action.stored_data['relax_status'] == RelaxOutcome.FINISHED.name


def test_castep_relax_script(clean_launchpad, temp_workdir, get_data_dir):
    """Test the buildcell task"""
    with open(get_data_dir('castep_relax') / 'C2-RAND.cell') as fhandle:
        struct_content = fhandle.read()

    with open(get_data_dir('castep_relax') / 'C2-RAND.param') as fhandle:
        param_content = fhandle.read()
    spec = {
        'struct_name': 'C2-TEST',
        'struct_content': struct_content,
        'seed_name': 'C2',
        'pressure': 100,
        '_fw_env': {
            'castep_relax_prepend_command': 'module load essential'
        }
    }
    btask = AirssCastepRelaxTask(
        param_content=param_content,
        cycles=100,
        executable='mpirun -np 2 castep.mpi',
    )
    btask._init_parameters(spec)
    assert btask.prepend_command == 'module load essential'
    assert btask._get_cmd() == [
        'castep_relax', '100', 'mpirun -np 2 castep.mpi', '0', '0', 'C2-TEST'
    ]

    # Prepare the run script
    btask._prepare_run_script(btask._get_cmd(), 'module load essential',
                              ['module unload essential', 'echo all good'])
    content = Path(btask.run_script_name).read_text().split('\n')
    assert content[0] == btask.shebang
    assert content[2] == 'module load essential'
    assert content[3] == 'echo Current PATH: $PATH'
    assert content[
        4] == "'castep_relax' '100' 'mpirun -np 2 castep.mpi' '0' '0' 'C2-TEST'"


@need_castep
def test_castep_timeout(clean_db, clean_launchpad, temp_workdir, get_data_dir, datapath):
    """Test the buildcell task"""
    del temp_workdir

    with open(get_data_dir('castep_relax') / 'C2-RAND.cell') as fhandle:
        struct_content = fhandle.read()

    with open(get_data_dir('castep_relax') / 'C2-RAND.param') as fhandle:
        param_content = fhandle.read()

    # Only 10s left, but gulp needs 20 seconds
    Dummy.DEFAULT_REMAINING_TIME = 10
    AirssCastepRelaxTask.MINIMUM_RUN_TIME = 3
    AirssCastepRelaxTask.SHCEUDLER_TIME_OFFSET = 5

    btask = AirssCastepRelaxTask(
        param_content=param_content,
        cycles=100,
        executable='castep.mpi',
    )
    # project_name = 'TEST/C2'
    fwk = Firework(
        [btask],
        spec={
            'struct_name': 'C2-TEST',
            'struct_content': struct_content,
            'seed_name': 'C2',
            'pressure': 100,
            'db_file': str(datapath / 'disp_db.yaml'),
        })

    wkf = Workflow([fwk])
    lpd = clean_launchpad
    lpd.add_wf(wkf)
    launch_rocket(lpd)
    action = lpd.get_launch_by_id(1).action

    assert action.stored_data['relax_status'] == RelaxOutcome.TIMEDOUT.name
    Dummy.DEFAULT_REMAINING_TIME = 9999
    AirssCastepRelaxTask.MINIMUM_RUN_TIME = 600
    AirssCastepRelaxTask.SHCEUDLER_TIME_OFFSET = 60
