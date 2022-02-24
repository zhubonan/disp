"""
Module with definition of Fireworks
"""
from multiprocessing.sharedctypes import Value
from fireworks.core.firework import Firework

from .tasks import AirssBuildcellTask, AirssCastepRelaxTask, AirssDataTransferTask, DbRecordTask, AirssModcellTask, AirssGulpRelaxTask, AirssPp3RelaxTask
from .utility_tasks import GzipDir

#pylint: disable=too-many-arguments, return-in-init,too-many-locals


class AirssSearchFW(Firework):
    """
    Perform standard AIRSS search work

    Perform structure building, relaxation, transfer and uploading to database
    """
    def __init__(self,
                 project_name,
                 seed_name,
                 seed_content,
                 param_content,
                 executable,
                 castep_code='default',
                 cycles=200,
                 record_db=False,
                 keep=True,
                 gzip_folder=True,
                 spec=None,
                 name=None,
                 modcell_content=None,
                 modcell_name=None,
                 code='castep',
                 walltime_seconds=600,
                 **kwargs):
        """
        Initialise a AirssSearchFW instance
        """

        tasks = []
        if spec is None:
            spec = {}

        _default = {
            'gzip_folder': gzip_folder,
            'record_db': record_db,
            'seed_name': seed_name,
            'project_name': project_name,
            '_walltime_seconds': walltime_seconds
        }
        spec.update(_default)

        build = AirssBuildcellTask(seed_name=seed_name,
                                   seed_content=seed_content,
                                   store_content=False,
                                   keep_seed=True,
                                   deposit_init_structure=True,
                                   project_name=project_name)
        tasks.append(build)
        if modcell_name is not None:
            mod = AirssModcellTask(func=modcell_name,
                                   func_content=modcell_content)
            tasks.append(mod)

        if code == 'castep':
            relax = AirssCastepRelaxTask(param_content=param_content,
                                        executable=executable,
                                        castep_code=castep_code,
                                        cycles=cycles)
        elif code == 'gulp':
            relax = AirssGulpRelaxTask(param_content=param_content,
                                        executable=executable,
                                        cycles=cycles)
        elif code == 'pp3':
            relax = AirssPp3RelaxTask(param_content=param_content,
                                        executable=executable,
                                        cycles=cycles)
        else:
            raise ValueError(f'Unknown code: {code}')
        
        tasks.append(relax)

        transfer = AirssDataTransferTask(keep=keep)
        tasks.append(transfer)

        if name is None:
            name = f'BuildRelax-{project_name}/{seed_name}'

        if record_db or spec.get('record_db'):
            spec['record_db'] = True
            spec[
                '_add_launchpad_and_fw_id'] = True  # Allow the Firework to acess the fw_id
            tasks.append(DbRecordTask())
        if gzip_folder or spec.get('gzip_folder'):
            spec['gzip_folder'] = True
            tasks.append(GzipDir())

        return super(AirssSearchFW, self).__init__(tasks=tasks,
                                                   spec=spec,
                                                   name=name,
                                                   **kwargs)


class RelaxFW(Firework):
    """
    Perform standard a relaxation

    Perform a geometry optimisation using CASTEP.
    """
    def __init__(self,
                 project_name,
                 struct_name,
                 struct_content,
                 param_content,
                 executable,
                 seed_name,
                 castep_code='default',
                 cycles=200,
                 record_db=False,
                 gzip_folder=False,
                 keep=True,
                 existing_spec=None,
                 name=None,
                 code='castep',
                 walltime_seconds=600,
                 **kwargs):
        """
        Initialise a AirssSearchFW instance

        Args:
          existing_spec: Existing spec to be based on.
        """

        tasks = []
        if existing_spec is None:
            spec = {}
        else:
            spec = dict(existing_spec)

        spec.update({
            'struct_name': struct_name,
            'struct_content': struct_content,
            'project_name': project_name,
            'seed_name': seed_name,
            '_walltime_seconds': walltime_seconds
        })

        if code == 'castep':
            relax = AirssCastepRelaxTask(param_content=param_content,
                                        executable=executable,
                                        castep_code=castep_code,
                                        cycles=cycles)
        elif code == 'gulp':
            relax = AirssGulpRelaxTask(param_content=param_content,
                                        executable=executable,
                                        cycles=cycles)
        elif code == 'pp3':
            relax = AirssPp3RelaxTask(param_content=param_content,
                                        executable=executable,
                                        cycles=cycles)
        else:
            raise ValueError(f'Unknown code: {code}')

        transfer = AirssDataTransferTask(keep=keep)

        if name is None:
            name = f'Relax-{project_name}/{struct_name}'
        tasks = [relax, transfer]

        if record_db or spec.get('record_db'):
            spec['record_db'] = True
            spec[
                '_add_launchpad_and_fw_id'] = True  # Allow the Firework to access the fw_id
            tasks.append(DbRecordTask())
        if gzip_folder or spec.get('gzip_folder'):
            spec['gzip_folder'] = True
            tasks.append(GzipDir())

        return super(RelaxFW, self).__init__(tasks=tasks,
                                             spec=spec,
                                             name=name,
                                             **kwargs)
