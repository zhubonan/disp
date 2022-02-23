.. _crystal_structure_prediction:

============================
Crystal Structure Prediction
============================


    ONE of the continuing scandals in the
    physical sciences is that it remains in
    general impossible to predict the structure
    of even the simplest crystalline solids from
    a knowledge of their chemical composi-
    tion.
    - Maddox, J. Crystals from first principles. Nature 335, 201 (1988). https://doi.org/10.1038/335201a0


The structure of the material is essential in order to carry out any materials modelling work.
Very often, this information has to be obtained experimentally in the first place, or a reasonable guess must be performed.
For example, if one want to compute the band structure of TiO2 using DFT, the crystal structure of that particular TiO2 polymorph 
(and there are many of them) is needed as the input.
However, what if one want to model materials that has not been synthesised? Or perhaps looking for other polymorphs of the same
composition that can potentailly have different properties?

Crystal structure prediction is the process of predicting the crystal structure of materials from no or limited experimental data.
Quantum mechanics based first-principles calculations allow accurate energy/force/stress to be determined for any given atomic structure.
Using these techniques, in theory, one can just type in the formula and the computer should be able to output the experimental crystal structure(s).
This, however, turned out to be not so trivial and may involve significant amount of the computational work load.
The root of the problem is the vast configurational spaces to be explored - for a periodic system with N atoms there are 3N + 1 dimensions,
making locating the global minimum, or points having similar energy to the global minimum challenging.

Fortunately, many approaches have been developed to tackle this problem. They involves:

- Simulated annealing
- Basin hopping
- Minimum hopping
- Genetic algorithms
- Particle swarm optimisation 
- Random search

A review of modern crystal structure prediction can be found here. 

The word "crystal structure prediction", sometimes also refers to those based on subsituting species in known structures from databases, usually coupled with machine learning.
While they offers essentially cost-free predictions for a given composition, they are mostly applicable to systems that are well studied and have many experimental data available.
While low energy structures for particular composition can be suggested, but there is no guarantee that the true ground state structure is among them, due to the lack of true exploration.  
Nevertheless, when apply to a large number of compositions, they can still provide valuable information of the chemical space.

=========================================================
Ab initio Random Structure Searching - brief introduction
=========================================================


Ab initio random structure searching (AIRSS) [#pickard_2006]_ [#pickard_2011]_ is an approach to search for low energy structure by simply generating random structures, 
followed by local optimisation.
Local optimisation is a relatively simple and mathematically well-established, it found a nearby local minimum in the configuration space by
simply going down-hill in energy.
The potential energy surface (PES) can be divided into many basins-of-attraction. Performing a local optimisation inside a basin would lead
us to bottom of this basin, e.g. the local minimum.

From first glance, such random sampling approach is deemed to fail for complex and high-dimensional configuration space due to the existence
of many high energy local minima, making the chance of landing in the basin of attraction of the global minimum diminishing. 
However, one must not forget that the potential energy surface (PES) is a physical quantity, and hence their structure follow certain rules.
While the number of high energy local minima may be overwhelming, the chance of landing into a basins-of-attraction is proportional to its 
hypervolume, and the lower the energy, the larger the hypervolume, favouring even a random sampler.
In addition, we know that a large portion of the configuration space is not likely to contain any low energy minima - the atoms the bonds 
between them do have well-known finite sizes. 
The region of the PES including atoms very close to each other are unlikely to have any low energy minima, and hence can be excluded from
sampling. Likewise, structures with atoms far apart from each other should also be excluded from sampling.
With a few physical constraints, such as the species-wise minimum separations, including symmetry operations, a simple random search
approach can be made highly efficient for locating the ground state structure and other low energy polymorphs.
While the structures are *randomly* generated, the parameters controlling the generation process are *not randomly chosen* - they are
motivated by physical reasons.

The phrase *ab initio* not only means that this approach  **can** be used with first-principles methods for energy evaluation, 
but also that it **should** be used with them, since it is the physical nature of the PES that is been exploited here.
While random search can be applied with parameterized interatomic potentials, the latter are unlikely to reproduce the true PES especially in the
region far away from fitted phases. Hence, it is not a surprise if random search does not work well in those cases.

A consequence of random sampling is that the computational workload can be made fully parallel and distributed. 
There is no need to coordinate the search as a whole, each worker can work independently little or no inter-communication at all.
In constrast, "global optimisation" methods such as basin hopping, requires each calculation to be performed in serial.
Population based approaches such as genetic algorithms and particle swarm optimisation allow certain degree of parallelism within a single generation (tenth of structures),
but each generation still have to be evaluated iteratively.

This means that for random searching:

- The underlying DFT calculations can be parallelised over only a few CPUs each, maximising the parallel efficiently which otherwise can drop sharply with increasing core counts. 
- The elimination of iterative process means there is no dilemma of *exploration or exploitation*. 
- A further consequence is that the DFT calculations can be performed at relatively low basis set qulaity and accuracy to maximise the speed, usually at several times lower in the cost compared to normal calculations.
- In addition, most structures include and perserv symmetry operations throughout the process, which can be used to speed-up DFT calculations by several folds.


=====================
The ``AIRSS`` package
=====================


The ``AIRSS`` package is a open-source collection of tools and scripts for performing *ab initio* random structure searching (AIRSS) (which confusinly has the same name),
and analysing the results.
The key components of this package includes:

buildcell
  The main work horse for generating structures. This file reads a input *seed* file from stdin and outputs generated structuer in stdout.
  Both input and outputs files are in the CASTEP's ``cell`` format, and the former contains special directives on how the random Structure
  should be generated.

airss.pl
  The main driver script for performing the search. It read command line arguments and performs random structure generation and runs DFT calculations in serial,
  and stop until the specified number of structure has been generated.
  Because the search is embarrsingly parallel, one can just launch as many ``airss.pl`` as they like to occupy all computational resources.
  For example, to sample 800 structure using 128 cores, one can launch 8 ``airss.pl`` script each using 16 cores and sampling 100 structures.
  The result of ``airss.pl`` are saved in the SHELX format with suffix ``res``. 
  These files contains both the crystal structure and the calculated quantities.
  While ``DISP`` does not use this script directly, it is recommanded that the user familiarise themselves with operating ``AIRSS`` using it.

cryan
  A tool to analyse the relaxed structures. It can be used to rank structures according to energy as well as eliminating nearly identical structures
  and extracting species-wise minimum distances.
  It also has many other advanced features as such decomposing a structure into modular units.
 
cabal
  A tool for convert different file formats. It is used internally by various scripts. One very useful feature is to convert file into SHELX format so they
  can be processed by ``cryan``.

castep_relax
  The driver script for performing geometry optimisation using CASTEP. The use of this script is needed because CASTEP defaults to constant-cut off energy
  variable cell optionsation. For high-throughput operation the more traditional constant basis optimisation is more efficeint, but t requires multiple restarts
  to reach convergence. This script does exactly this jobs - it restarts CASTEP relaxation up to defined iterations or until the converged is reached twice in succession.
  This script is used by ``DISP`` to perform CASTEP relaxations.

This package extends the search ability in ``AIRSS`` to allow a client-server based workflow for directing massive parallel search at run time. 
The ``AIRSS`` package must be installed on  **both** the local and the remote machines.
Similar to the ``airss.pl`` script, the ``castep_relax`` script is invoked for relaxation with CASTEP in ``DISP``. 
The output file is stored in the SHELX format that is compatible with the ``cryan`` tool. 
The input and output files used here are aimed to be fully compatible with the original ``AIRSS`` package.



.. [#pickard_2006] Pickard, C. J.; Needs, R. J. High-Pressure Phases of Silane. Phys. Rev. Lett. 2006, 97 (4), 045504. https://doi.org/10.1103/PhysRevLett.97.045504.

.. [#pickard_2011] Pickard, C. J.; Needs, R. J. Ab Initio Random Structure Searching. Journal of physics. Condensed matter : an Institute of Physics journal 2011, 23 (5), 053201–053201. https://doi.org/10.1088/0953-8984/23/5/053201.