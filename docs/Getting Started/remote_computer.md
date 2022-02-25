# Setup on the remote computer

DISP and associated packages needs to be installed on the computers which the workload will be run.
In most cases, the process is similar to that of installation on the local computer.
It is recommanded that you install all packages in a [conda environment](https://docs.conda.io/en/latest/), rather than relying on system-wide installed python environment.

## Installation using `conda` environment manager

For computing clusters and supercomputers, the default `HOME` folder of user may not be mounted on the computer nodes. 
If that if the case, you can install [miniconda3](https://docs.conda.io/en/latest/miniconda.html) onto the work/scratch partition and use a activation script to enable the environment.

Example activation script:

```
. /work/xxx/<username>/miniconda3/etc/profile.d/conda.sh
export WORK_DIR="/work/xxxx/<username>"
export FW_CONFIG_FILE="/work/xxx/<username>/disp/config/FW_config.yaml"
export DISP_DB_FILE="/work/xxx/<username>/disp/config/disp_db.yaml"
export PATH=${WORK_DIR}/airss-0.9.1/bin:$PATH
```

assuming that AIRSS has been compiled and installed under `$WORK_DIR/airss-0.9.1`.
This file is  save as `/work/xxx/<username>/activate_disp.sh`.

To create a conda environment and install DISP in it:

```
conda create -p /work/xxx/<username>/disp-base/disp_env python=3.8
conda activate /work/xxx/<username>/disp-base/disp_env
pip install git+https://https://github.com/zhubonan/disp
```


Once done, you should use `disp check database` to test if the connection to the remote server is working.

## Submission script

To have DISP running on the compute nodes, the jobs script setup the environment and start the work using the `trlaunch` command (or `arlaunch` from [aiida-fireworks-scheduler](https://github.com/zhubonan/aiida-fireworks-scheduler)).

Here is an example jobs script for SLURM scheduler:

```
#!/bin/bash

# Slurm job options (job-name, compute nodes, job time)
#SBATCH --job-name=DISP-32
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --tasks-per-node=128
#SBATCH --cpus-per-task=1

# User account information
#SBATCH --account=XXXX
#SBATCH --partition=XXXX
#SBATCH --qos=XXXX

# Setup the job environment (this module needs to be loaded before any other modules)
# Modules should be loaded for running CASTEP
module load <PACKAGE NAME>
module list


# Initiate conda environments
source /work/xxxx/<username>/activate_disp.sh

# Activate the conda environment with DISP installed
conda activate /work/xxxx/<username>/disp-base/disp_env

# Default launch command prefix for CASTEP
export MPI_LAUNCH_CMD="srun -N1 -n32 --exclusive --mem-per-cpu=1600M --cpus-per-task=1 --distribution=block:block --hint=nomultithread"

# Check connect to the remote server
lpad get_fws -m 1

if [ "$?" -eq 0 ]; then
        # Start the rocket launcher
        CMD="trlaunch -l ${WORK_DIR}/disp-base/config/my_launchpad.yaml -w ./fworker-32-core.yaml multi 4 --timeout 86000 --local_redirect --nlaunches 100"
        eval $CMD
else
        echo "Server cannot be reached - job terminated"
fi

```


In this example, each compute node has 128 CPUs and we want to run four 32-core CASTEP jobs concurrent for relaxing the structure. 
This is achieve by the line below:

```
CMD="trlaunch -l ${WORK_DIR}/disp-base/config/my_launchpad.yaml -w ./fworker-32-core.yaml multi 4 --timeout 86000 --local_redirect" 
```

which runs 4 concurrent workers, each using 32 CPUs.
The workers will run indefinitely until the timeout has passed, or when there is no jobs in the server to be picked up.
In this example, each cluster job is limited to 24 hours, and a timeout 86000 seconds is set to avoid picking new job in the very last part of the allocation.
Any unfinished relaxation will be loaded to the server and pick up by other workers in the future.


The file `fworker-32-core.yaml` controls certain run time parameters and gives an identity to the process runs our structure searching workload.

```
name: "<CLUSTER NAME> 32-core worker"
category:
  - 32-core
query: '{}'

env:
    castep_codes:
            latest: srun -N1 -n32 --mem-per-cpu=1600M --cpus-per-task=1 --exclusive --cpu-bind=cores --distribution=block:block --hint=nomultithread /work/xxx/<username>/castep/bin/latest/castep.mpi
            2011: srun -N1 -n32 --mem-per-cpu=1600M --cpus-per-task=1 --exclusive --cpu-bind=cores --distribution=block:block --hint=nomultithread /work/xxx/<username>/castep/bin/linux_x86_64_gfortran10.0-XT--2011-geom-spin/castep.mpi

    # Use non-login shell for running

```

The `env` section contains directive specific for this worker.
The `castep_codes` contains a dictionary of code alias and the full command to be used for launching CASTEP. 
It the requesteed code is not found in this section, the default `castep.mpi` (from `$PATH`) will be used with prefix from `MPI_LAUNCH_CMD` used.
The `category` allows controling the placement of workload.
Each search can be associated with one or more categories, and only those *worker* with matching category will pull the job to run.
For example, those with small unit cells can be run with few number of MPI processes (to improve the overall throughput).

In this example, advanced *job step* capability of the SLURM scheduler is used to run many smaller jobs inside a single job, using the `srun` MPI launcher. 
Care should be taken to verify the CPU resources are indeed allocated in the correct way.


## Further reading