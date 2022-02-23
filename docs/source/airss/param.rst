==================
The ``param`` file
==================


A typical default ``param`` file for CASTEP looks like this:

.. literalinclude:: 4SrTiO3.param

Several tags that you may want to modify are:

xc_functional
    Defines the exchange-correlation functional to be used. 
    Since PBE often bias towards less bonded (larger volume) phases, one may want to use PBEsol instead.

spin_polarized
    If set to ``true`` the calculation will be spin polarized. 
    Note that CASTEP does not have default set for each site, so one have to break the symmetry manually in addition to setting this tag.
    The initial spin polarisation per site can be site as ``SPIN=XX`` following the coorindates under ``POSITIONS_ABS`` or ``POSITIONS_FRAC``` in the ``cell`` file.
    Alternatively, one can set ``spin : XX`` in the ``param`` file here, where ``XX`` is the total spin of the unit cell.
    However, the value passed must to consistent with the total set in ``cell`` file, if the latter is also set.

fixed_npw
    aka, "fix the number of plane waves". 
    CASTEP default to constant basis-quality during variable-cell geometry geometry optmisation rather than the constant basis set in many other plane wave codes.
    While this allows getting a reliable final energy with restarts, the ``castep_relax`` script already handles automatically restart anyway.
    Having consistant basis-quality may not be optimum when large pulay stress is present, e.g. using less well-converged cut off energies.
    Hence, it is preferable to set it to ``true`` and use the constant basis set approach.

cut_off_energy
    The cut off energy should be sufficient for the pseudopotential used.
    There is no need to high quality but harder pseudopotentials in the initial search in most case.

geom_method
    Algorithm for geometry optmisation. ``LBFGS`` works well cases, otherwise ``tpsd`` may be used instead.

mixing_scheme
    This tags controls the charge density mixer. The ``pulay`` mixer is OK for most case, otherwise one can use ``broyden`` instead if convergence struggles.

max_scf_cycles
    Keep a large value to avoid CASTEP giving up the structure due to electronic convergence instability.

opt_strategy
    Use ``speed`` to keep everything in the RAM and avoid any slow disk IO.

geom_max_iter
    Number of geometry optimisation per run. Since ``castep_relax`` will repetively restart calculation, use a small value so the basis set is reset every so often.
    For fixed cell optimisation, one can use a large value in combination with apporiate ``castep_relax`` arguments and avoid restarts.

metals_method
    Use ``dm`` (density mixing) for speed. The ``edft`` solver is more stable but much slower, making it unsuitable for any search works.
    It may still be useful for conventional DFT calculation where the system has an electronic structure that is tricky to solve.
