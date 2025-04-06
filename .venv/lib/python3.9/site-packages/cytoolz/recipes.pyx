from cpython.sequence cimport PySequence_Tuple
from cytoolz.itertoolz cimport frequencies, pluck

from itertools import groupby


__all__ = ['countby', 'partitionby']


cpdef object countby(object key, object seq):
    """
    Count elements of a collection by a key function

    >>> countby(len, ['cat', 'mouse', 'dog'])
    {3: 2, 5: 1}

    >>> def iseven(x): return x % 2 == 0
    >>> countby(iseven, [1, 2, 3])  # doctest:+SKIP
    {True: 1, False: 2}

    See Also:
        groupby
    """
    if not callable(key):
        return frequencies(pluck(key, seq))
    return frequencies(map(key, seq))


cdef class partitionby:
    """ partitionby(func, seq)

    Partition a sequence according to a function

    Partition `s` into a sequence of lists such that, when traversing
    `s`, every time the output of `func` changes a new list is started
    and that and subsequent items are collected into that list.

    >>> is_space = lambda c: c == " "
    >>> list(partitionby(is_space, "I have space"))
    [('I',), (' ',), ('h', 'a', 'v', 'e'), (' ',), ('s', 'p', 'a', 'c', 'e')]

    >>> is_large = lambda x: x > 10
    >>> list(partitionby(is_large, [1, 2, 1, 99, 88, 33, 99, -1, 5]))
    [(1, 2, 1), (99, 88, 33, 99), (-1, 5)]

    See also:
        partition
        groupby
        itertools.groupby
    """
    def __cinit__(self, object func, object seq):
        self.iter_groupby = groupby(seq, key=func)

    def __iter__(self):
        return self

    def __next__(self):
        cdef object key, val
        key, val = next(self.iter_groupby)
        return PySequence_Tuple(val)
