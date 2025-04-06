from cytoolz.utils import consume, raises


def test_raises():
    assert raises(ZeroDivisionError, lambda: 1 / 0)
    assert not raises(ZeroDivisionError, lambda: 1)


def test_consume():
    l = [1, 2, 3]
    assert consume(l) is None
    il = iter(l)
    assert consume(il) is None
    assert raises(StopIteration, lambda: next(il))
    assert raises(TypeError, lambda: consume(1))
