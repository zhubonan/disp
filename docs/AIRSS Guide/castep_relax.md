# The `castep_relax` script

This is script supplied by the `airss` package. The main idea is to
restart the DFT calculations every certain number of geometry step, in
order to update the basis set when running in the *fixed basis set* mode
with variable unit cell. By default, the script does several restarts
with very small number of ionic steps, as it is expected that the volume
could change significantly in the very begining. Afterwards, the
`geom_max_iter` setting in the `param` is respected. The optimisation is
terminated if CASTEP reports that the optimization is successful in two
consecutive restats, of if the maximum number of steps has been reached.

The input syntex is:

```
castep_relax <maxit> <exe> <sim> <symm> <seed>
```

These arguments are explained as below:

-   `<maxit>` is the maximum total number of geometry optimisation steps
    among all restarts. The optimisation is *assumed* to be finished if
    this number of steps has been reached.
-   `<exe>` is the launch command for running CASTEP, including the MPI
    launch command and its arguments.
-   `<sim>` is a switch to enable check if the same structure has been
    found before. It should be disabled by setting it to `0` in DISP, as
    each calculation is run under a different directory.
-   If the `<symm>` switch is set to `1` the structure will be
    symmetrised on-the-fly during the restarts. It is typically turned
    off.
-   `<seed>` is the name of the seed for CASTEP.

# When to use it

DISP invoke this script during the search and relaxation tasks to
perform the geomettry optimisation. Typically, the user does not need to
use this script manually, although it can useful when testing the
parameters or for performing manual relaxations of reference structures.

In the standard AIRSS search, this script is invoked by
`airss.pl` internally for CASTEP relaxation.
