# Searching for SrTiO3 ground state structure


$\mathrm{SrTiO_3}$ has a cubic perovskite structure at room temperature with space group $Pm\bar{3}m$.

## Search with GULP

In this example we search for its ground state using buckingham potential with long range coulumb interaction with [GULP](http://gulp.curtin.edu.au/gulp/).

The [Buckingham potential](https://en.wikipedia.org/wiki/Buckingham_potential) has the form:

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
cat *.res | cryan -u 0.1 -r -t  
SrTiO3-2*57-e185f4       0.00    61.004    -149.364    3 TiSrO3       Pm-3m          6
SrTiO3-2*37-9915e8       0.00   103.123       0.369    4 TiSrO3       Cmme           1
SrTiO3-2*02-d20277       0.00    85.448       0.399    2 TiSrO3       P21/m          4
SrTiO3-2*57-544bb1       0.00   102.862       0.422    4 TiSrO3       C2/c           1
SrTiO3-2*39-1dddc1       0.00   106.323       0.609    4 TiSrO3       P1             1
SrTiO3-2*05-354449       0.00    84.269       0.621    3 TiSrO3       P2             1
SrTiO3-2*25-1b6445       0.00    68.232       0.710    2 TiSrO3       R-3            3
SrTiO3-2*33-2f8d70       0.00   116.637       0.716    3 TiSrO3       P3212          1
SrTiO3-2*28-308697       0.00   100.410       0.718    4 TiSrO3       P1             1
SrTiO3-2*03-47308a       0.00   101.734       0.726    4 TiSrO3       P1             1
```

The above commend tries to *unite* similar structures before ranking them.
The numbers of united structures are printed in the last column.
It can be seen that ground state structure ($Pm\bar{3}m$) has been encountered six times, giving an encounter rate of 3%.

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

The command `disp db summary --project example/sto/dft` can be used to monitor the status of the search.
Once all 200 structures have been completed, retrieve the SHELX files and rank them with `ca -r -t` as before:


```
SrTiO3-2*16-fbabe1       0.01    60.788   -3798.971    2 TiSrO3       P4mm           1
SrTiO3-2*13-400370      -0.05    61.009       0.008    2 TiSrO3       R3m            1
SrTiO3-2*39-f3dc32      -0.04    61.073       0.011    3 TiSrO3       R3m            1
SrTiO3-2*49-8bd3e2      -0.03    61.094       0.011    3 TiSrO3       R3m            1
SrTiO3-2*52-9949ce       0.02    83.182       0.092    2 TiSrO3       P21/m          1
SrTiO3-2*30-e8bee6      -0.00    80.260       0.425    4 TiSrO3       Ima2           1
SrTiO3-2*38-7d3a16       0.03    76.714       0.445    4 TiSrO3       C2/c           1
SrTiO3-2*18-ac0857       0.03    72.950       0.466    6 TiSrO3       P32            1
SrTiO3-2*29-c45552      -0.01    74.188       0.498    2 TiSrO3       C2/m           1
SrTiO3-2*07-085d5a      -0.00    95.629       0.576    6 TiSrO3       P-6            1
```

At the first glance, there is a no structure with space group $Pm\bar{3}m$.
This is not surprise since the $Pm\bar{3}m$ phase is not actually the low temperature ground state.
The true ground state has a distorted octahedral network with space group $I4/mcm$.
While we did not found this exact phase, the top four structures are in fact also perovskites but has different distortion patterns.

Note that we have sampled only 200 structures, with the only prior knowledge of estimate range of atom-atom minimum distances and *volume per atom*.
While continuing the search may allow the true ground state to be found, one can already establish at this point that the ground state of $\mathrm{SrTiO_3}$ is a probably a perovskite.

!!! note

    Perovskites are known to have many distorted phases with octahedral.
    The P4mm phase obtained is non-central symmetric and has been reported in the literature as well[^1]. 
    Using the cubic phases as the high symmetry starting structure, one can also determine the ground state by mode mapping[^2].


## High precision calculation

Since the DFT search is carried out with setting prioritising speed rather than accuracy, typically one would need to re-relax the obtained structure with more converged parameters and more transferable pseudopotentials.

First, create the `SrTiO3-refine.cell` and `SrTiO3-refine.param` with revised parameters:

!!! example "SrTiO3-refine.cell"

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

    KPOINTS_MP_SPACING 0.05

    SYMMETRY_GENERATE
    SNAP_TO_SYMMETRY

    %BLOCK SPECIES_POT
    C19
    %ENDBLOCK SPECIES_POT

    %BLOCK EXTERNAL_PRESSURE
    0 0 0
    0 0
    0
    %ENDBLOCK EXTERNAL_PRESSURE

    ```

Where the `SPECIES_POT` is changed from `QC5` to `C19`.
The latter is a library with more accurate pseudopotentials ([delta = 0.3 meV]()).
In addition, the spaces of generated kpoints is requested to be at most $0.05 2\pi \unicode{x212B}^{-1}$ for improved sampling of the reciprocal space. 

!!! example "SrTiO3-refine.param"

    ```
    task                 : geometryoptimization
    xc_functional        : PBE 
    spin_polarized       : false 
    fix_occupancy        : false 
    metals_method        : dm 
    mixing_scheme        : pulay 
    max_scf_cycles       : 1000 
    cut_off_energy       : 700 eV
    opt_strategy         : speed 
    page_wvfns           : 0 
    num_dump_cycles      : 0 
    backup_interval      : 0 
    geom_method          : LBFGS 
    geom_max_iter        : 100 
    mix_history_length   : 20 
    finite_basis_corr    : auto
    fixed_npw            : false
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

In the `param` file, the plane-wave cut off energy is raised to `700 eV`.

!!! note "Constant basis quality relaxation"
    
    In this example, the `fixed_npw` is turned off so the variable cell relaxation will be performed under constant cut-off energy (quality) mode, and `finite_basis_corr` is turned on to allow the Pulay stress to be correct automatically.
    Otherwise, the basis set would change with unit cell, hence the effective cut off energy can be different from that initially supplied.
    This means that the final energy is always consistent with the geometry, and there is no need to perform an additional singlepoint calculation as in constant-basis mode, e.g. `fixed_npw : true`.

Create a folder with the top structures:

```
mkdir refine
cp $(ca -r -t -l |  awk '{print $1".res"}') refine/
```

And deploy the relaxations with:

```
disp deploy relax --seed SrTiO3-refine --base-cell SrTiO3-refine.cell \
--cell "refine/SrTiO3-*.res" --param SrTiO3-refine.param --project example/sto/dft-refine \
--priority 100 --category 24-core --cycles 0
```

Note that setting `cycles` to 0 bypass the automatic restart routine in `castep_relax` which is not needed with constant basis quality mode.

!!! tip

    Final results, one may also want to have:
    ```
    grid_scale : 2
    fine_grid_scale : 3
    ```
    in order to use denser FFT grids.
