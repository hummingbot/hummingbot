import doctest

import cytoolz
import cytoolz.dicttoolz
import cytoolz.functoolz
import cytoolz.itertoolz
import cytoolz.recipes


def module_doctest(m, *args, **kwargs):
    return doctest.testmod(m, *args, **kwargs).failed == 0


def test_doctest():
    assert module_doctest(cytoolz)
    assert module_doctest(cytoolz.dicttoolz)
    assert module_doctest(cytoolz.functoolz)
    assert module_doctest(cytoolz.itertoolz)
    assert module_doctest(cytoolz.recipes)
