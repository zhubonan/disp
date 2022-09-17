"""
Collection of useful tools
"""
from json import dumps, load
from pathlib import Path

import click
from ase.io import read

from disp.tools.modcell import modify_cell
from disp.tools.sheapio import (
    SheapOut,
    parse_sheap_output,
    sheap_to_dict,
)

# pylint: disable=import-outside-toplevel


@click.group("tools")
@click.pass_context
def tools(ctx):
    """Collection of tools"""
    _ = ctx


@tools.command("modcell")
@click.argument("base_cell")
@click.argument("other_cell")
def modcell(base_cell, other_cell):
    """Modify the structure of a CELL file using another"""
    click.echo("\n".join(modify_cell(base_cell, read(other_cell))))


@tools.command("sheap2json")
@click.argument("sheapout")
@click.argument("path")
def cmd_sheap2json(sheapout, path):
    """Convert output from SHEAP to chemiscope format including the structures.

    The results is printed to the STDOUT
    """
    with open(sheapout) as handle:
        parsed_data = parse_sheap_output(handle)

    outdict = sheap_to_dict(parsed_data, path)

    # Include mapping settings
    map_dict = {
        "x": {"property": "sheap1"},
        "y": {"property": "sheap2"},
        "color": {"max": min(parsed_data.enthalpy) + 0.5, "min": min(parsed_data.enthalpy), "property": "energy", "scale": "linear"},
        "size": {"factor": 20, "mode": "linear", "property": "size", "reverse": False},
    }
    settings = {
        "map": map_dict,
        "structure": [
            {
                "bonds": True,
                "spaceFilling": False,
                "atomLabels": False,
                "unitCell": True,
                "rotation": False,
                "supercell": {"0": 2, "1": 2, "2": 2},
                "axes": "off",
                "keepOrientation": False,
                "environments": {"activated": True, "bgColor": "grey", "bgStyle": "ball-stick", "center": True, "cutoff": 0},
            }
        ],
    }
    outdict["settings"] = settings
    click.echo(dumps(outdict))


@tools.command("plot-sheap")
@click.argument("sheapout")
@click.option("--vmax", help="Color scale maximum relative to the minimum value", default=0.25)
@click.option("--savename", default="sheap-map.pdf")
@click.option("--plot/--no-plot", default=True)
def plot_sheap(sheapout, vmax, savename, plot):
    """
    Plot the output of SHEAP as spheres, respecting the specification of radius output.
    """
    import matplotlib.cm as cm
    import matplotlib.pyplot as plt
    import numpy as np

    if "json" in sheapout:
        with open(sheapout) as handle:
            parsed = SheapOut(**load(handle))
    else:
        with open(sheapout) as handle:
            parsed = parse_sheap_output(handle)
    coords = np.array(parsed.coords)
    radius = np.array(parsed.radius)

    # Plot the output
    fig, axes = plt.subplots(1, 1)
    axes.set_aspect("equal")

    # Compute the colours
    cmap = plt.get_cmap()
    emin = min(parsed.enthalpy)
    emax = emin + vmax
    norm = plt.Normalize(emin, emax)

    for i, coord in enumerate(coords):
        axes.add_patch(plt.Circle(coord, radius=radius[i], facecolor=cmap(norm(parsed.enthalpy[i]))))
    xmin, xmax = coords[:, 0].min(), coords[:, 0].max()
    ymin, ymax = coords[:, 1].min(), coords[:, 1].max()
    axes.set_xlim(min(xmin, ymin) - 0.1, max(xmax, ymax) + 0.1)
    axes.set_ylim(min(xmin, ymin) - 0.1, max(xmax, ymax) + 0.1)
    plt.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap))
    if plot:
        plt.show()
    fig.savefig(savename, dpi=200)
    # Save the raw data as json
    Path(savename).with_suffix(".json").write_text(dumps(parsed._asdict()))
