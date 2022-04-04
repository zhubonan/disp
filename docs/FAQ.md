
## Where can I found information about how to use AIRSS?

- [Official source distribution](https://www.mtg.msm.cam.ac.uk/Codes/AIRSS). It contains an example direction with tutorials. Running the tutorials does not need to have a DFT code installed, and can be done on a computer.

- [Official online documentation](https://airss-docs.github.io/). It contains the content of most `examples` comes with the source distribution as well as some additional tutorials.

- [Unofficial documentation (PDF)](https://github.com/kYangLi/airss4vasp/tree/master/doc/AIRSS-0.9.1_manual). However, the official source distribution is recommanded instead of the modified version in that repository.

- The source code itself. If you are not sure about a specific setting, look it up in  the source code, where useful code comments can be often be found nearby.


## Do I have to use CASTEP for DFT relaxation?

This package (`disp`) only supports CASTEP. The latter can be obtained free-of-charge for academic use by signing up the academic license: https://licenses.stfc.ac.uk/product/castep.

In theory, any DFT code (and interatomic potential codes) can be use to relax the structures. The stock `airss.pl` driver script actually support quite a few. 
CASTEP is well tested for running AIRSS search, and its robust electronic and geometry minimisation implementations can benefit calculations with geometries that are far from local minima (e.g. generated random structures).