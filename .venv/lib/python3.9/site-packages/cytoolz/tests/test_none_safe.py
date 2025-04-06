""" Test that functions are reasonably behaved with None as input.

Typed Cython objects (like dict) may also be None.  Using functions from
Python's C API that expect a specific type but receive None instead can cause
problems such as throwing an uncatchable SystemError (and some systems may
segfault instead).  We obviously don't what that to happen!  As the tests
below discovered, this turned out to be a rare occurence.  The only changes
required were to use `d.copy()` instead of `PyDict_Copy(d)`, and to always
return Python objects from functions instead of int or bint (so exceptions
can propagate).

The vast majority of functions throw TypeError.  The vast majority of
functions also behave the same in `toolz` and `cytoolz`.  However, there
are a few minor exceptions.  Since passing None to functions are edge cases
that don't have well-established behavior yet (other than raising TypeError),
the tests in this file serve to verify that the behavior is at least
reasonably well-behaved and don't cause SystemErrors.

"""
# XXX: This file could be back-ported to `toolz` once unified testing exists.
import cytoolz
from cytoolz import *
from cytoolz.utils import raises
from operator import add


class GenException(object):
    def __init__(self, exc):
        self.exc = exc

    def __iter__(self):
        return self

    def __next__(self):
        raise self.exc

    def next(self):
        raise self.exc


def test_dicttoolz():
    tested = []
    assert raises((TypeError, AttributeError), lambda: assoc(None, 1, 2))
    tested.append('assoc')

    assert raises((TypeError, AttributeError), lambda: dissoc(None, 1))
    tested.append('dissoc')

    # XXX
    assert (raises(TypeError, lambda: get_in(None, {})) or
            get_in(None, {}) is None)

    assert raises(TypeError, lambda: get_in(None, {}, no_default=True))
    assert get_in([0, 1], None) is None
    assert raises(TypeError, lambda: get_in([0, 1], None, no_default=True))
    tested.append('get_in')

    assert raises(TypeError, lambda: keyfilter(None, {1: 2}))
    assert raises((AttributeError, TypeError), lambda: keyfilter(identity, None))
    tested.append('keyfilter')

    # XXX
    assert (raises(TypeError, lambda: keymap(None, {1: 2})) or
            keymap(None, {1: 2}) == {(1,): 2})
    assert raises((AttributeError, TypeError), lambda: keymap(identity, None))
    tested.append('keymap')

    assert raises(TypeError, lambda: merge(None))
    assert raises((TypeError, AttributeError), lambda: merge(None, None))
    tested.append('merge')

    assert raises(TypeError, lambda: merge_with(None, {1: 2}, {3: 4}))
    assert raises(TypeError, lambda: merge_with(identity, None))
    assert raises((TypeError, AttributeError),
                  lambda: merge_with(identity, None, None))
    tested.append('merge_with')

    assert raises(TypeError, lambda: update_in({1: {2: 3}}, [1, 2], None))
    assert raises(TypeError, lambda: update_in({1: {2: 3}}, None, identity))
    assert raises((TypeError, AttributeError),
                  lambda:  update_in(None, [1, 2], identity))
    tested.append('update_in')

    assert raises(TypeError, lambda: valfilter(None, {1: 2}))
    assert raises((AttributeError, TypeError), lambda: valfilter(identity, None))
    tested.append('valfilter')

    # XXX
    assert (raises(TypeError, lambda: valmap(None, {1: 2})) or
            valmap(None, {1: 2}) == {1: (2,)})
    assert raises((AttributeError, TypeError), lambda: valmap(identity, None))
    tested.append('valmap')

    assert (raises(TypeError, lambda: itemmap(None, {1: 2})) or
            itemmap(None, {1: 2}) == {1: (2,)})
    assert raises((AttributeError, TypeError), lambda: itemmap(identity, None))
    tested.append('itemmap')

    assert raises(TypeError, lambda: itemfilter(None, {1: 2}))
    assert raises((AttributeError, TypeError), lambda: itemfilter(identity, None))
    tested.append('itemfilter')

    assert raises((AttributeError, TypeError), lambda: assoc_in(None, [2, 2], 3))
    assert raises(TypeError, lambda: assoc_in({}, None, 3))
    tested.append('assoc_in')

    s1 = set(tested)
    s2 = set(cytoolz.dicttoolz.__all__)
    assert s1 == s2, '%s not tested for being None-safe' % ', '.join(s2 - s1)


def test_functoolz():
    tested = []
    assert raises(TypeError, lambda: complement(None)())
    tested.append('complement')

    assert compose(None) is None
    assert raises(TypeError, lambda: compose(None, None)())
    tested.append('compose')

    assert compose_left(None) is None
    assert raises(TypeError, lambda: compose_left(None, None)())
    tested.append('compose_left')

    assert raises(TypeError, lambda: curry(None))
    tested.append('curry')

    assert raises(TypeError, lambda: do(None, 1))
    tested.append('do')

    assert identity(None) is None
    tested.append('identity')

    assert raises(TypeError, lambda: juxt(None))
    assert raises(TypeError, lambda: list(juxt(None, None)()))
    tested.append('juxt')

    assert memoize(identity, key=None)(1) == 1
    assert memoize(identity, cache=None)(1) == 1
    tested.append('memoize')

    assert raises(TypeError, lambda: pipe(1, None))
    tested.append('pipe')

    assert thread_first(1, None) is None
    tested.append('thread_first')

    assert thread_last(1, None) is None
    tested.append('thread_last')

    assert flip(lambda a, b: (a, b))(None)(None) == (None, None)
    tested.append('flip')

    assert apply(identity, None) is None
    assert raises(TypeError, lambda: apply(None))
    tested.append('apply')

    excepts(None, lambda x: x)
    excepts(TypeError, None)
    tested.append('excepts')

    s1 = set(tested)
    s2 = set(cytoolz.functoolz.__all__)
    assert s1 == s2, '%s not tested for being None-safe' % ', '.join(s2 - s1)


def test_itertoolz():
    tested = []
    assert raises(TypeError, lambda: list(accumulate(None, [1, 2])))
    assert raises(TypeError, lambda: list(accumulate(identity, None)))
    tested.append('accumulate')

    assert raises(TypeError, lambda: concat(None))
    assert raises(TypeError, lambda: list(concat([None])))
    tested.append('concat')

    assert raises(TypeError, lambda: list(concatv(None)))
    tested.append('concatv')

    assert raises(TypeError, lambda: list(cons(1, None)))
    tested.append('cons')

    assert raises(TypeError, lambda: count(None))
    tested.append('count')

    # XXX
    assert (raises(TypeError, lambda: list(drop(None, [1, 2]))) or
            list(drop(None, [1, 2])) == [1, 2])

    assert raises(TypeError, lambda: list(drop(1, None)))
    tested.append('drop')

    assert raises(TypeError, lambda: first(None))
    tested.append('first')

    assert raises(TypeError, lambda: frequencies(None))
    tested.append('frequencies')

    assert raises(TypeError, lambda: get(1, None))
    assert raises(TypeError, lambda: get([1, 2], None))
    tested.append('get')

    assert raises(TypeError, lambda: groupby(None, [1, 2]))
    assert raises(TypeError, lambda: groupby(identity, None))
    tested.append('groupby')

    assert raises(TypeError, lambda: list(interleave(None)))
    assert raises(TypeError, lambda: list(interleave([None, None])))
    assert raises(TypeError,
                  lambda: list(interleave([[1, 2], GenException(ValueError)],
                                          pass_exceptions=None)))
    tested.append('interleave')

    assert raises(TypeError, lambda: list(interpose(1, None)))
    tested.append('interpose')

    assert raises(TypeError, lambda: isdistinct(None))
    tested.append('isdistinct')

    assert isiterable(None) is False
    tested.append('isiterable')

    assert raises(TypeError, lambda: list(iterate(None, 1)))
    tested.append('iterate')

    assert raises(TypeError, lambda: last(None))
    tested.append('last')

    # XXX
    assert (raises(TypeError, lambda: list(mapcat(None, [[1], [2]]))) or
            list(mapcat(None, [[1], [2]])) == [[1], [2]])
    assert raises(TypeError, lambda: list(mapcat(identity, [None, [2]])))
    assert raises(TypeError, lambda: list(mapcat(identity, None)))
    tested.append('mapcat')

    assert raises(TypeError, lambda: list(merge_sorted(None, [1, 2])))
    tested.append('merge_sorted')

    assert raises(TypeError, lambda: nth(None, [1, 2]))
    assert raises(TypeError, lambda: nth(0, None))
    tested.append('nth')

    assert raises(TypeError, lambda: partition(None, [1, 2, 3]))
    assert raises(TypeError, lambda: partition(1, None))
    tested.append('partition')

    assert raises(TypeError, lambda: list(partition_all(None, [1, 2, 3])))
    assert raises(TypeError, lambda: list(partition_all(1, None)))
    tested.append('partition_all')

    assert raises(TypeError, lambda: list(pluck(None, [[1], [2]])))
    assert raises(TypeError, lambda: list(pluck(0, [None, [2]])))
    assert raises(TypeError, lambda: list(pluck(0, None)))
    tested.append('pluck')

    assert raises(TypeError, lambda: reduceby(None, add, [1, 2, 3], 0))
    assert raises(TypeError, lambda: reduceby(identity, None, [1, 2, 3], 0))
    assert raises(TypeError, lambda: reduceby(identity, add, None, 0))
    tested.append('reduceby')

    assert raises(TypeError, lambda: list(remove(None, [1, 2])))
    assert raises(TypeError, lambda: list(remove(identity, None)))
    tested.append('remove')

    assert raises(TypeError, lambda: second(None))
    tested.append('second')

    # XXX
    assert (raises(TypeError, lambda: list(sliding_window(None, [1, 2, 3]))) or
            list(sliding_window(None, [1, 2, 3])) == [])
    assert raises(TypeError, lambda: list(sliding_window(1, None)))
    tested.append('sliding_window')

    # XXX
    assert (raises(TypeError, lambda: list(take(None, [1, 2])) == [1, 2]) or
            list(take(None, [1, 2])) == [1, 2])
    assert raises(TypeError, lambda: list(take(1, None)))
    tested.append('take')

    # XXX
    assert (raises(TypeError, lambda: list(tail(None, [1, 2])) == [1, 2]) or
            list(tail(None, [1, 2])) == [1, 2])
    assert raises(TypeError, lambda: list(tail(1, None)))
    tested.append('tail')

    # XXX
    assert (raises(TypeError, lambda: list(take_nth(None, [1, 2]))) or
            list(take_nth(None, [1, 2])) == [1, 2])
    assert raises(TypeError, lambda: list(take_nth(1, None)))
    tested.append('take_nth')

    assert raises(TypeError, lambda: list(unique(None)))
    assert list(unique([1, 1, 2], key=None)) == [1, 2]
    tested.append('unique')

    assert raises(TypeError, lambda: join(first, None, second, (1, 2, 3)))
    assert raises(TypeError, lambda: join(first, (1, 2, 3), second, None))
    tested.append('join')

    assert raises(TypeError, lambda: topk(None, [1, 2, 3]))
    assert raises(TypeError, lambda: topk(3, None))
    tested.append('topk')

    assert raises(TypeError, lambda: list(diff(None, [1, 2, 3])))
    assert raises(TypeError, lambda: list(diff(None)))
    assert raises(TypeError, lambda: list(diff([None])))
    assert raises(TypeError, lambda: list(diff([None, None])))
    tested.append('diff')

    assert raises(TypeError, lambda: peek(None))
    tested.append('peek')

    assert raises(TypeError, lambda: peekn(None, [1, 2, 3]))
    assert raises(TypeError, lambda: peekn(3, None))
    tested.append('peekn')

    assert raises(TypeError, lambda: list(random_sample(None, [1])))
    assert raises(TypeError, lambda: list(random_sample(0.1, None)))
    tested.append('random_sample')

    s1 = set(tested)
    s2 = set(cytoolz.itertoolz.__all__)
    assert s1 == s2, '%s not tested for being None-safe' % ', '.join(s2 - s1)


def test_recipes():
    tested = []
    # XXX
    assert (raises(TypeError, lambda: countby(None, [1, 2])) or
            countby(None, [1, 2]) == {(1,): 1, (2,): 1})
    assert raises(TypeError, lambda: countby(identity, None))
    tested.append('countby')

    # XXX
    assert (raises(TypeError, lambda: list(partitionby(None, [1, 2]))) or
            list(partitionby(None, [1, 2])) == [(1,), (2,)])
    assert raises(TypeError, lambda: list(partitionby(identity, None)))
    tested.append('partitionby')

    s1 = set(tested)
    s2 = set(cytoolz.recipes.__all__)
    assert s1 == s2, '%s not tested for being None-safe' % ', '.join(s2 - s1)
