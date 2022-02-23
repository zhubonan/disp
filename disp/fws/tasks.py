"""
Module defining the FIRE tasks for AIRSS operations
"""
import tarfile
import sys
import os
import shutil
import subprocess
from pathlib import Path
import contextlib
from enum import Enum
import time
import filecmp
from uuid import uuid4

from fireworks.core.firework import FiretaskBase, FWAction, Firework
from fireworks.utilities.fw_utilities import get_fw_logger
from fireworks import explicit_serialize

from disp.scheduler import Scheduler
from disp.casteptools import (get_rand_cell_name, castep_geom_count,
                              castep_finish_ok, push_cell,
                              gulp_relax_finish_ok)
from disp.fws.utils import FWPathManager
from disp.database import DB_FILE, SearchDB, get_hash
from .utility_tasks import GzipDir

#pylint: disable=logging-format-interpolation, too-many-lines


class RelaxOutcome(Enum):
    """Outcome of a relaxation"""
    FINISHED = 0
    TIMEDOUT = 1
    ERRORED = 2
    UNDETERMINED = 3
    CYCLE_EXCEEDED = 4
    INSUFFICIENT_TIME = 5


@explicit_serialize
class AirssValidateTask(FiretaskBase):
    """
    Task for validating the instuallation of AIRSS
    """

    optional_params = ['additional_exes']
    required_exes = ['buildcell', 'castep_relax', 'castep2res']

    logger = get_fw_logger(__name__, l_dir=None, stream_level='INFO')

    def run_task(self, fw_spec):
        """Validate the avaliability of AIRSS toolkits"""

        exes_to_check = self.get('additional_exes', []) + self.required_exes
        not_found = []
        for exe_name in exes_to_check:
            try:
                subprocess.run(['which', exe_name], check=True)
            except subprocess.CalledProcessError:
                not_found.append(exe_name)

        if not_found:
            self.logger.error((
                'AIRSS installation incomplete, these executables are not found:\n'
                '{}'.format(not_found)))
            return FWAction(defuse_children=True)
        return None


@explicit_serialize
class AirssBuildcellTask(FiretaskBase):
    """
    Task for launching buildcell for generating random structures

    Required inputs:

    - seed_content: Content of the seed file
    - seed_name: Name for the seed file
    - project_name: Name of the project

    Optional inputs:

    - store_content: Whether store the generated structure in spec and action.
      Default to True. May be set to False if this task is packaged with
      relaxation within the same Firework.
    - deposit_init_structure: Store the initial structure to the database or not. Default to False.
    - keep_seed: Whether write out the seed to the file system. Default to True.
    """
    # _fw_name = 'BuildcellTask'
    required_params = ['seed_content', 'seed_name', 'project_name']
    optional_params = [
        'upload', 'store_content', 'keep_seed', 'deposit_init_structure',
        'build_timeout'
    ]
    logger = get_fw_logger(__name__, l_dir=None, stream_level='INFO')

    def run_task(self, fw_spec):
        """
        Internal function for running buildcell
        """
        seed_name = self['seed_name']
        project_name = self['project_name']
        seed_content = self['seed_content']

        # Timeout default to 600 seconds
        build_timeout = self.get('build_timeout', 300)

        # Try to build the random structure with timeout
        self.logger.info('Start building a random structure...')
        attempt = 3
        while attempt > 0:
            try:
                proc = subprocess.Popen(
                    'buildcell',
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    universal_newlines=True,
                )
                stdout, stderr = proc.communicate(seed_content,
                                                  timeout=build_timeout)
            except subprocess.TimeoutExpired:
                attempt -= 1
            else:
                break

        if attempt <= 0:
            msg = 'Warning - random structure generation timedout'
            self.logger.error(msg)
            return FWAction(defuse_children=True, stored_data={'message': msg})

        self.logger.info('Random structure building completed')

        stdout = stdout.decode('utf-8') if isinstance(stdout,
                                                      bytes) else stdout
        stderr = stderr.decode('utf-8') if isinstance(stderr,
                                                      bytes) else stderr

        cell_name = get_rand_cell_name(self['seed_name'])
        struct_name = cell_name.replace('.cell', '')

        # Write down the seed file, if requested
        if self.get('keep_seed', True):
            Path(seed_name + '.cell').write_text(seed_content)

        # Write down the structure file
        with open(cell_name, 'w') as fhandle:
            fhandle.write(stdout)

        # Write the original, unrelaxed cell structure as '-orig.cell'
        with open(struct_name + '-orig' + '.cell', 'w') as fhandle:
            fhandle.write(stdout)

        stored_data = {
            'struct_name': struct_name,
        }
        update_spec = {
            'project_name': project_name,
            'seed_name': seed_name,
            'struct_name': struct_name,
            'seed_hash': get_hash(seed_content)
        }
        # Default is to store the content to the fireworks, this allows
        # the relaxation to be in another Firework
        if self.get('store_content', True):
            update_spec.update({'struct_content': stdout})

        if self.get('deposit_init_structure', False):
            db_file = fw_spec.get('db_file', DB_FILE)
            sdb = SearchDB.from_db_file(db_file)
            try:
                fw_id = self.fw_id
            except AttributeError:
                fw_id = None

            task_uuid = fw_spec.get('task_uuid', uuid4().hex)
            update_spec['task_uuid'] = task_uuid

            sdb.set_identity(fw_id, task_uuid)
            sdb.insert_initial_structure(
                struct_content=stdout,
                project_name=project_name,
                struct_name=struct_name,
                seed_name=seed_name,
                seed_content=seed_content,
            )
            self.logger.info(f'Initial structure deposited {struct_name}')

        return FWAction(stored_data=stored_data, update_spec=update_spec)


@explicit_serialize
class AirssModcellTask(FiretaskBase):
    """
    Task for modifying the generated cell

    Use a function to modify the the struct_content field in the spec.
    This allows custom post-generation modifications.
    The function will receive a list of the lines parsed from `struct_content`
    , and it should return a list of processed lines.

    If `func_content` field exists, we import the function from that defined
    there. This file will be written to the disk and then the `func` is imported
    from there.
    """

    # _fw_name = 'ModcellTask'
    required_params = ['func']
    optional_params = ['func_content']
    logger = get_fw_logger(__name__, l_dir=None, stream_level='INFO')

    def run_task(self, fw_spec):
        # Importing the function
        func_content = self.get('func_content', None)
        # If given the content, we write it to the disk and import it
        if func_content:
            with open('modfunc.py', 'w') as fhandle:
                fhandle.write(func_content)
            sys.path.append(os.getcwd())
            funcname = self['func']
            mod = __import__('modfunc', globals(), locals(), [str(funcname)],
                             0)
            func = getattr(mod, funcname)
            sys.path.pop()
        # otherwise, use a existing function from somewhere
        else:
            toks = self['func'].rsplit('.', 1)
            modname, funcname = toks
            mod = __import__(modname, globals(), locals(), [str(funcname)], 0)
            func = getattr(mod, funcname)

        incell = fw_spec.get('struct_content', None)
        # If the content does not exists, read from file
        file_mode = False
        if incell is None:
            file_mode = True
            with open(fw_spec['struct_name'] + '.cell') as fhandle:
                incell = fhandle.read()

        outcell = func(incell.split('\n'))
        outcell = '\n'.join(outcell) + '\n'
        if file_mode:
            # If the original communication is from file, we keep using files
            with open(fw_spec['struct_name'] + '.cell', 'w') as fhandle:
                fhandle.write(outcell)
            out = None
        else:
            out = FWAction(update_spec={'struct_content': outcell})

        self.logger.info('Cell structure modified')
        return out


@explicit_serialize
class AirssCastepRelaxTask(FiretaskBase):  # pylint: disable=too-many-instance-attributes
    """
    Task for running the `castep_relax` script

    The executable to be used for CASTEP is worked our in the following steps:

    - The `executable` in as defined
    - Look for `castep_executable` under env part of the worker file
    - Look for specific code under `castep_codes` dictionary stored in under `env` of the worker file.

    Required parameters in the spec:

    - struct_name: name of the cell file to be used
    - seed_name: name of the original seed structure

    Optional parameters in the spec:

    - struct_content: content of the cell file containing the structure
    - timeout: timeout for the call to castep_relax
    - executable: Name of the executable to be passed to `castep_relax`.
      Note that this may include the mpirun -np <> part. Overrides the
      immediate parameters
    - pressure: the pressure under with the relaxation needs to performed.
      Not implemented for `castep_relax` at the moment
    - launch_count: Counter for the number of launches
    - launch_limit: Limit of the number of launches, defaults to 5
    - prepend_command: A list of commands to be run before the relaxation, such as loading required modules.
      Can also be defined at a per-worker basis using `castep_relax_prepend_command` under the `env` field.
    - append_command: A list of commands to be run after the relaxation, such as cleaning certain files.
      Can also be defined at a per-worker basis using `castep_relax_append_command` under the `env` field.

    Required parameter for this task:

    - cycles: Number of cycles for the relaxation
    - param_content: Content for the param file
    - executable: Name of the executable to be passed to `castep_relax`.
      Note that this may include the mpirun -np <> part. If a environmental
      variable `MPI_LAUNCH_CMD` exists. The part before `castep` will be
      replaced with it.

    """

    # _fw_name = 'CastepRelaxTask'
    required_params = ['cycles', 'param_content', 'executable']
    optional_params = [
        'minimum_run_time', 'prepend_command', 'append_command', 'castep_code'
    ]
    MINIMUM_RUN_TIME = 600
    logger = get_fw_logger(__name__, l_dir=None, stream_level='INFO')
    SHCEUDLER_TIME_OFFSET = 60
    PRIORITY_OFFSET = {'insufficient_time': 15, 'continuation': 10}
    shebang = '#!/bin/bash -l'
    run_script_name = 'jobscript.sh'
    code_string = 'castep_relax'  # Identifier for which code is running
    _param_suffix = '.param'

    # pylint: disable=attribute-defined-outside-init
    def _init_parameters(self, fw_spec):
        """Initialise the internal parameters"""
        # Required parameters
        fw_env = fw_spec.get('_fw_env', {})
        self.cycles = self['cycles']
        self.param_content = self['param_content']
        self.minimum_run_time = self.get('minimum_run_time',
                                         self.MINIMUM_RUN_TIME)
        self.struct_name = fw_spec['struct_name']
        self.project_name = fw_spec.get('project_name')
        self.seed_name = fw_spec.get('seed_name')
        self.struct_content = fw_spec.get('struct_content')

        # Specific executable
        self.executable = self['executable']
        self.executable = fw_spec.get('executable', self.executable)

        # Any specific code defined?
        self.castep_code = self.get('castep_code', 'default')

        # Check the _fw_env for the executable - this takes the precedence
        self.executable = fw_env.get('castep_executable', self.executable)

        # Check the _fw_env for code-specific executable path - this takes the precedence
        codes = fw_env.get('castep_codes', {})
        if self.castep_code != 'default':
            if self.castep_code in codes:
                self.executable = codes[self.castep_code]
            else:
                raise RuntimeError(
                    f"Required '{self.castep_code}' code is not found in the worker environment!"
                )

        # Allow worker-based customisation for the shebang
        self.shebang = fw_env.get('castep_jobscript_shebang', self.shebang)

        self.pressure = fw_spec.get('pressure', 0.0)

        self.prepend_command = self.get(
            'prepend_command',
            fw_env.get(f'{self.code_string}_prepend_command'))
        self.append_command = self.get(
            'append_command', fw_env.get(f'{self.code_string}_append_command'))

        # Increment the launch_count in the spec
        self.nlaunches = fw_spec.get('launch_count', 0) + 1
        self.launch_limit = fw_spec.get('launch_limit', 5)
        self.base_priority = fw_spec.get('_priority', 0)

        # Placeholder for the SearchDB instance
        self._sdb = None

        # Set the timeout
        timeout = fw_spec.get('timeout')
        if timeout is None:
            self.timeout = self._get_timeout()
        else:
            self.timeout = timeout

    def _prepare_inputs(self, struct_name):
        """Write the input files"""
        cell_name = struct_name + '.cell'
        param_name = struct_name + self._param_suffix
        # Only write if there is no file
        if not Path(cell_name).is_file():
            with open(cell_name, 'w') as fhandle:
                fhandle.write(self.struct_content)

        if not Path(param_name).is_file():
            with open(param_name, 'w') as fhandle:
                fhandle.write(self.param_content)

    def _get_cmd(self):
        """Construct the command line arguments"""
        exe = self.executable

        mpicmd = self.get_mpi_launch_cmd()
        if mpicmd:
            # If there is a MPI_LAUNCH_CMD in the ENV
            # we replace the original MPI launcher part with it
            tokens = exe.split()
            istart = None
            # Locate the part for CASTEP executabe path
            for idx, token in enumerate(tokens):
                if 'castep' in token:
                    istart = idx
                    break
            if istart is None:
                raise RuntimeError(
                    f'CASTEP executable cannot be detected in {exe}')

            # Take everything after castep after the launcher command
            exe = '{} {}'.format(mpicmd, ' '.join(tokens[istart:]))

        cmd = [
            'castep_relax', '{:d}'.format(self.cycles), exe, '0', '0',
            self.struct_name
        ]
        return cmd

    def _handle_relax_finshed(self):
        """Handle successful relaxation"""

        self.logger.info('Relaxation finished')
        self._save_res()
        return FWAction(
            stored_data={
                'relax_status': RelaxOutcome.FINISHED.name,
                'struct_name': self.struct_name,
                'seed_name': self.seed_name
            })

    def _handle_too_few_cycle_left(self, rem_cycles):
        """Handle the case where there are too few cycles left"""

        self.logger.info(
            f'Only have {rem_cycles} to perform, relaxation terminated')

        # Detete the '-out.cell', otherwise castep2res will pick it up and use it
        # as the structure
        if os.path.isfile(self.struct_name + '-out.cell'):
            os.remove(self.struct_name + '-out.cell')
        self._save_res()
        return FWAction(
            stored_data={
                'relax_status': RelaxOutcome.CYCLE_EXCEEDED.name,
                'struct_name': self.struct_name,
                'seed_name': self.seed_name,
            })

    def run_task(self, fw_spec):
        """Run the task"""
        self._init_parameters(fw_spec)
        struct_name = self.struct_name

        self._prepare_inputs(self.struct_name)
        cmd = self._get_cmd()

        # Run CASTEP relax, leave one minute for cleaning up
        actual_timeout = self.timeout - self.SHCEUDLER_TIME_OFFSET
        self.logger.info(f'Setting timeout to: {actual_timeout} seconds')

        # Check if we have sufficient time for this run, if not we do not do the relaxation
        if actual_timeout < self.minimum_run_time:
            # Sleep for 10 seconds
            slp = 10 if actual_timeout > 10 else 1
            time.sleep(slp)
            return self._handle_insufficient_run_time(fw_spec)

        # Create symbolic links for running calculations
        base_path = fw_spec.get('base_path', None)
        run_files = [
            self.struct_name + suffix
            for suffix in ['.cell', '.param', '.castep']
        ]

        # Retrieve dot CASTEP if this is not the first relaxation
        if self.nlaunches > 1:
            self._retrieve_dot_castep()
            self._delete_dot_castep()

        with create_symlinks(base_path, self.project_name, run_files):
            relax_outcome = self._run_relax(
                self.struct_name,
                cmd,
                actual_timeout,
                prepend_command=self.prepend_command,
                append_command=self.append_command)

        if relax_outcome is RelaxOutcome.FINISHED:
            return self._handle_relax_finshed()

        if relax_outcome is RelaxOutcome.TIMEDOUT:
            # Finished with error - now we try to recover it
            self.logger.info('Relaxation timed out: taking the last geometry')

            # Do not add new jobs if there are less than 20 cycles
            completed_cycles = castep_geom_count(struct_name + '.castep')
            remining_cycles = self.cycles - completed_cycles
            if (self.cycles != 0) and (remining_cycles < 20):
                return self._handle_too_few_cycle_left(
                    rem_cycles=remining_cycles)

            self.logger.info('Adding continuation fireworks')
            return self._handle_relax_timeout(fw_spec)

        # The relaxation is errorred
        return self._handle_relax_error(fw_spec)

    def _handle_insufficient_run_time(self, fw_spec):
        """
        Handle the problem there are insufficient run time

        In this case we just resubmit the same job.
        A potential problem is that his job may be picked up by the
        same worker again, so it will keep bouncing. We should make
        sure the worker's timeout is sufficiently less than the actual
        remaining time...

        TODO: Make the worker gracefully terminate if it encounters such
        job. This will involve changing the fireworks code.
        """
        # pylint: disable=cyclic-import, import-outside-toplevel
        from disp.fws.works import RelaxFW

        # We must inlclude the structure, as the restarted firework may be on
        # a different machine...
        struct_content = Path(self.struct_name + '.cell').read_text()

        # Create the spec for the Child workflow
        # Do not take any _keys
        new_spec = filter_spec(fw_spec)
        new_spec['launch_count'] = self.nlaunches

        # Here I set a high prority case of the insufficient_time case
        # So if I am in a loop, it will get picked up first next time....
        new_spec['_priority'] = self.base_priority + self.PRIORITY_OFFSET[
            'insufficient_time']
        new_spec['struct_content'] = struct_content

        new_fw = RelaxFW(project_name=fw_spec.get('project_name'),
                         struct_name=self.struct_name,
                         struct_content=struct_content,
                         param_content=self.param_content,
                         executable=self.executable,
                         cycles=self.cycles,
                         seed_name=self.seed_name,
                         existing_spec=new_spec)

        detours = [new_fw]

        stored_data = {
            'relax_status': RelaxOutcome.INSUFFICIENT_TIME.name,
            'struct_name': self.struct_name,
            'seed_name': self.seed_name,
            '_insufficient_time_left': True,
        }
        self.logger.warning(
            'Insufficent run time detected. This should never happen if the timeout is set properly for the worker....'
        )

        return FWAction(detours=detours, stored_data=stored_data)

    def _handle_relax_timeout(self, fw_spec):
        """Handle the case where relaxation is time out"""
        # Take the last relaxation, mind that the precision in the .castep file is lower
        # pylint: disable=cyclic-import, import-outside-toplevel
        from disp.fws.works import RelaxFW

        struct_name = self.struct_name
        cell_content = Path(f'{struct_name}.cell').read_text()
        # Check if spin polarisation is enabled in the input structure file
        has_spin = 'SPIN=' in cell_content

        if has_spin:
            # In this case we cannot use the last structure from CASTEP as it does not
            # contain the project spins from the population analysis. Hence, we simply
            # use the last input structure as the content. This implies that all progress
            # since the last DFT launch are lost
            struct_content = cell_content

        else:
            subprocess.run(
                f'cabal castep cell < {struct_name}.castep > cell_update.cell',
                shell=True,
                check=True)

            # Upload the incomplete CASTEP file
            self._upload_dot_castep()

            # Construct the new cell content
            shutil.copy(struct_name + '.cell', struct_name + '-partial.cell')
            push_cell('cell_update.cell', struct_name + '-partial.cell')
            with open(struct_name + '-partial.cell') as fhandle:
                struct_content = fhandle.read()

        # Update the cycles limit - subtract away the computed cycles
        # zero is the special case - castep_relax does not restart but just
        # perform whatever that is specified in the *.param file
        if self.cycles != 0:
            ncycles = castep_geom_count(struct_name + '.castep')
            remining_cycles = self.cycles - ncycles
        else:
            remining_cycles = 0

        # Create the spec for the Child workflow
        new_spec = filter_spec(fw_spec)
        new_spec['struct_content'] = struct_content
        # Update the number of existing launches
        new_spec['launch_count'] = self.nlaunches
        new_spec['_priority'] = self.base_priority + self.PRIORITY_OFFSET[
            'continuation']
        # Remove the uuid field from the children Firework
        new_spec.pop('task_uuid', None)

        new_fw = RelaxFW(project_name=self.project_name,
                         struct_name=self.struct_name,
                         struct_content=struct_content,
                         param_content=self.param_content,
                         executable=self.executable,
                         cycles=remining_cycles,
                         seed_name=self.seed_name,
                         existing_spec=new_spec)

        stored_data = {
            'relax_status': RelaxOutcome.TIMEDOUT.name,
            'struct_name': self.struct_name,
            'seed_name': self.seed_name,
        }

        detours = None
        if new_spec['launch_count'] < self.launch_limit:
            detours = [new_fw]

        return FWAction(stored_data=stored_data, detours=detours)

    def _handle_relax_error(self, fw_spec):
        """Handle relaxation error - store the error status in spec"""
        _ = fw_spec
        relax_status = RelaxOutcome.ERRORED.name
        stored_data = {
            'relax_status': relax_status,
            'struct_name': self.struct_name,
            'seed_name': self.seed_name,
        }
        self.logger.warning('Relaxation errored.')
        return FWAction(stored_data=stored_data,
                        update_spec={'relax_status': relax_status})

    def _get_timeout(self):
        """
        Get the timeout in seconds

        This should be get from the scheduler
        """
        scheduler = Scheduler.get_scheduler()
        self.logger.info(f'Using scheduler interface {scheduler}')
        timeout = scheduler.get_remaining_seconds()
        self.logger.info(f'Obtained timeout from scheudler {timeout}')
        return timeout

    def _save_res(self):  # pylint: disable=no-self-use
        """Save the res file"""
        proc = subprocess.run(['castep2res', self.struct_name],
                              capture_output=True,
                              universal_newlines=True,
                              check=True)
        with open(self.struct_name + '.res', 'w') as fhandle:
            fhandle.write(proc.stdout)

    @property
    def search_db(self):
        if self._sdb is None:
            self._sdb = SearchDB.from_db_file(DB_FILE)
        return self._sdb

    def close_search_db(self):
        """Close the connection of the SearchDB instance"""
        if self._sdb is None:
            return
        self._sdb.connection.close()

    def _upload_dot_castep(self):
        """Upload the .castep file"""
        try:
            self.search_db.upload_dot_castep(self.struct_name, self.seed_name,
                                             self.project_name)
            self.logger.info('Uploaded .castep file to the database')
            return True
        except FileExistsError:
            self.logger.error(
                'Cannot upload the .castep to the database - file exists')
            return False

    def _retrieve_dot_castep(self):
        """Retrieve the .castep file"""
        try:
            self.search_db.retrieve_dot_castep(self.struct_name,
                                               self.seed_name,
                                               self.project_name)
            self.logger.info('Retrieved .castep file to the database')
            return True
        except FileNotFoundError:
            self.logger.error(
                'the .castep from the previous calculation cannot be found.')
            return False

    def _delete_dot_castep(self):
        """Retrieve the .castep file"""
        self.logger.info('Deleted .castep file in the database')
        self.search_db.delete_dot_castep(self.struct_name, self.seed_name,
                                         self.project_name)

    def _run_relax(self,
                   struct_name,
                   cmd,
                   timeout,
                   prepend_command=None,
                   append_command=None):
        """Run the 'castep_relax' program"""
        outcome = RelaxOutcome.UNDETERMINED

        self.logger.info(f'Starting CASTEP run with command: {cmd}')
        self._prepare_run_script(cmd, prepend_command, append_command)
        with transiant_file('.realx_stdout', mode='w+') as tmpout:
            try:
                subprocess.run(f'./{self.run_script_name}',
                               timeout=timeout,
                               check=True,
                               universal_newlines=True,
                               stdout=tmpout)
            except subprocess.TimeoutExpired:
                outcome = RelaxOutcome.TIMEDOUT
                self.logger.info('Relaxation timed out')
            else:
                tmpout.seek(0)
                stdout_content = tmpout.read()
                if 'Pressure' in stdout_content and castep_finish_ok(
                        struct_name + '.castep'):
                    outcome = RelaxOutcome.FINISHED
                else:
                    outcome = RelaxOutcome.ERRORED

        return outcome

    def _prepare_run_script(self,
                            cmd,
                            prepend_command=None,
                            append_command=None):
        """
        Prepare the run script in the current working directory for running CASTEP

        The use of script is necessary as it allows us to set the module environments.
        """
        template = """{shebang}

{prepend}
echo Current PATH: $PATH
{cmd}
{append}

"""
        if isinstance(prepend_command, list):
            prepend_command = '\n'.join(prepend_command)
        if isinstance(append_command, list):
            append_command = '\n'.join(append_command)

        # If unset - make they an emtpy string
        prepend_command = '' if prepend_command is None else prepend_command
        append_command = '' if append_command is None else append_command

        string = template.format(
            shebang=self.shebang,
            prepend=prepend_command,
            # Escate the commands
            cmd=' '.join(map(lambda x: '\'' + x + '\'', cmd)),
            append=append_command)
        script_path = Path(f'{self.run_script_name}')
        # Write the script content
        script_path.write_text(string)
        # Set the permission
        subprocess.run(f'chmod +x {self.run_script_name}',
                       shell=True,
                       check=True)

    def get_mpi_launch_cmd(self):  # pylint: disable=no-self-use
        """Get the launch command for MPI"""
        mpicmd = os.environ.get('MPI_LAUNCH_CMD', '')
        return mpicmd


@explicit_serialize
class AirssGulpRelaxTask(AirssCastepRelaxTask):
    """
    Relaxation using GULP instead of CASTEP

    Invoke `gulp_relax` to perform relaxation instead of using CASTEP
    otherwise it is mostly the same.
    For now, it is assumed that GULP relaxation will always finish,
    if it does not, we simply try again...

    Optional parameters:
    - prepend_command: A list of commands to be run before the relaxation, such as loading required modules.
      Can also be defined at a per-worker basis using `gulp_relax_prepend_command` under the `env` field.
    - append_command: A list of commands to be run after the relaxation, such as cleaning certain files.
      Can also be defined at a per-worker basis using `gulp_relax_append_command` under the `env` field.

    """

    #_fw_name = 'GulpRelaxTask'
    required_params = ['cycles', 'param_content', 'executable']
    optional_params = ['minimum_run_time', 'prepend_command', 'append_command']
    MINIMUM_RUN_TIME = 10
    SHCEUDLER_TIME_OFFSET = 10
    logger = get_fw_logger(__name__, l_dir=None, stream_level='INFO')
    code_string = 'gulp_relax'  # Identifier for which code is running
    _param_suffix = '.lib'

    def _get_cmd(self):
        """Construct the command line arguments"""
        # NOTE: this assumes that we are working with a periodic system and
        # zero pressure
        cmd = [
            'gulp_relax', self.executable, '0',
            str(self.pressure), self.struct_name
        ]
        return cmd

    def _run_relax(self,
                   struct_name,
                   cmd,
                   timeout,
                   prepend_command=None,
                   append_command=None):
        """Run the 'gulp_relax' program"""
        outcome = RelaxOutcome.UNDETERMINED
        self._prepare_run_script(cmd, prepend_command, append_command)
        with transiant_file('.relax_stdout', mode='w+') as outtmp:
            try:
                subprocess.run(f'./{self.run_script_name}',
                               timeout=timeout,
                               check=True,
                               universal_newlines=True,
                               stdout=outtmp)

            except subprocess.TimeoutExpired:
                outcome = RelaxOutcome.TIMEDOUT
                self.logger.info('Relaxation timed out')
            else:
                outtmp.seek(0)
                content = outtmp.read()
                if gulp_relax_finish_ok(struct_name +
                                        '.castep') and 'Volume' in content:
                    outcome = RelaxOutcome.FINISHED
                else:
                    outcome = RelaxOutcome.ERRORED

        return outcome

    def _handle_relax_timeout(self, fw_spec):
        """
        Handle the case where relaxation is timedout, this is a simple retry"""
        new_task = self.__class__(param_content=self['param_content'],
                                      cycles=self.cycles,
                                      executable=self['executable'])
        transport_task = AirssDataTransferTask()

        # Create the spec for the Child workflow
        new_spec = filter_spec(fw_spec)
        new_spec['launch_count'] = self.nlaunches

        stored_data = {
            'relax_status': RelaxOutcome.TIMEDOUT.name,
            'struct_name': self.struct_name,
            'seed_name': self.seed_name,
        }

        detours = None
        if new_spec['launch_count'] < self.launch_limit:
            tasks = [new_task, transport_task]

            if fw_spec.get('record_db') is True:
                tasks.append(DbRecordTask())
            if fw_spec.get('gzip_folder') is True:
                tasks.append(GzipDir())

            detours = [Firework(tasks, spec=new_spec, name=self.__class__.name + 'Restart')]

        return FWAction(stored_data=stored_data, detours=detours)


@explicit_serialize
class AirssPp3RelaxTask(AirssGulpRelaxTask):
    """
    Relaxation using pp3

    Invoke `pp3_relax` to perform relaxation using pair potentials
    It is assumed that pp3 relaxation will always finish

    Optional parameters:
    - prepend_command: A list of commands to be run before the relaxation, such as loading required modules.
      Can also be defined at a per-worker basis using `gulp_relax_prepend_command` under the `env` field.
    - append_command: A list of commands to be run after the relaxation, such as cleaning certain files.
      Can also be defined at a per-worker basis using `gulp_relax_append_command` under the `env` field.

    """

    #_fw_name = 'GulpRelaxTask'
    required_params = ['cycles', 'param_content', 'executable']
    optional_params = ['minimum_run_time', 'prepend_command', 'append_command']
    MINIMUM_RUN_TIME = 10
    SHCEUDLER_TIME_OFFSET = 10
    logger = get_fw_logger(__name__, l_dir=None, stream_level='INFO')
    code_string = 'pp3_relax'  # Identifier for which code is running
    _param_suffix = '.pp'

    def _get_cmd(self):
        """Construct the command line arguments"""
        # NOTE: this assumes that we are working with a periodic system and
        # zero pressure
        cmd = [
            'pp3_relax', self.executable, '0',
            str(self.pressure), self.struct_name
        ]
        return cmd


@explicit_serialize
class DbRecordTask(FiretaskBase):
    """
    Taks for storing a record to the database

    Insert a record into the database, includes the found structures and seed
    and the paramters.

    There must be the following keys in the spec: struct_name, project_name.
    The <struct_name>.res file must be present in the current working directory.

    """

    optional_params = ['db_file', 'include_param']
    default_params = {
        'db_file': DB_FILE,
        'include_param': False,
    }
    logger = get_fw_logger(__name__, l_dir=None, stream_level='INFO')

    # pylint: disable=attribute-defined-outside-init
    def _init_parameters(self, fw_spec):
        """Initialise the parameters"""
        self.db_file = DB_FILE
        self.include_param = False

        set_attributes(self, fw_spec, self.default_params)

    def run_task(self, fw_spec):
        """
        Save search results to the database

        Uses the information in fw_spec to read in the files and store them to
        the database defined under the 'db_file' entry.
        """

        self._init_parameters(fw_spec)
        struct_name = fw_spec['struct_name']
        seed_name = fw_spec.get('seed_name')
        seed_content = fw_spec.get('seed_content')
        seed_hash = fw_spec.get('seed_hash')

        try:
            res_content = Path(struct_name + '.res').read_text()
        except FileNotFoundError:
            self.logger.error('No res file found - aborting')
            return None

        if seed_name:
            if not seed_content and Path(seed_name + '.cell').exists():
                seed_content = Path(seed_name + '.cell').read_text()

        if self.include_param:
            param_content = fw_spec.get('param_content')
        else:
            param_content = None

        sdb = SearchDB.from_db_file(self.db_file)

        # Try populate the fw_id field
        try:
            fw_id = self.fw_id
        except AttributeError:
            fw_id = None
        # Take the UUID of this task
        task_uuid = fw_spec.get('task_uuid', uuid4().hex)

        sdb.set_identity(fw_id, uuid=task_uuid)
        sdb.insert_search_record(
            project_name=fw_spec['project_name'],
            struct_name=struct_name,
            res_content=res_content,
            param_content=param_content,
            seed_name=seed_name,
            seed_hash=seed_hash,
            seed_content=seed_content,
        )
        self.logger.info(f'Deposited the relaxed structure of {struct_name}')
        return FWAction(update_spec={'task_uuid': task_uuid})


@explicit_serialize
class AirssDataTransferTask(FiretaskBase):
    """
    Task for transfering data to the repository

    The task is for transfering data generated in the search
    and save it to the directory as specified by the `project_name`
    in the spec.

    Optional parameters:

    - keep: Transfer all data to a separate directory
    - additional_types: Additional file types to be transferred
    - additional_files: Additional file names to be transferred
    - base_path: Alternative <BASE_PATH>

    All parameter can be override in `fw_spec`.
    """

    # _fw_name = 'DataTransferTask'
    optional_params = [
        'keep', 'additional_types', 'base_path', 'additional_files'
    ]

    DEFAULT_TYPES = ['.res', '-orig.cell']
    logger = get_fw_logger(__name__, l_dir=None, stream_level='INFO')

    def run_task(self, fw_spec):  # pylint: disable=too-many-branches
        """Transfer data"""

        base_path = self._get_param(fw_spec, 'base_path', None)
        fman = FWPathManager(base_path)

        pfolder = fman.get_project_path(fw_spec['project_name'])
        struct_name = fw_spec['struct_name']
        cwd = Path('.')

        types_to_transfer = self.DEFAULT_TYPES + self._get_param(
            fw_spec, 'additional_types', [])
        for suffix in types_to_transfer:
            for file in cwd.glob(struct_name + suffix):
                # Note that glob gives the relative path withrespect to the current folder
                if file.is_file():
                    shutil.copy2(file, pfolder / file)

        self.logger.info('Copying the files to the repository')
        for fname in map(Path, self._get_param(fw_spec, 'additional_files',
                                               [])):
            if fname.is_file():
                shutil.copy2(fname, pfolder / fname)

        if self._get_param(fw_spec, 'keep', False):
            # Just copy all files to the <struct_name>_data directory
            self.logger.info('Copying raw run data the repository')
            destination = pfolder / (struct_name + '_data.tar.gz')
            subfolder = Path(struct_name + '_data')
            with tarfile.open(str(destination), mode='w:gz') as archive:
                for file in cwd.glob(struct_name + '*'):
                    archive.add(file, arcname=str(subfolder / file))
                for file in cwd.glob('FW*'):
                    archive.add(file, arcname=str(subfolder / file))

        # Copy the seed file to the project folder
        if 'seed_name' in fw_spec:
            self.logger.info('Copying seed file to the repository')
            seed_file = cwd / (fw_spec['seed_name'] + '.cell')
            seed_file_pfolder = pfolder / seed_file.name
            # Only copy if there is the seed
            if seed_file.is_file():
                self.logger.info('Seed foound in the working directory')
                if seed_file_pfolder.is_file():
                    self.logger.info('Existing seed found in the repository')
                    if not filecmp.cmp(seed_file.resolve(),
                                       seed_file_pfolder.resolve()):
                        # Two seeds are not the same - something is wrong!!! Backup the seed as '-seed.cell'
                        self.logger.warning(
                            'Found seed in the project folder, but it is NOT THE SAME as used here!'
                        )
                        shutil.copy2(seed_file,
                                     pfolder / (struct_name + '-seed.cell'))
                else:
                    shutil.copy(seed_file, seed_file_pfolder)

    def _get_param(self, fw_spec, name, default=None):
        """Get paramaters that can be overriden by that in fw_spec"""

        if name in fw_spec:
            return fw_spec.get(name)
        return self.get(name, default)


@contextlib.contextmanager
def transiant_file(fname, mode='w+'):
    """Open a temporary file that will be deleted afterwards"""
    fhandle = open(fname, mode)
    yield fhandle
    fhandle.close()
    os.remove(fname)


def set_attributes(self, fw_spec, defaults):
    """
    Setup the attributes for an object.

    Those in the fw_spec takes the precedence.

    Args:
      self: The object whose attribute to be set
      fw_spec: A dictionary of the properties to be considerred
      defaults: A dictionary of the keys and its default values

    Returns:
      None

    """

    for key, default in defaults.items():
        if key in fw_spec:
            setattr(self, key, fw_spec[key])
        else:
            value = self.get(key, default)
            setattr(self, key, value)
    return self


def filter_spec(fw_spec):
    """Filter away internal parameters of a firework"""
    include_keys = [
        '_fworker',
        '_category',
        '_preserve_fworker',
    ]
    new_dict = {}
    for key, value in fw_spec.items():
        if (key in include_keys) or (not key.startswith('_')):
            new_dict[key] = value
    return new_dict


@contextlib.contextmanager
def create_symlinks(base_path, project_name, filenames):
    """
    Create symbolic links in the repository and remove the links when they are
    finished.

    Args:
      base_path: The base path for the setup
      project_name: name of the project
      filenames: a list of files to be linked
    """
    logger = get_fw_logger(__name__)
    if project_name is None:
        logger.info("No project name supplied - using 'default-project'")
        project_name = 'default-project'
    fman = FWPathManager(base_path)
    pfolder = fman.get_project_path(project_name)
    running_folder = pfolder / 'running'
    running_folder.mkdir(exist_ok=True)
    targets = []
    for filename in filenames:
        name = Path(filename).name
        target_path = running_folder / name
        # Remove existing link
        if target_path.is_symlink() or target_path.is_file():
            target_path.unlink()

        # Create the link
        try:
            os.symlink(Path(filename).resolve(), target_path)
        except FileExistsError:
            logger.error(f'Symbolics exists for {filename}')
        else:
            targets.append(target_path)

    logger.info(f'Symbolics created for {filenames}')
    yield targets

    # Remove the links when finished
    try:
        for target in targets:
            if target.is_symlink() or target.is_file():
                target.unlink()
    except OSError:
        logger.error(f'Problems when removing symlinks: {targets}')
