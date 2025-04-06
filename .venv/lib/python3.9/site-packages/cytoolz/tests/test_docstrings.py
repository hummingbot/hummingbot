import difflib
import cytoolz

from cytoolz import curry, identity, keyfilter, valfilter, merge_with
from cytoolz.utils import raises
from dev_skip_test import dev_skip_test


# `cytoolz` functions for which "# doctest: +SKIP" were added.
# This may have been done because the error message may not exactly match.
# The skipped tests should be added below with results and explanations.
skipped_doctests = ['get_in']


@curry
def isfrommod(modname, func):
    mod = getattr(func, '__module__', '') or ''
    return mod.startswith(modname) or 'toolz.functoolz.curry' in str(type(func))


def convertdoc(doc):
    """ Convert docstring from `toolz` to `cytoolz`."""
    if hasattr(doc, '__doc__'):
        doc = doc.__doc__
    doc = doc.replace('toolz', 'cytoolz')
    doc = doc.replace('dictcytoolz', 'dicttoolz')
    doc = doc.replace('funccytoolz', 'functoolz')
    doc = doc.replace('itercytoolz', 'itertoolz')
    doc = doc.replace('cytoolz.readthedocs', 'toolz.readthedocs')
    return doc


@dev_skip_test
def test_docstrings_uptodate():
    import toolz
    differ = difflib.Differ()

    # only consider items created in both `toolz` and `cytoolz`
    toolz_dict = valfilter(isfrommod('toolz'), toolz.__dict__)
    cytoolz_dict = valfilter(isfrommod('cytoolz'), cytoolz.__dict__)

    # only test functions that have docstrings defined in `toolz`
    toolz_dict = valfilter(lambda x: getattr(x, '__doc__', ''), toolz_dict)

    # full API coverage should be tested elsewhere
    toolz_dict = keyfilter(lambda x: x in cytoolz_dict, toolz_dict)
    cytoolz_dict = keyfilter(lambda x: x in toolz_dict, cytoolz_dict)

    d = merge_with(identity, toolz_dict, cytoolz_dict)
    for key, (toolz_func, cytoolz_func) in d.items():
        # only check if the new doctstring *contains* the expected docstring
        # in Python < 3.13 the second line is indented, in 3.13+
        # it is not, strip all lines to fudge it
        toolz_doc = "\n".join((line.strip() for line in convertdoc(toolz_func).splitlines()))
        cytoolz_doc = "\n".join((line.strip() for line in cytoolz_func.__doc__.splitlines()))
        if toolz_doc not in cytoolz_doc:
            diff = list(differ.compare(toolz_doc.splitlines(),
                                       cytoolz_doc.splitlines()))
            fulldiff = list(diff)
            # remove additional lines at the beginning
            while diff and diff[0].startswith('+'):
                diff.pop(0)
            # remove additional lines at the end
            while diff and diff[-1].startswith('+'):
                diff.pop()

            def checkbad(line):
                return (line.startswith('+') and
                        not ('# doctest: +SKIP' in line and
                             key in skipped_doctests))

            if any(map(checkbad, diff)):
                assert False, 'Error: cytoolz.%s has a bad docstring:\n%s\n' % (
                    key, '\n'.join(fulldiff))


def test_get_in_doctest():
    # Original doctest:
    #     >>> get_in(['y'], {}, no_default=True)
    #     Traceback (most recent call last):
    #         ...
    #     KeyError: 'y'

    # cytoolz result:
    #     KeyError:

    raises(KeyError, lambda: cytoolz.get_in(['y'], {}, no_default=True))
