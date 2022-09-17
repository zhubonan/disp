"""
Tests for the full relax function
"""
import shutil
import tempfile
from pathlib import Path

import pytest

from disp.casteptools import push_cell


def test_push_cell(tmpdir):
    """Test push_cell function"""
    data_folder = Path(__file__).parent / "test_data"
    workdir = tempfile.mkdtemp()
    test_cell = Path(workdir) / "test.cell"
    test_cell_out = Path(workdir) / "test-out.cell"
    shutil.copy(data_folder / "Si2.cell", test_cell)
    shutil.copy(data_folder / "Si2-out.cell", test_cell_out)

    push_cell(test_cell_out, test_cell)
    with open(test_cell) as fhandle:
        text = fhandle.read()

    print(text)
    assert "Si 0.5" in text
    assert "Si 0.0" not in text

    assert "3.009" in text
    assert "3.107231" not in text
    assert "SYMMETRY_GENERATE" in text
