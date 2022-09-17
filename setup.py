#!/usr/bin/env python

from pathlib import Path

from setuptools import find_packages, setup

_version = "1.0.0"

MODULE_PATH = Path(__file__).parent

if __name__ == "__main__":

    with open(MODULE_PATH / "README.md") as fh:
        readme_content = fh.read()
    setup(
        name="disp",
        author="Bonan Zhu",
        author_email="zhubonan@outlook.com",
        description="Distributed structure prediction",
        long_description_content_type="text/markdown",
        long_description=readme_content,
        version=_version,
        install_requires=[
            "fireworks>=1.9.5",
            "numpy>=1.13",
            "click",
            "spglib",
            "ase",
            "pandas",
            "pytest",
            "mongoengine==0.20.0",
            "mongomock==3.20.0",
        ],
        extras_require={"vasp": ["atomate"], "doc": ["sphinx", "sphinx-rtd-theme"]},
        packages=find_packages(),
        entry_points={
            "console_scripts": ["ggulp=disp.cli.cmd_ggulp:main", "disp=disp.cli.cmd_disp:main", "trlaunch=disp.cli.trlaunch:trlaunch"]
        },
    )
