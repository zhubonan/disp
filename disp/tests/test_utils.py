"""
Testing for Utility module
"""
import pytest

from disp.utils import trim_stream, filter_out_stream
from io import StringIO


@pytest.fixture
def stream():
    text = """
%BLOCK A
FOO
ANG
%ENDBLOCK A

%BLOCK B
BAR
%ENDBLOCK B
"""
    return StringIO(text)


def test_trim(stream):
    """Test trim stream function"""
    out = trim_stream(stream, r'^%BLOCK A', r'^%ENDBLOCK A', ['ANG'])
    out.seek(0)
    res = out.read()
    print(res)
    assert '%BLOCK A' in res
    assert '%ENDBLOCK A' in res
    assert 'ANG' not in res
    assert '%BLOCK B' not in res
    assert '%ENDBLOCK B' not in res


def test_filter(stream):
    """Test filter_out_stream function"""
    out = filter_out_stream(stream, r'^%BLOCK A', r'^%ENDBLOCK A')
    out.seek(0)
    res = out.read()
    print(res)
    assert '%BLOCK B' in res
    assert '%ENDBLOCK B' in res
    assert '%BLOCK A' not in res
