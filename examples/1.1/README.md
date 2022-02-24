# Ground state of Lennard-Jones solid

In this example we will search for the ground state of a Lennard-Jones solid following the example 1.1 in the AIRSS pacakge itself.

The cell is chosen randomly with a volume of 8 Ang^3 per atom, and 8 atoms are placed into the cell.
A minimum separation of 1.5 A is enforced when generating the structure.
Note that there is a only a single entry in the `POSITIONS_FRAC` block with `NUM=8`.
This syntex allows the volume of the cell to be scaled automatically - the *apparent* volume is for the *apparent* number of atoms in the `POSITIONS_FRAC` block. 
To search a 16-atom cell, simply change `NUM=8` to `NUM=16`.

The pair potential infromation is stored in the `Al.pp` file.

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
    Al-91855-9500-1       -0.00     7.561    -6.659  8 Al           P63/mmc    1
    Al-91855-9500-6       -0.00     7.561     0.000  8 Al           P63/mmc    1
    Al-91855-9500-5       -0.00     7.561     0.000  8 Al           P63/mmc    1
    Al-91855-9500-10       0.00     7.564     0.005  8 Al           P-1        1
    Al-91855-9500-17      -0.00     7.564     0.005  8 Al           P-1        1
    Al-91855-9500-3       -0.00     7.564     0.005  8 Al           C2/m       1
    Al-91855-9500-18      -0.00     7.564     0.005  8 Al           Pmmm       1
    Al-91855-9500-20      -0.00     7.564     0.005  8 Al           C2/m       1
    Al-91855-9500-4       -0.00     7.564     0.005  8 Al           Pmmm       1
    Al-91855-9500-16      -0.00     7.564     0.005  8 Al           C2/m       1
    Al-91855-9500-2       -0.00     7.564     0.005  8 Al           Cmmm       1
    Al-91855-9500-11      -0.00     7.564     0.005  8 Al           C2/m       1
    Al-91855-9500-9       -0.00     7.564     0.005  8 Al           Cmmm       1
    Al-91855-9500-8        0.00     7.564     0.005  8 Al           Fmmm       1
    Al-91855-9500-19       0.00     7.784     0.260  8 Al           C2/m       1
    Al-91855-9500-12      -0.00     8.119     0.700  8 Al           R-3c       1
    Al-91855-9500-14      -0.00     8.446     0.705  8 Al           Cm         1
    Al-91855-9500-13       0.00     8.453     0.794  8 Al           C2/m       1
    Al-91855-9500-15       0.00     8.465     0.802  8 Al           C2/m       1
    Al-91855-9500-7        0.00     8.505     0.834  8 Al           P21/m      1
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
First, check the status with `disp check database`. 
This should print something like:

```
Using launchpad file at `/home/bonan/airss-fw/config/my_launchpad.yaml`
LaunchPad name: bonan-db
DISP database specification file located at: /home/bonan/airss-fw/config/disp_db.yaml
host           : XXXXXX
user           : XXXXXX
port           : XXXXXX
db_name        : XXXXXX

Total number of SHELX entries: XXXX
```

The last line indicates that the database is successfully connected.


Now, you can deploy the searches with 

```
disp deploy search --seed Al --project example/1.1
```

