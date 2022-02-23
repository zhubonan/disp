"""
Tools for working with GULP
"""
import re
from collections import namedtuple
import subprocess
import sys

Ginfo = namedtuple('Ginfo', ['cycle', 'energy', 'gnorm', 'cpu'])

GEOM_LINE_PATTERN = re.compile(
    r'^ +Cycle:([ 0-9]+)Energy:([-0-9e*. ]+)Gnorm:([-0-9e*. ]+)CPU:([-0-9e. ]+)'
)


def gemo_opt_progress(gfile):
    """Parse Geometry optimisation info in GULP output file"""

    if isinstance(gfile, str):
        with open(gfile) as fhandle:
            fcontent = fhandle.readlines()
    else:
        fcontent = gfile

    data = []
    for line in fcontent:
        match = GEOM_LINE_PATTERN.match(line)
        if match:
            data.append(Ginfo(*[match.group(i).strip() for i in range(1, 5)]))

    return data


def check_gulp(gfile):
    """Check if GULP is progressing well"""

    gopt = gemo_opt_progress(gfile)
    # Check for the existing of the **** entries
    gnorms = []
    for entry in gopt:
        if '*' in entry.energy or '*' in entry.gnorm:
            return False
        gnorms.append(float(entry.gnorm))

        # Check whether Gnorms are getting unphysically large
        if len(gnorms) > 5 and gnorms[-1] > 10:
            if gnorms[-1] > gnorms[-4]:
                return False

    return True


def guarded_gulp(exe='gulp'):
    """
    A python function that help running GULP

    Check the progress of GULP while it runs, the GULP program
    will be terminated if the energy or Gnorm becomes *****
    """

    proc = subprocess.Popen([exe],
                            stdin=sys.stdin,
                            stdout=subprocess.PIPE,
                            universal_newlines=True)

    run_ok = True
    data_lines = []
    while proc.poll() is None:
        new_line = proc.stdout.readline()
        print(new_line, end='')
        data_lines.append(new_line)
        # Check if we are OK so far
        run_ok = check_gulp(data_lines)
        if run_ok is False:
            proc.terminate()
    # Print the rest of the stdout
    print(proc.stdout.read(), end='')
    sys.stdout.flush()

    return run_ok
