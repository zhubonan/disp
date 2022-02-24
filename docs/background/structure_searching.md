# Crystal Structure Prediction {#crystal_structure_prediction}

The structure of the material is essential in order to carry out any
materials modelling work. Very often, this information has to be
obtained experimentally in the first place, or a reasonable guess must
be performed. For example, if one want to compute the band structure of
TiO2 using DFT, the crystal structure of that particular TiO2 polymorph
(and there are many of them) is needed as the input. However, what if
one want to model materials that has not been synthesised? Or perhaps
looking for other polymorphs of the same composition that can
potentailly have different properties?

Crystal structure prediction is the process of predicting the crystal
structure of materials from no or limited experimental data. Quantum
mechanics based first-principles calculations allow accurate
energy/force/stress to be determined for any given atomic structure.
Using these techniques, in theory, one can just type in the formula and
the computer should be able to output the experimental crystal
structure(s). This, however, turned out to be not so trivial and may
involve significant amount of the computational work load. The root of
the problem is the vast configurational spaces to be explored - for a
periodic system with N atoms there are 3N + 1 dimensions, making
locating the global minimum, or points having similar energy to the
global minimum challenging.

Fortunately, many approaches have been developed to tackle this problem.

-   Simulated annealing
-   Basin hopping
-   Minimum hopping
-   Genetic algorithms
-   Particle swarm optimisation
-   Random search

The word \"crystal structure prediction\", sometimes also refers to
those based on subsituting species in known structures from databases,
usually coupled with machine learning. While they offers essentially
cost-free predictions for a given composition, they are mostly
applicable to systems that are well studied and have many experimental
data available. While low energy structures for particular composition
can be suggested, but there is no guarantee that the true ground state
structure is among them, due to the lack of true exploration.
Nevertheless, when apply to a large number of compositions, they can
still provide valuable information of the chemical space.

# Ab initio Random Structure Searching - brief introduction

Ab initio random structure searching (AIRSS)[^1][^2] is an approach to
search for low energy structure by simply generating random structures,
followed by local optimisation. Local optimisation is a relatively
simple and mathematically well-established, it found a nearby local
minimum in the configuration space by simply going down-hill in energy.
The potential energy surface (PES) can be divided into many
basins-of-attraction. Performing a local optimisation inside a basin
would lead us to bottom of this basin, e.g. the local minimum.

From first glance, such random sampling approach is deemed to fail for
complex and high-dimensional configuration space due to the existence of
many high energy local minima, making the chance of landing in the basin
of attraction of the global minimum diminishing. However, one must not
forget that the potential energy surface (PES) is a physical quantity,
and hence their structure follow certain rules. While the number of high
energy local minima may be overwhelming, the chance of landing into a
basins-of-attraction is proportional to its hypervolume, and the lower
the energy, the larger the hypervolume, favouring even a random sampler.
In addition, we know that a large portion of the configuration space is
not likely to contain any low energy minima - the atoms the bonds
between them do have well-known finite sizes. The region of the PES
including atoms very close to each other are unlikely to have any low
energy minima, and hence can be excluded from sampling. Likewise,
structures with atoms far apart from each other should also be excluded
from sampling. With a few physical constraints, such as the species-wise
minimum separations, including symmetry operations, a simple random
search approach can be made highly efficient for locating the ground
state structure and other low energy polymorphs. While the structures
are *randomly* generated, the parameters controlling the generation
process are *not randomly chosen* - they are motivated by physical
reasons.

The phrase *ab initio* not only means that this approach **can** be used
with first-principles methods for energy evaluation, but also that it
**should** be used with them, since it is the physical nature of the PES
that is been exploited here. While random search can be applied with
parameterized interatomic potentials, the latter are unlikely to
reproduce the true PES especially in the region far away from fitted
phases. Hence, it is not a surprise if random search does not work well
in those cases.

A consequence of random sampling is that the computational workload can
be made fully parallel and distributed. There is no need to coordinate
the search as a whole, each worker can work independently little or no
inter-communication at all. In constrast, \"global optimisation\"
methods such as basin hopping, requires each calculation to be performed
in serial. Population based approaches such as genetic algorithms and
particle swarm optimisation allow certain degree of parallelism within a
single generation (tenth of structures), but each generation still have
to be evaluated iteratively.

This means that for random searching:

-   The underlying DFT calculations can be parallelised over only a few
    CPUs each, maximising the parallel efficiently which otherwise can
    drop sharply with increasing core counts.
-   The elimination of iterative process means there is no dilemma of
    *exploration or exploitation*.
-   A further consequence is that the DFT calculations can be performed
    at relatively low basis set qulaity and accuracy to maximise the
    speed, usually at several times lower in the cost compared to normal
    calculations.
-   In addition, most structures include and perserv symmetry operations
    throughout the process, which can be used to speed-up DFT
    calculations by several folds.

[^1]: Pickard, C. J.; Needs, R. J. High-Pressure Phases of Silane. Phys.
    Rev. Lett. 2006, 97 (4), 045504.
    <https://doi.org/10.1103/PhysRevLett.97.045504>.

[^2]: Pickard, C. J.; Needs, R. J. Ab Initio Random Structure Searching.
    Journal of physics. Condensed matter : an Institute of Physics
    journal 2011, 23 (5), 053201--053201.
    <https://doi.org/10.1088/0953-8984/23/5/053201>.
