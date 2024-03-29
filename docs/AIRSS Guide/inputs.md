# Typical inputs

The `buildcell` program is the workhorse for generating random
structures. It is often useful to generate a initial cell using the
`gencell` utility with `gencell <volume> <units> [<specie> <number>]`.
For example to search for `SrTiO3`, one can input:

``` console
gencell 60 4 Sr 1 Ti 1 O 3
```

This prepares a seed to search for four formula units of `SrTiO3`, each
formula unit is expected to have a volume of 60 $\mathrm{Å^3}$.

# The `cell` file


The content of the generated file `4SrTiO3.cell` is shown below:

???+ example

    ```
    %BLOCK LATTICE_CART
    3.914865 0 0
    0 3.914865 0
    0 0 3.914865
    %ENDBLOCK LATTICE_CART

    #VARVOL=60

    %BLOCK POSITIONS_FRAC
    Sr 0.0 0.0 0.0 # Sr1 % NUM=1
    Sr 0.0 0.0 0.0 # Sr2 % NUM=1
    Sr 0.0 0.0 0.0 # Sr3 % NUM=1
    Sr 0.0 0.0 0.0 # Sr4 % NUM=1
    Ti 0.0 0.0 0.0 # Ti1 % NUM=1
    Ti 0.0 0.0 0.0 # Ti2 % NUM=1
    Ti 0.0 0.0 0.0 # Ti3 % NUM=1
    Ti 0.0 0.0 0.0 # Ti4 % NUM=1
    O 0.0 0.0 0.0 # O1 % NUM=1
    O 0.0 0.0 0.0 # O2 % NUM=1
    O 0.0 0.0 0.0 # O3 % NUM=1
    O 0.0 0.0 0.0 # O4 % NUM=1
    O 0.0 0.0 0.0 # O5 % NUM=1
    O 0.0 0.0 0.0 # O6 % NUM=1
    O 0.0 0.0 0.0 # O7 % NUM=1
    O 0.0 0.0 0.0 # O8 % NUM=1
    O 0.0 0.0 0.0 # O9 % NUM=1
    O 0.0 0.0 0.0 # O10 % NUM=1
    O 0.0 0.0 0.0 # O11 % NUM=1
    O 0.0 0.0 0.0 # O12 % NUM=1
    %ENDBLOCK POSITIONS_FRAC

    ##SPECIES=Sr,Ti,O
    ##NATOM=3-9
    ##FOCUS=3

    #SYMMOPS=2-4
    ##SGRANK=20
    #NFORM=1
    ##ADJGEN=0-1
    #SLACK=0.25
    #OVERLAP=0.1
    #MINSEP=1-3 AUTO
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

As you can see, the input file for `buildcell` is essentially an marked
up `cell` file for CASTEP. Lines starting with `#` provides directives
for `buildcell`, although those with `##` will still be ignored.

# Options for `buildcell`

Several key tags are explained below:

`VARVOL`

:   Defines the *variable* volume of the unit cell, the exact volume
    will be randomise at a harded coded range of ± 5%. The actual unit
    cell vectors will be randomised, and those in the `LATTICE_CART`
    block takes no effect.

`POSITIONS_ABC`

:   Defines the *initial* positions of the atoms in the unit cell. The
    syntax after the `#` is `<set name> % [<tags>...]`. Where
    `<set name>` can be used to define rigid fragments by setting the
    same value for all of the linked sites. Since each atom should be
    considered independently in this example, each line has a different
    value. After the `%` comes the site-specific settings. The `NUM`
    allows a single site to be multiplicated. For example, adding 12
    oxygen atoms can achieved specified by `O 0. 0. 0. # O % NUM=12`
    instead of doing it line by line.

`SYMOPS`

:   Defines the number of symmetry operations to be included in the
    randomised structure. The `-` defines the range and a random value
    will be drawn from.

`SGRANK`

:   This tags can be enabled to bias the (randomly chosen) space group
    towards those that are more frequently found in the ICSD. The value
    defines a threshold rank for accepting the space group.

`NFORM`

:   This tags defines the number of formula units to be included in the
    generated structure. Here, the cell has the formula $\ce{Sr4Ti4O12}$
    according to the `POSITIONS_ABC` block. If one changes `NFORM` to be
    `2`, then the effective chemical formula would be $\ce{Sr8Ti8O24}$.
    If `NCORM` is not defined, the composition will be affect by
    `SYMOPS`, placing all atoms in the general positions.

`ADJGEN`

:   This tags is used to modify the number of general positions when
    generating symmetry-containing structures. By default, the number of
    general positions is maximised. This tags allows more special
    postions to be occupied if possible. For blind search, there is no
    need to use this tag in most cases.

`MINSEP`

:   This tags defines the specie-wise minimum separations and is one of
    the few tags that need to be manually changed by hand. The default
    `1-3 AUTO` means to randomly set minimum separations *per
    specie-pair* between 1 Å and 3 Å, but also try to extract and use
    that of the best structure if possible. The latter part is achieved
    by looking for a `.minsep` file in the current wroking directory,
    which is generated by the `airss.pl` script on-the-fly. This
    approach cannot be used by `DIPS` searches each calculation will be
    run from different directories (and probably also different
    machines). Initial values may be composed by the knowledge of common
    bond lengths. The `cryan -g` command can also be used to extract
    `MINSEP` from existing structures.

`SLACK,OVERLAP`

:   These two tags controls the process of modifying the structure to
    satisfy the minimum separations. Roughly speaking, a geometry
    optimisation is performed ,each species-pair having a hard shell
    potential. The tag `SLACK` defines how *soft* the hard shell
    potential constructed will be, and `OVERLAP` defines the threshold
    for acceptance. There is usually no need to vary these two tags.

`COMPACT,CELLADAPT`

:   Controls if the cell should be compacted and deformed based on the
    hard shell potentials. There is usually no need to change these two
    tags.

`SYSTEM`

:   Allows limiting the generated structure to certain crystal systems,
    which can be useful to bias the search based on prior knowledge.

## Options for CASTEP

Lines not marked up by `#` are often passed through, below are
descriptions of some CASTEP-related tags that goes in the `cell` file.


!!! note
    The `buildcell` program will not always pass through the native CASTEP keys, so check
    the output cell carefully.

`KPOINTS_MP_SPACING`

:   Defines kpoints spacing in unit of $\mathrm{2\pi\,Å^{-1}}$. Usually
    a not so well-converged setting can be used for the initial search.

`SYMMETRY_GENERATE`

:   Let CASTEP determine the symmetry for acclerating calculations. You
    will almost always want to have this.

`SNAP_TO_SYMMETRY`

:   Snap the atoms to the positions according to the determined
    symmetry. You will almost always want to have this.

`EXTERNAL_PRESSURE`

:   The upper triangle of the external stress tenser. It does not get
    passed through after `buildcell`.

`HUBBARD_U`

:   The Hubbard-U values for each specie and orbital. For example,
    `Mn d:3` will apply an effective U of 3 eV to the d orbital of Mn.

# The `param` file

The `param` file read by CASTEP only, and not used for building structure.
A default `param` file for CASTEP from `gencell` looks like this:

???+ example

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

Several tags that you may want to modify are:

`xc_functional`

:   Defines the exchange-correlation functional to be used. Since PBE
    often bias towards less bonded (larger volume) phases, one may want
    to use PBEsol instead.

`spin_polarized`

:   If set to `true` the calculation will be spin polarized. Note that
    CASTEP does not have default set for each site, so one have to break
    the symmetry manually in addition to setting this tag.

`fixed_npw`

:   aka, fix the number of plane waves. CASTEP default to constant
    basis-quality during variable-cell geometry geometry optmisation
    rather than the constant basis set in many other plane wave codes.
    While this allows getting a reliable final energy with restarts, the
    `castep_relax` script already handles automatically restart anyway.
    Having consistant basis-quality may not be optimum when large pulay
    stress is present, e.g. using less well-converged cut off energies.
    Hence, it is preferable to set it to `true` and use the constant
    basis set approach.

`cut_off_energy`

:   The cut off energy should be sufficient for the pseudopotential
    used. There is no need to high quality but harder pseudopotentials
    in the initial search in most case.

`geom_method`

:   Algorithm for geometry optmisation. `LBFGS` works well cases,
    otherwise `tpsd` may be used instead.

`mixing_scheme`

:   This tags controls the charge density mixer. The `pulay` mixer is OK
    for most case, otherwise one can use `broyden` instead if
    convergence struggles.

`max_scf_cycles`

:   Keep a large value to avoid CASTEP giving up the structure due to
    electronic convergence instability.

`opt_strategy`

:   Use `speed` to keep everything in the RAM and avoid any slow disk
    IO.

`geom_max_iter`

:   Number of geometry optimisation per run. Since `castep_relax` will
    repetively restart calculation, use a small value so the basis set
    is reset every so often. For fixed cell optimisation, one can use a
    large value in combination with apporiate `castep_relax` arguments
    and avoid restarts.

`metals_method`

:   Use `dm` (density mixing) for speed.
