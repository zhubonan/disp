from pathlib import Path
import pytest

MODULE_DIR = Path(__file__).parent
DATA_DIR = MODULE_DIR / 'test_data'

@pytest.fixture
def get_data_dir():
    """Get the directory containing test data"""
    def _get_data_dir(name):
        """Return the Path pointing to the test data"""
        return DATA_DIR / name

    return _get_data_dir

