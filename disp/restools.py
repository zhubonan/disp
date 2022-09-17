"""module for minipulating res file"""
import io
import logging
import os

from ase.io import write

logger = logging.getLogger(__name__)


def extract_res(fname):
    """Extract information from res file"""
    rems = []
    with open(fname) as fh:
        for line in fh:
            if "TITL" in line:
                title = line.strip()
            if "REM" in line:
                rems.append(line.replace("REM", "").strip())
            # Break when data starts
            if "cell" in line:
                break
    entries = title.split()
    if len(entries) < 9:
        logger.warning(f"Bad res file {fname}")
        return None
    res = {}
    res["rem"] = rems
    res["uid"] = entries[1]
    res["P"] = float(entries[2])
    res["V"] = float(entries[3])
    res["H"] = float(entries[4])
    res["nat"] = int(entries[7])
    res["sym"] = entries[8]
    res["fname"] = fname
    return res


def save_airss_res(atoms, info_dict, fname=None, force_write=False):
    """
    Save the rusult of a sucessful airss run in the res file
    """

    # Prepare output file
    if fname is None:
        fname = info_dict["uid"] + ".res"
    if os.path.isfile(fname) and not force_write:
        raise FileExistsError("Switch on force_write to overwrite existing files")
    else:
        fout = open(fname, "w")

    P, V, H = info_dict["P"], info_dict["V"], info_dict["H"]
    # Get number of atoms, spin
    nat, sg = info_dict["nat"], info_dict["sym"]
    # Construct title line
    PVH = f" {P:.3f} {V:.3f} {H:.6f} "
    title = "TITL " + info_dict["uid"] + " " + PVH + " 0 " + " 0 " + " " + str(nat) + " " + sg + " n - 1\n"

    # Write to the top of res file
    restmp = info_dict["uid"] + ".rtmp"
    write(restmp, atoms, format="res")
    resin = open(restmp)
    resout = io.StringIO()
    resout.write(title)

    if "rem" in info_dict:
        rems = info_dict["rem"]
        for line in rems:
            print("REM " + line, file=resout)

    # Write the rest of the lines
    resin.readline()
    for line in resin:
        resout.write(line)
    resin.close()
    os.remove(restmp)

    resout.seek(0)
    for line in resout:
        fout.write(line)
    fout.close()
    resout.close()
    return
