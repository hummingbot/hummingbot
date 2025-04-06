
import pytest
import importlib

def test_compat_warn():
    with pytest.warns(DeprecationWarning):
        # something else is importing this,
        import cytoolz.compatibility
        # reload to be sure we warn
        importlib.reload(cytoolz.compatibility)
