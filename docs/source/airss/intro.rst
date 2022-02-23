============
Introduction
============

In this section, we give an brief introduction of the ``airss`` package and various search related settings.
Most of the contents are not specific to DISP and also apply when search with ``airss`` package along.


-----------------------
Ingredients of a search
-----------------------

This section gives a brief introduction of how to run a search using ``airss`` along.

The searching process is rather simple: a random structure is generated and subsequently relaxed.
However, both steps needs to be optimised for efficient searching.


++++++++++++++++++++
Structure generation
++++++++++++++++++++


In particular, the random structure should be not generated purely "randomly", 
but instead should based on a set of pre-determined constraints, to ensure that the output structures are physically sound.
If not done so, the search can be rather inefficient [#pickard_2011]_ [#zhu_2020]_ [#pyxtal]_ (often incorrectly interpreted as baseline).

The structure generation process is done by the ``buildcell`` program, which takes a CASTEP ``cell`` file style input. 
The key quantities pass for providing the constraints are:

* Estimated volume
* Species-wise minimum separations
* Number of symmetry operations to include

The question is: how can one know this prior to even performing the search? One simple way is to perform a short search with some guessed values. 
Such search may not find the true ground state, but the low energy structure would be able to provide the *cues* of what a ground state structure may
look like. 
The first two parameters can thereby be estimated from the low energy structure of such "pilot" search. 
Alternatively, if there are known experimental structure, the first two parameters can be estimated from those as well.

.. note::

    ``cat <xxx>.res | cryan -g`` is your friend for exacting these parameters.
    If the input structure is not in the SHELX format, the ``cabal`` tool can be used to convert it into that!

If one looks at typically polymorphs of a compounds, they do not vary too much (say < 20%) in terms of density and bond lengths.
The species-wise minimum separation may be inferred from that of chemically similar materials.
The exact values of the first two parameters would not make a huge difference in terms of search efficiency as long as they are sensible.
In fact, one may want to use minimum separation drawn randomly from a certain 

Finally, one may want to include symmetry operations in the generated structures - experimental structures are rarely *P1* after all.
Typically, two to four symmetry operations are included in the generated structure. 
The actual structure may gain more symmetry during the geometry operatimisation process, so the it is no necessary to have chosen specific space group in the first place.


.. note::

    A side issue of imposing symmetry operations is that once a space group is chosen,
    the multiplicity of a atom will not change during subsequent relaxations. 
    For example, atoms at the general positions will not be able to move to special positions.
    The default rule in ``airss`` is to maximise the occupation of general positions, which reduces the overall degrees of freedom.
    This also seems to follow the trend in most known crystals, but there can be exceptions.
    More special positions can be occupied by specifying the ``#ADJGEN`` setting. 
    Mind that the general positions of a low symmetry space group can still become special positions of a higher symmetry one or that of a smaller unit cell.

The template ``cell`` file generate by ``gencell`` contains other default settings which will not be detailed here.


++++++++++++++
DFT relaxation
++++++++++++++

Each generated structure needs to be relaxed to a local minimium by some means.
First-principles based methods are preferable as they provide realistic potential energy surfaces that are relatively smooth.
Typically, this is done by CASTEP [#castep]_ , although other plane wave DFT code may also be used as well.
CASTEP is preferred because it is well tested for this kind of tasks.
It has robust electronic and ionic minimisation routines and soft pseudopotentials (QC5) optimised for throughput.
The self-adaptive parallelisation in CASTEP also make it easy to deploy calculations on computing resources, since no manual input of parallelisation scheme is needed.

The typical setting is to use the QC5 pseudopotentials that requires very low cut off energies (300 - 340 eV) in order to maximise the speed.
These potentials are probably not accurate enough for regular calculations, but they are sufficient for sampling the potential energy surfaces.
The depth and the relative positions the local minima may be slightly wrong, but using them would be allow us to local these low energy structure much faster.
Since there is no ranking taking place during the search to direct the sampling region (e.g. unlike GA or PSO), it is not necessary to obtain accurate energy and structures at this stage. 
In the end, a set of high quality calculations (typically using the C19 pseudopotential set) needs be applied to refine the results and obtain reliable energy orderings.
This process is applied to only a subset of low energy structures that are already near the local minimum needs to be processed.

++++++++++++++++++
When to (not) stop
++++++++++++++++++

In crystal structure prediction, there is no way to make sure the ground state structure found is indeed true ground state,
unless one performs a exhaustive sampling of the potential energy surface, which is impractical for any high-dimensional space. 
However, for a single search, ones still have to have a stopping criteria.


.. [#pickard_2011] Pickard, C. J.; Needs, R. J. Ab Initio Random Structure Searching. Journal of physics. Condensed matter : an Institute of Physics journal 2011, 23 (5), 053201–053201. https://doi.org/10.1088/0953-8984/23/5/053201.
.. [#zhu_2020] Section 4.2.2, https://doi.org/10.17863/CAM.55681
.. [#pyxtal] Figure 7, https://doi.org/10.1016/j.cpc.2020.107810
.. [#castep] Academic license for CASTEP can be obtained free of charge, see http://www.castep.org.