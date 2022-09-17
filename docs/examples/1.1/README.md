# Ground state of a Lennard-Jones solid

!!! tip

    This example can be run on a laptop, no DFT calculation is involved

In this example we will search for the ground state of a Lennard-Jones solid following the example 1.1 in the AIRSS pacakge itself (see https://airss-docs.github.io/tutorials/examples/).

The cell is chosen randomly with a volume of 8 Ang^3 per atom, and 8 atoms are placed into the cell.
A minimum separation of 1.5 A is enforced when generating the structure.

???+ example "Al.cell"

    ```
    %BLOCK LATTICE_CART
    2 0 0
    0 2 0
    0 0 2
    %ENDBLOCK LATTICE_CART

    %BLOCK POSITIONS_FRAC
    Al 0.0 0.0 0.0 # Al1 % NUM=8
    %ENDBLOCK POSITIONS_FRAC

    #MINSEP=1.5
    ```

Note that there is a only a single entry in the `POSITIONS_FRAC` block with `NUM=8`.
This syntex allows the volume of the cell to be scaled automatically - the *apparent* volume is for the *apparent* number of atoms in the `POSITIONS_FRAC` block.
To search a 16-atom cell, simply change `NUM=8` to `NUM=16`.

The pair potential infromation is stored in the `Al.pp` file.

???+ example "Al.pp"

    ```
    1 12 6 2.5
    Al
    # Epsilon
    1
    # Sigma
    2
    # Beta
    1
    ```

The 12 and 6 in the first line are the exponentials, making this a Lennard-Jones potentials,
followed by the cut off distance in the unit of *sigma*.
The potential is shifted so that the energy is zero at the cut off radius (see [here](https://en.wikipedia.org/wiki/Lennard-Jones_potential)).

You should be able to launch a search with:

```
airss.pl -pp3 -max 20 -seed Al
```

This command will generate 20 structures and relax them, the final results will be in the SHLEX format.
You can list the structures using the `ca -r` command (equivalent to `cat *.res | cryan -r`).

```
Al-12719-7842-18         0.00     7.561      -6.659    8 Al           P63/mmc        1
Al-12719-7842-2          0.00     7.561       0.000    8 Al           P63/mmc        1
Al-12719-7842-5          0.00     7.561       0.000    8 Al           P63/mmc        1
Al-12719-7842-14        -0.00     7.562       0.002    8 Al           P63/mmc        1
Al-12719-7842-20         0.00     7.564       0.005    8 Al           Fm-3m          1
Al-12719-7842-15        -0.00     7.564       0.005    8 Al           Fm-3m          1
Al-12719-7842-4         -0.00     7.564       0.005    8 Al           Fm-3m          1
Al-12719-7842-8         -0.00     7.564       0.005    8 Al           Fm-3m          1
Al-12719-7842-16        -0.00     7.564       0.005    8 Al           Fm-3m          1
Al-12719-7842-7         -0.00     7.564       0.005    8 Al           Fm-3m          1
Al-12719-7842-12        -0.00     7.564       0.005    8 Al           Fm-3m          1
Al-12719-7842-11         0.00     7.564       0.005    8 Al           Fm-3m          1
Al-12719-7842-17        -0.00     7.564       0.005    8 Al           Fm-3m          1
Al-12719-7842-9         -0.00     7.564       0.005    8 Al           Fm-3m          1
Al-12719-7842-19        -0.00     7.784       0.260    8 Al           C2/m           1
Al-12719-7842-3         -0.00     7.825       0.360    8 Al           Immm           1
Al-12719-7842-13         0.00     7.835       0.364    8 Al           Cmmm           1
Al-12719-7842-10        -0.00     8.119       0.700    8 Al           R-3c           1
Al-12719-7842-1         -0.00     8.446       0.705    8 Al           Cm             1
Al-12719-7842-6          0.00     8.773       0.869    8 Al           C2/m           1
```

Column one shows the label of each structure.
The second and the third column shows the pressure and the volume of the structures, respectively.
The forth column is the enthalpy of the system, based on which the structure are ranked.
For clarity, from the second row and below only the difference is printed.
The value is normalised *per formula* as shown in the sixth column.
The number of formula is shown in the fifth column.
The space group of each structure is shown in the seventh column, in the output above the known hexagonal ground state structure (P63/mmc) phase is found.
So far we are just using the scripts in the AIRSS package itself.


## Using DISP

Let's now use DISP as the search runner.
You should have a MongDB instance running some where, and have updated its information in both `disp_db.yaml` and `my_launchpad.yaml`.
The default in these two files is to connect to a instance hosted locally.

??? note "Using MongoDB locally"

    If you are on Linux, you can use docker to quickly launch an mongodb:
    ```
    sudo service docker start
    sudo docker run -d -p 27017:27017 mongo:4.4.9
    ```
    to shutdown the service:
    ```
    sudo docker ps
    ```
    to find the id the of container, then
    ```
    sudo docker stop <container_id>
    ```
    will stop the container.

!!! note

    Test the fireworks setup with `lpad get_fws` - it should return `[]` for a fresh database.
    For a completely blank database, you need to run `lpad reset` to initialise it for fireworks.


First, check the status with `disp check database`.
This should print something like:

```
Using launchpad file at `<your current directory>/my_launchpad.yaml`
LaunchPad name: bonan-db
DISP database specification file located at: <your current directory>/disp_db.yaml
host           : XXXXXX
user           : XXXXXX
port           : XXXXXX
db_name        : XXXXXX

Total number of SHELX entries: XXXX
```

The last line indicates that the database is successfully connected.

!!! note

    Test the fireworks setup with `lpad get_fws` - it should return `[]` for a fresh database.
    For a completely blank database, you need to run `lpad reset` to initialise it for fireworks.


Now, you can deploy the searches with

```
disp deploy search --seed Al --project example/1.1 --code pp3 --num 20
```

!!! note

    A `--dryrun` tag can be used to dryrun the submission of the jobs.
    It also runs `buildcell` locally trying to build the structures and will print the inputs.
    It is a good practice to check if they are correct before submitting the workload to the remote computer.

Now, the jobs have been submitted to the remote server.


To run the actual search, using the local computer as a worker:

```
export DISP_DB_FILE=$(pwd)/disp_db.yaml
rlaunch rapidfire
```

The first line is important as it sets the environmental variable so the *worker* knows which database to upload the completed structures to.

In production search using DFT calculations, we need to run `rlaunch` from inside a job script.
However, because Fireworks does it deal with walltime limits, an extended launcher `trlaunch` should be used instead.
This way the remaining walltime limit will be taken into consideration.


Now you can inspect the results with:

```
disp db summary
```

which should give an output like the one below:

```
              Structure      WF count - search
                    RES Init         COMPLETED ALL
project  seed
test-1-1 Al          20   20                20  20
```

The resulting structure can be pulled from the server with:

```
disp db retrieve-project --project test-1-1
```

Then use `ca -r` to check the results, just as before.


## Further reading

The [online airss documentation](https://airss-docs.github.io/tutorials/examples/) contains more insightful tutorials for searching Lennard-Jone systems.

!!! note

    Search for isolated clusters is not currently supported by DISP.
