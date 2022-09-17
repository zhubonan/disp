"""
Module based on getting information from scontrol
"""
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Scheduler:
    """Scheduler object"""

    def __init__(self, *args, **kwargs):
        """Scheduler object for accessing information from the scheduler"""
        del args
        del kwargs
        self._job_id = None
        self._ncpus = None

    def get_n_cpus(self):
        """Return the number of CPUS in this job"""
        raise NotImplementedError

    @property
    def user_name(self):
        """Return the name of the current user"""
        return os.environ["USER"]

    def get_remaining_seconds(self):
        """Get the reminaing time before this job gets killed"""
        raise NotImplementedError

    @property
    def is_in_job(self):
        """Return wether I am in a remote job"""
        if self.job_id is None:
            return False
        return True

    @property
    def job_id(self):
        raise NotImplementedError

    @classmethod
    def get_scheduler(cls):
        """
        Return a valid scheduler instance for the current environment.
        """
        for trial in [Slurm, SGE, Dummy]:
            obj = trial()
            if obj.is_in_job:
                return obj
        return None


class Dummy(Scheduler):
    """Dummy scheduler for running locally"""

    DEFAULT_REMAINING_TIME = 3600 * 24 * 30

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._job_id = "0"

    def get_n_cpus(self):
        return 4

    @property
    def job_id(self) -> str:
        return self._job_id

    def get_remaining_seconds(self):
        """Get the remaining time. Default to 30 days"""
        return self.DEFAULT_REMAINING_TIME

    @property
    def is_in_job(self):
        return True


class SGE(Scheduler):
    """Scheduler object for SGE scheduler"""

    def __init__(self, *args, **kwargs):
        """Initialise the SGE scheulder object"""
        super().__init__(*args, **kwargs)
        if self.is_in_job:
            self._readtask_info()
        self._start_time = None

    @property
    def job_id(self):
        """ID of the job"""
        if self._job_id is None:
            job_id = os.environ.get("JOB_ID")
            task_id = os.environ.get("SGE_TASK_ID")
            if task_id and task_id != "undefined":
                job_id = job_id + "." + task_id
                logger.warning("WARNING: REMAINING TIME IS NOT CORRECT FOR TASK ARRAY")
            self._job_id = job_id
        return self._job_id

    def _readtask_info(self):
        """Read more detailed task infomation"""
        raw_data = subprocess.check_output(
            ["qstat", "-j", f"{self.job_id}"], universal_newlines=True  # pylint: disable=unexpected-keyword-arg
        )
        raw_data = raw_data.split("\n")
        task_info = {}
        for line in raw_data[1:]:
            # Ignore lines that are not in the right format
            try:
                key, value = line.split(":", maxsplit=1)
            except ValueError:
                continue
            task_info[key.strip()] = value.strip()
        self._task_info = task_info

    def get_n_cpus(self):
        """Get the number of CPUS"""
        nslots = os.environ.get("NSLOTS")
        if nslots:
            return int(nslots)
        return None

    def get_max_run_seconds(self):
        """Return the maximum run time in seconds"""
        rlist = self._task_info["hard resource_list"]
        match = re.search(r"h_rt=(\d+)", rlist)
        if match:
            return int(match.group(1))
        return None

    def get_end_time(self):
        """Return the time when the job is expected to finish"""
        end_time = self.get_start_time() + timedelta(seconds=self.get_max_run_seconds())
        return end_time

    def get_start_time(self):
        """Return the start time of this job"""
        output = subprocess.check_output(  # pylint: disable=unexpected-keyword-arg
            ["qstat", "-j", str(self.job_id), "-xml"], universal_newlines=True
        )
        match = re.search(r"<JAT_start_time>(.+)</JAT_start_time>", output)
        if match:
            raw = match.group(1)
            time_int = int(raw)
            # Scheduler always use UTC time - not may note be true everywhere
            start_time = datetime.utcfromtimestamp(time_int).replace(tzinfo=timezone.utc)
            self._start_time = start_time
        return start_time

    def get_remaining_seconds(self):
        """Return the remaining time in seconds"""
        # Everything much be time zone aware to work with BST
        tdelta = self.get_end_time() - datetime.now().astimezone()
        return int(tdelta.total_seconds())


class Slurm(Scheduler):
    """Slurm object for storing and extracting information in slurm"""

    _task_info = None
    _warning = 0

    def __init__(self):
        """Initialise and Slurm instance"""
        super().__init__()
        self.task_info = {}
        if self._task_info is None:
            self._readtask_info()
            self._task_info = self.task_info
        else:
            self.task_info = self._task_info

    @property
    def is_in_job(self):
        """Wether I am in a job"""
        return "SLURM_JOB_ID" in os.environ

    @property
    def job_id(self):
        if self._job_id is None:
            self._job_id = os.environ.get("SLURM_JOB_ID")
        return self._job_id

    def _readtask_info(self):
        """A function to extract information from environmental varibles
        SLURM_JOB_ID unique to each job
        Return an dictionnary contain job information.
        If not in slurm, return None
        TODO Refector avoid saving intermediate file
        """
        sinfo_dict = {}
        if not self.is_in_job:
            if self._warning == 0:
                logger.debug("NOT STARTED FROM SLURM")
                self._warning += 1
            self.task_info = {}
            return

        # Read information from scontrol commend
        # Temporary file for storing output
        with tempfile.TemporaryFile(mode="w+") as tmp_file:
            subprocess.run(f"scontrol show jobid={self.job_id:s}", shell=True, check=True, stdout=tmp_file)
            # Iterate through lines
            tmp_file.seek(0)
            for line in tmp_file:
                # Iterate through each pair
                for pair in line.split():
                    # Parse each pair
                    pair_s = pair.split("=", maxsplit=2)
                    if len(pair_s) == 2:
                        sinfo_dict[pair_s[0]] = pair_s[1]
                    # Empty field - put None
                    elif len(pair_s) == 1:
                        sinfo_dict[pair_s[0]] = None
        type(self)._task_info = sinfo_dict
        self.task_info = sinfo_dict
        return

    def get_end_time(self):
        """
        Query the end time of an job
        Return a datetime object
        """
        if self.task_info:
            end_time = datetime.strptime(self.task_info["EndTime"], "%Y-%m-%dT%H:%M:%S")
        else:
            end_time = None
        return end_time

    def get_remaining_seconds(self):
        """Return the reminaing time in seconds"""
        return int((self.get_end_time() - datetime.now()).total_seconds())

    def get_user_name(self):
        """
        Parse the user name from task info
        """
        if self.task_info:
            pattern = r"([A-Za-z]+[0-9]+)\([0-9]+\)"
            match = re.match(pattern, self.task_info["UserId"])
            return match.group(1)
        return None

    def get_job_id(self):
        """Return the job ID(string)"""
        return self.task_info.get("JobId", None)

    def get_n_cpus(self):
        """Return number of CPU allocated"""
        return self.task_info.get("NumCPUs", None)

    def get_array_id(self):
        """return array id, or None"""

        return self.task_info.get("ArrayJobId", None)

    def get_array_task_id(self):
        return self.task_info.get("ArrayTaskId", None)

    def get_array_job_id(self):
        """Return the array job id.
        {array_id}_{array_task_id}"""
        task = self.task_info
        if not task:
            return None
        try:
            ajobid = task["ArrayJobId"]
            ataskid = task["ArrayTaskId"]
        except KeyError:
            res = None
        else:
            res = f"{ajobid}_{ataskid}"
        return res

    def hold_array(self, array_num=None):
        """
        Try to hold the array this job is run from
        """
        array_id = self.get_array_job_id()
        if array_num:
            array = array_num
        elif array_id:
            array = array_id.split("_")[0]
        else:
            array = None
        if array is not None:
            proc = subprocess.run(f"scontrol hold {array}", shell=True, check=True)
            if proc.returncode == 0:
                logger.info("Successfully hold the array %d", array)
            else:
                logger.error("Cannot hold array %d", array)
        else:
            logger.error("Cannot found the array to hold")

    def hold_all_pd_arrays(self, user_name=None):
        """Hold ALL pending arrays"""
        arrays = self.get_pd_arrays(user_name)
        if not arrays:
            logger.warning("No array found to be hold")
            return
        logger.info("Trying to hold all arrays in pending state")
        array_list = ",".join(arrays)
        subprocess.run(["scontrol", "hold", array_list], check=True)

    def release_all_pd_arrays(self, user_name=None):
        """
        Release all pending arrays
        """
        arrays = self.get_pd_arrays(user_name)
        if not arrays:
            logger.warning("No array found to be released")
            return
        array_list = ",".join(arrays)
        subprocess.run(["scontrol", "release", array_list], check=True)

    def get_running_jobs(self, user_name=None):
        """
        Return a list of running jobs of the current user
        NOTE: in string format
        """
        ids = self._get_id_of_state("R", "%A %t", user_name)
        return ids

    def get_pd_arrays(self, user_name=None):
        """
        Return a list of pending array jobs
        """
        ids = self._get_id_of_state("PD", "%F %t", user_name)
        return ids

    def _get_id_of_state(self, criteria, fmt_str, user_name=None):
        """
        Get ids for jobs satisfying certain criteria
        criteria : string of the criteria
        fmt_str : format string should be used in sequence
        user_name : assign specific user name
        """
        if not self.task_info and not user_name:
            return None

        if not user_name:
            user_name = self.get_user_name()
        res = tempfile.TemporaryFile(mode="w+")
        subprocess.run(f'squeue -u {user_name:s} -o"{fmt_str}"', shell=True, check=True, stdout=res)
        res.seek(0)
        task_ids = []
        for line in res:
            sline = line.split()
            if sline[1] == criteria:
                task_ids.append(sline[0])
        res.close()
        return task_ids

    def __bool__(self):
        """Neat check of whether we get information yet"""
        return bool(self.task_info)

    def __getitem__(self, key):
        """Overide for easier item getting"""
        if self.task_info:
            return self.task_info.__getitem__(key)
        return None

    def __contains__(self, key):
        return key in self.task_info
