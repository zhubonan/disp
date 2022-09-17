"""
Guarded GULP
"""
import sys

import click

from disp.gulptools import guarded_gulp


@click.command("ggulp")
@click.option("--gulp-exe", "-exe", default="gulp", help="Name of the GULP executable")
def main(gulp_exe):
    """Guard GULP and terminate it if necessary"""

    run_ok = guarded_gulp(gulp_exe)
    if run_ok is False:
        sys.exit(255)
