"""
Testing SCF tools
"""

import os

from disp.scftools import SCFInfo

fpath, fname = os.path.split(__file__)
spt_dir = os.path.join(fpath, "test_data")


def test_scf_read():
    seed = os.path.join(spt_dir, "LFO")
    scf = SCFInfo(seed)
    assert scf.new_cycles[0] == 0
    conv = scf.get_converge_data(-1)
    assert conv["loop"][0] == 1
    assert conv["eng"][0] == -3.15500957e003
    assert conv["eng"][-1] == -3.25246274e003
    assert conv["time"][-1] == 8.75
    # Checking both indexing
    assert conv == scf.get_converge_data(0)
