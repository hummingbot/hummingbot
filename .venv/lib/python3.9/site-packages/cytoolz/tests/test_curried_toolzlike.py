import cytoolz
import cytoolz.curried
import types
from dev_skip_test import dev_skip_test


# Note that the tests in this file assume `toolz.curry` is a class, but we
# may some day make `toolz.curry` a function and `toolz.Curry` a class.

@dev_skip_test
def test_toolzcurry_is_class():
    import toolz
    assert isinstance(toolz.curry, type) is True
    assert isinstance(toolz.curry, types.FunctionType) is False


@dev_skip_test
def test_cytoolz_like_toolz():
    import toolz
    import toolz.curried
    for key, val in vars(toolz.curried).items():
        if isinstance(val, toolz.curry):
            if val.func is toolz.curry:  # XXX: Python 3.4 work-around!
                continue
            assert hasattr(cytoolz.curried, key), (
                    'cytoolz.curried.%s does not exist' % key)
            assert isinstance(getattr(cytoolz.curried, key), cytoolz.curry), (
                    'cytoolz.curried.%s should be curried' % key)


@dev_skip_test
def test_toolz_like_cytoolz():
    import toolz
    import toolz.curried
    for key, val in vars(cytoolz.curried).items():
        if isinstance(val, cytoolz.curry):
            assert hasattr(toolz.curried, key), (
                    'cytoolz.curried.%s should not exist' % key)
            assert isinstance(getattr(toolz.curried, key), toolz.curry), (
                    'cytoolz.curried.%s should not be curried' % key)
