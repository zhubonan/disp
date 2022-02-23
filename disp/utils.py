"""
Utility Module - contains useful routines
"""
import re
import io
import numpy as np


def trim_stream(stream, start, end, extra_remove=None):
    """
    Select an portion of a stream, return the portion without lines
    matched with extra_remove keywords
    Return a StringIO object
    """
    out_stream = io.StringIO()
    record = False
    stream.seek(0)
    if extra_remove is None:
        extra_remove = []
    for line in stream:
        if re.match(start, line, re.IGNORECASE):
            record = True
        # filter out the lines with ANG and 'FIX_VOL'
        if record is True:
            # Apply to filter, if there is the keyword then
            appear = False
            for i in extra_remove:
                if i in line:
                    appear = True
                    break
            # Only write when there is no match
            if appear is not True:
                out_stream.write(line)
            else:
                continue
        # Trun recording off at the end of line
        if re.match(end, line, re.IGNORECASE):
            break
    # Reset
    stream.seek(0)
    out_stream.seek(0)
    return out_stream


def filter_out_stream(stream, start, end):
    """
    Opposite of trim_streamm, only the portion outside start end is selected
    Return a StringIO object
    """
    out_stream = io.StringIO()
    record = True
    stream.seek(0)
    for line in stream:
        if re.match(start, line, re.IGNORECASE):
            record = False
        # filter out the lines with ANG and 'FIX_VOL'
        if record is True:
            out_stream.write(line)
        # Trun recording off at the end of line
        if re.match(end, line, re.IGNORECASE):
            record = True
    # Reset
    stream.seek(0)
    out_stream.seek(0)
    return out_stream


def calc_kpt_tuple_recip(structure, mp_spacing=0.05, rounding='up'):
    """Calculate reciprocal-space sampling with real-space parameter"""

    # Get reciprocal lattice vectors with pymatgen. Note that pymatgen does include
    # the 2*pi factor used in many definitions of these vectors; hence it is divided by 2pi for the
    # CASTEP convention
    recip_cell = structure.lattice.reciprocal_lattice.matrix / np.pi / 2

    # Get reciprocal cell vector magnitudes according to Pythagoras' theorem
    abc_recip = np.sqrt(np.sum(np.square(recip_cell), 1))
    k_samples = abc_recip / mp_spacing

    # Rounding
    if rounding == 'up':
        k_samples = np.ceil(k_samples)
    else:
        k_samples = np.floor(k_samples + 0.5)
    return tuple((int(x) for x in k_samples))
