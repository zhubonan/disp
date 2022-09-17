"""
Module for analyse CASTEP run time statistics
"""
import re
from collections import namedtuple

import numpy as np

# pylint: disable=import-outside-toplevel


class SCFInfo:
    """Class for storing an extracting information of SCF convergence"""

    SCF_LINE = re.compile(r"^ +([0-9]+) +([+-.E0-9]+) +([+-.E0-9]+) +([+-.E0-9]+) +([.0-9]+) +<-- SCF")
    ScfData = namedtuple("ScfData", ["loops", "energies", "fermi_energies", "gains", "timers"])

    def __init__(self, castep_file):
        """Construct an SCFInfo object given the name of the seed"""
        self.filename = castep_file
        with open(castep_file) as fhandle:
            self.scf_data = self.parse(fhandle)
        self.compute_converge_data()

    def __len__(self):
        return len(self.scf_data)

    def reload(self):
        with open(self.filename) as fhandle:
            self.scf_data = self.parse(fhandle)

    def parse(self, lines):
        """
        Parse SCF loops

        Parse energy/timing for each SCF step.

        Args:
          lines (iteratable): lines to be parsed

        Returns:
          A list of data include all SCF loops
        """
        scf_loops = []
        pattern = self.SCF_LINE
        # Collect all SCF data
        for line in lines:
            match = pattern.match(line)
            if not match:
                continue

            loop = int(match.group(1))
            # Initialise storage space for first cycle
            if loop == 1:
                loops, engs, fermi_engs, gains, timers = [], [], [], [], []
                scf_loops.append(self.ScfData(loops=loops, energies=engs, fermi_energies=fermi_engs, gains=gains, timers=timers))

            loops.append(loop)
            engs.append(float(match.group(2)))
            fermi_engs.append(float(match.group(3)))
            gains.append(float(match.group(4)))
            timers.append(float(match.group(5)))
        return scf_loops

    def compute_converge_data(self):
        """
        Compute summary information about ionic steps
        """
        energies = []
        timmings = []
        durations = []
        steps = []
        avg_scf = []
        for cycle in self.scf_data:
            init_time = cycle.timers[0]
            final_time = cycle.timers[-1]
            duration = final_time - init_time
            energies.append(cycle.energies[-1])
            timmings.append(final_time)
            durations.append(duration)
            steps.append(cycle.loops[-1])
            avg_scf.append(duration / cycle.loops[-1])

        self.conv_data = {"energies": energies, "timimings": timmings, "durations": durations, "steps": steps, "average_scf_time": avg_scf}

    def get_summary(self):
        """Obtain summary information"""
        conv_data = self.conv_data
        output = {
            "avg_ionic_time": np.mean(conv_data["durations"]),
            "avg_elec_time": np.mean(conv_data["average_scf_time"]),
            "avg_elec_steps": np.mean(conv_data["steps"]),
            "ionic_steps": len(conv_data["steps"]),
            "total_time": sum(conv_data["durations"]),
        }
        return output

    def plot_scf(self, scf_no, xaxis="loops", show=True):
        """
        Quick plotting to show a single SCF

        Args:
          scf_no(int): Number of the SCF cycle to be shown
        """
        import matplotlib.pyplot as plt

        data = self.scf_data[scf_no]
        fig, axs = plt.subplots(3, 1, sharex=True)
        xax = getattr(data, xaxis)
        axs[0].set_title(f"SCF Information for cycle {scf_no}")
        axs[0].plot(xax, data.energies)
        axs[0].set_ylabel("Energy (eV)")
        axs[1].plot(xax, data.fermi_energies)
        axs[1].set_ylabel("Fermi Energy (eV)")

        abs_diff = np.abs(np.array(data.gains))
        axs[2].plot(xax, abs_diff)
        axs[2].set_yscale("log")
        axs[2].set_ylabel("Energy change (eV)")
        if show:
            fig.show()

    def plot_conv(self, axs=None, show=True):
        """
        Plot convergence information
        """

        import matplotlib.pyplot as plt

        data = self.conv_data
        if not axs:
            fig, axs = plt.subplots(4, 1, sharex=True, figsize=(7, 8))
        loops = list(range(len(data["steps"])))
        axs[0].plot(loops, data["energies"], "-x", label="Final energy")
        axs[0].set_ylabel("Energy (eV)")
        axs[1].plot(loops, data["durations"], "-x", label="Durations")
        axs[1].set_ylabel("Duration (s)")
        axs[2].plot(loops, data["average_scf_time"], "-x", label="SCF time")
        axs[2].set_ylabel("Avg SCF time (s)")
        axs[3].plot(loops, data["steps"], "-x", label="Electronic steps")
        axs[3].set_ylabel("Electronic Steps")
        axs[3].set_xlabel("Ionic Step")

        if show:
            fig.tight_layout()
            fig.show()
