# Searching for SrTiO3 ground state structure


$\mathrm{SrTiO_3}$ has a cubic perovskite structure at room temperature with space group $Pm\bar{3}m$.

## Search with GULP

In this example we search for its ground state using buckingham potential with long range coulumb interaction with [GULP]().

The Buckingham potential has the form:

$$ \Phi_{12} = A \exp(-Br) - \frac{C}{r^6} + \frac{q_1 q_2}{4\pi\epsilon_0r} $$

A template seed can be generated with:

```
gencell 60 1 Sr 1 Ti 1 O 3
```

The `gencell` command is a very useful for providing a template *seed* file for `buildcell`.
Using the command above, the generated cell has a target volume of 60 $\unicode{x212B}^3$ containing one Sr atom, one Ti atom and three O atoms.
The content of this file is shown below.

???+ example "SrTiO3.cell"

    ```
    %BLOCK LATTICE_CART
    3.914865 0 0
    0 3.914865 0
    0 0 3.914865
    %ENDBLOCK LATTICE_CART

    #VARVOL=60

    %BLOCK POSITIONS_FRAC
    Sr 0.0 0.0 0.0 # Sr1 % NUM=1
    Ti 0.0 0.0 0.0 # Ti1 % NUM=1
    O 0.0 0.0 0.0 # O1 % NUM=1
    O 0.0 0.0 0.0 # O2 % NUM=1
    O 0.0 0.0 0.0 # O3 % NUM=1
    %ENDBLOCK POSITIONS_FRAC

    ##SPECIES=Sr,Ti,O
    ##NATOM=3-9
    ##FOCUS=3

    #SYMMOPS=2-4
    ##SGRANK=20
    #NFORM=2-6
    ##ADJGEN=0-1
    #SLACK=0.25
    #OVERLAP=0.1
    #MINSEP=1.8-3
    #COMPACT
    #CELLADAPT
    ##SYSTEM={Rhom,Tric,Mono,Cubi,Hexa,Orth,Tetra}

    KPOINTS_MP_SPACING 0.07

    SYMMETRY_GENERATE
    SNAP_TO_SYMMETRY

    %BLOCK SPECIES_POT
    QC5
    %ENDBLOCK SPECIES_POT

    %BLOCK EXTERNAL_PRESSURE
    0 0 0
    0 0
    0
    %ENDBLOCK EXTERNAL_PRESSURE
    ```

An `param` is also generated for default CASTEP inputs. 

??? example "SrTiO3.param"

    A `param` file CASTEP calculation is generated as well. 
    ```
        task                 : geometryoptimization
    xc_functional        : PBE
    spin_polarized       : false
    fix_occupancy        : false
    metals_method        : dm
    mixing_scheme        : pulay
    max_scf_cycles       : 1000
    cut_off_energy       : 340 eV
    opt_strategy         : speed
    page_wvfns           : 0
    num_dump_cycles      : 0
    backup_interval      : 0
    geom_method          : LBFGS
    geom_max_iter        : 20
    mix_history_length   : 20
    finite_basis_corr    : 0
    fixed_npw            : true
    write_cell_structure : true
    write_checkpoint     : none
    write_bib            : false
    write_otfg           : false
    write_cst_esp        : false
    write_bands          : false
    write_geom           : false
    bs_write_eigenvalues : false
    calculate_stress     : true
    ```

The potential in put for GULP is:

???+ example "SrTiO3.lib for GULP"

    This file `SrTiO3.lib` is needed for providing the parameters of the interatomic potentials.
    ```
    species
    Sr 2.00
    Ti 4.00
    O -2.00
    lennard 12 6
    Sr Sr 1.0 0.0 0. 6.0
    Sr Ti 1.0 0.0 0. 6.0
    Sr O  2.0 0.0 0. 6.0
    Ti Ti 1.0 0.0 0. 6.0
    Ti O  2.0 0.0 0. 6.0
    O  O  2.0 0.0 0. 6.0
    buck
    Sr Sr 9949.1  0.2446 0.0 0. 8.0
    Sr Ti 12708.1 0.2191 0.0 0. 8.0
    Sr O  1805.2  0.3250 0.0 0. 8.0
    Ti Ti 16963.1 0.1847 0.0 0. 8.0
    Ti O  845.0   0.3770 0.0 0. 8.0
    O  O  22746.3 0.1490 0.0 0. 8.0
    ```

While this `SrTiO3.cell` can be used straight away for searching already,
prior knowledge can be used to accelerate the search.
The number of formulas can be altered by setting `NFORM=2-6` to search for 2-6 formula units,
since it is expected thtat the ground state structure would take more than one formula units.
In addition, the specie-wise minimum separations can be set using the knowledge of known ion sizes and bond lengths - the Ti-O bond is known to be at least 1.8 $\unicode{x212B}$ long:

```
##MINSEP=1.8-3.0
```

This sets the species-wise minimum separation to be chosen randomly between 1.8 $\unicode{x212B}$ to 3.0 $\unicode{x212B}$. 

!!! tip

    One can invoke more knowledge of the system - cation-cation or anion-aion distances are larger than cation-anion distances. Incorporating this in the structure generation process would further improve the efficiency. 

We can now deploy our search with:

```
disp deploy search --project example/sto/gulp --seed SrTiO3 --code gulp --num 200 
```

To run locally

```
export DISP_DB_FILE=$(pwd)/disp_db.yaml
rlaunch rapidfire 
disp db retrieve-project --project example/sto/gulp
```

Example output:

```
$ ca -r -t

SrTiO3-2*57-e185f4       0.00    61.004    -149.364    3 TiSrO3       Pm-3m          1
SrTiO3-2*18-edecf0       0.00    61.005       0.000    2 TiSrO3       Pm-3m          1
SrTiO3-2*02-cdbf4e       0.00    61.005       0.000    2 TiSrO3       Pm-3m          1
SrTiO3-2*05-737e1a       0.00    61.004       0.000    2 TiSrO3       Pm-3m          1
SrTiO3-2*21-29ec4b       0.00    61.002       0.000    2 TiSrO3       Pm-3m          1
SrTiO3-2*47-ce203f       0.00    61.005       0.000    2 TiSrO3       Pm-3m          1
SrTiO3-2*37-9915e8       0.00   103.123       0.369    4 TiSrO3       Cmme           1
SrTiO3-2*02-d20277       0.00    85.448       0.399    2 TiSrO3       P21/m          1
SrTiO3-2*59-c7f053       0.00    85.448       0.399    2 TiSrO3       P21/m          1
SrTiO3-2*10-4f9c5f       0.00    85.449       0.399    4 TiSrO3       P21/m          1
```

The ground state structure ($Pm\bar{3}m$) has been encountered six times, giving an encounter rate of 3%.

!!! note

    As with all global search methods, there is no guarantee that the ground state is found.
    Given a $3\%$ encounter rate, the odds of finding the ground state out of 200 trials is:

    $$1 - (0.97)^200 = 99.7 \% $$

    Still, one can not rule our that there exists a true ground state with lower encounter rate.
    For example, if the encounter rate is 0.1%, the odds of finding it in 200 trials is only $18.1\%$.


## Search with CASTEP

Now we use CASTEP to perform the search using the same seed.


```
disp deploy search --seed SrTiO3  --project example/sto/dft --num 200 --priority 200 --category 24-core
```

This deploys the search tasks with a higher priority.
The actual calculations should be run on a decent-sized computing cluster.
Here the `--category` tag set ensures that the job to be picked up by workers whose category is set to `24-core`.




