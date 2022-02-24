# Installation and setup

A working setup of
[fireworks](https://materialsproject.github.io/fireworks/) is needed for
using this pacakge. This typically includes setting up a MongoDB server
that is both accessible by the local computer and the remote clusters
(compute nodes). The python
[fireworks](https://materialsproject.github.io/fireworks/) package needs
to be installed on both the local and the remote computers as well. The
MongoDB for managing the workflows is also used as a centralised
repository for holding the structure found by the search. Please refer
to the documentation of
[fireworks](https://materialsproject.github.io/fireworks/) for how to
setup it up.

As the MongoDB server also serves as a central storage for generated and
relaxed structures, sufficient storage space should be available to use.
Although usually the structure files (SHELX) format take relatively
small spaces.

The open sourced [AIRSS](https://www.mtg.msm.cam.ac.uk/Codes/AIRSS)
package also needs to be compiled and installed on both the remote and
local computers. This is necessary so that random structure can be
built, and its scripts shipped for running CASTEP calculations and
converting the results are needed as well.

Once the above is done, the DISP package can be installed using

``` none
pip install git+https://https://github.com/zhubonan/DISP
```

This will install the package with its dependencies. After this the
command `disp` will be available to use.
