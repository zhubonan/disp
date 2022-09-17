"""
Tools for visualisting SCF convergence
"""

import re

pattern_time = r"""
^\ +
([0-9]+)                      # Loop number
\ +
([+-.E0-9]+)                   # Energy
\ +
([+-.E0-9]+)                   # Fermi Energy
\ +
([+-.E0-9]+)                   # Energy gain per atom
\ +
([.0-9]+)                      # Timer
\ +
<--\ SCF
$
"""

sfc_line = re.compile(pattern_time, re.VERBOSE)


class SCFInfo:
    """Class for storing an extracting information of SCF convergence"""

    def __init__(self, seed):
        """Construct an SCFInfo object given the name of the seed"""
        self.new_cycles = None
        self.scf_data = None
        self.fh = open(seed + ".castep")
        self.parse()

    def __len__(self):
        return len(self.new_cycles)

    def reload(self):
        self.fh.seek(0)
        self.parse()

    def parse(self):
        """parse the castepfile"""
        loops, engs, fermis, gains, timers = [], [], [], [], []
        for line in self.fh:
            match = sfc_line.match(line)
            if match:
                loops.append(int(match.group(1)))
                engs.append(float(match.group(2)))
                fermis.append(float(match.group(3)))
                gains.append(float(match.group(4)))
                timers.append(float(match.group(5)))

        # We check discontinity in loop number
        last = 999999
        break_points = []  # Indices of new SCF cycles
        for i, num in enumerate(loops):
            if num < last:
                break_points.append(i)
            last = num

        self.scf_data = dict(loop=loops, eng=engs, fermi=fermis, gain=gains, time=timers)
        self.new_cycles = break_points

    def get_converge_data(self, scf_no):
        """Return informatino of i th scf minisation"""
        # Check if we are requesting the last index/not using negative indicing
        if scf_no + 1 == 0 or scf_no + 1 == len(self.new_cycles):
            slc = slice(self.new_cycles[scf_no], None)
        else:
            slc = slice(self.new_cycles[scf_no], self.new_cycles[scf_no + 1])

        sliced = {key: value[slc] for key, value in self.scf_data.items()}
        return sliced

    def plot(self, name, scf_no, *pltargs, **pltkwargs):
        """Quick plotting
        name : name of the properties in
        ["timer", "duration", "eng", "fermi", "gain"]
        scf_no : index of the scf_loop

        pltkwargs : kwarges to be passed to pyplot
        """

        # Recurive calling when scf_no is a list/tuple
        if isinstance(scf_no, (list, tuple)):
            for n in scf_no:
                self.plot(name, n, *pltargs, **pltkwargs)
            return

        import matplotlib.pyplot as plt
        import numpy as np

        data = self.get_converge_data(scf_no)

        if name == "duration":
            times = data["time"]
            dura = np.diff(times)
            plt.plot(data["loop"][:-1], dura, label=f"SCF loop {scf_no}", *pltargs, **pltkwargs)
        else:
            plt.plot(data["loop"], data[name], label=f"SCF loop {scf_no}", *pltargs, **pltkwargs)

        # Set up axis labels
        plt.xlabel("SCF Loops")
        if name in ["eng", "fermi", "gain"]:
            plt.ylabel("Energy /eV")
        elif name in ["time", "duration"]:
            plt.ylabel("Seconds")
        plt.title(f"{name} against SCF cycles")
        plt.legend()
        plt.show()
