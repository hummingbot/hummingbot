from cpython.dict cimport PyDict_GetItem, PyDict_SetItem
from cpython.exc cimport PyErr_Clear, PyErr_GivenExceptionMatches, PyErr_Occurred
from cpython.list cimport PyList_Append, PyList_GET_ITEM, PyList_GET_SIZE
from cpython.object cimport PyObject_RichCompareBool, Py_NE
from cpython.ref cimport PyObject, Py_INCREF, Py_XDECREF
from cpython.sequence cimport PySequence_Check
from cpython.set cimport PySet_Add, PySet_Contains
from cpython.tuple cimport PyTuple_GET_ITEM, PyTuple_GetSlice, PyTuple_New, PyTuple_SET_ITEM

# Locally defined bindings that differ from `cython.cpython` bindings
from cytoolz.cpython cimport PtrIter_Next, PtrObject_GetItem

from collections import deque
from heapq import heapify, heappop, heapreplace
from itertools import chain, islice, zip_longest
from operator import itemgetter
from cytoolz.utils import no_default


__all__ = ['remove', 'accumulate', 'groupby', 'merge_sorted', 'interleave',
           'unique', 'isiterable', 'isdistinct', 'take', 'drop', 'take_nth',
           'first', 'second', 'nth', 'last', 'get', 'concat', 'concatv',
           'mapcat', 'cons', 'interpose', 'frequencies', 'reduceby', 'iterate',
           'sliding_window', 'partition', 'partition_all', 'count', 'pluck',
           'join', 'tail', 'diff', 'topk', 'peek', 'peekn', 'random_sample']


cpdef object identity(object x):
    return x


cdef class remove:
    """ remove(predicate, seq)

    Return those items of sequence for which predicate(item) is False

    >>> def iseven(x):
    ...     return x % 2 == 0
    >>> list(remove(iseven, [1, 2, 3, 4]))
    [1, 3]
    """
    def __cinit__(self, object predicate, object seq):
        self.predicate = predicate
        self.iter_seq = iter(seq)

    def __iter__(self):
        return self

    def __next__(self):
        cdef object val
        val = next(self.iter_seq)
        while self.predicate(val):
            val = next(self.iter_seq)
        return val


cdef class accumulate:
    """ accumulate(binop, seq, initial='__no__default__')

    Repeatedly apply binary function to a sequence, accumulating results

    >>> from operator import add, mul
    >>> list(accumulate(add, [1, 2, 3, 4, 5]))
    [1, 3, 6, 10, 15]
    >>> list(accumulate(mul, [1, 2, 3, 4, 5]))
    [1, 2, 6, 24, 120]

    Accumulate is similar to ``reduce`` and is good for making functions like
    cumulative sum:

    >>> from functools import partial, reduce
    >>> sum    = partial(reduce, add)
    >>> cumsum = partial(accumulate, add)

    Accumulate also takes an optional argument that will be used as the first
    value. This is similar to reduce.

    >>> list(accumulate(add, [1, 2, 3], -1))
    [-1, 0, 2, 5]
    >>> list(accumulate(add, [], 1))
    [1]

    See Also:
        itertools.accumulate :  In standard itertools for Python 3.2+
    """
    def __cinit__(self, object binop, object seq, object initial='__no__default__'):
        self.binop = binop
        self.iter_seq = iter(seq)
        self.result = self  # sentinel
        self.initial = initial

    def __iter__(self):
        return self

    def __next__(self):
        if self.result is self:
            if self.initial != no_default:
                self.result = self.initial
            else:
                self.result = next(self.iter_seq)
        else:
            self.result = self.binop(self.result, next(self.iter_seq))
        return self.result


cdef inline object _groupby_core(dict d, object key, object item):
    cdef PyObject *obj = PyDict_GetItem(d, key)
    if obj is NULL:
        val = []
        PyList_Append(val, item)
        PyDict_SetItem(d, key, val)
    else:
        PyList_Append(<object>obj, item)


cpdef dict groupby(object key, object seq):
    """
    Group a collection by a key function

    >>> names = ['Alice', 'Bob', 'Charlie', 'Dan', 'Edith', 'Frank']
    >>> groupby(len, names)  # doctest: +SKIP
    {3: ['Bob', 'Dan'], 5: ['Alice', 'Edith', 'Frank'], 7: ['Charlie']}

    >>> iseven = lambda x: x % 2 == 0
    >>> groupby(iseven, [1, 2, 3, 4, 5, 6, 7, 8])  # doctest: +SKIP
    {False: [1, 3, 5, 7], True: [2, 4, 6, 8]}

    Non-callable keys imply grouping on a member.

    >>> groupby('gender', [{'name': 'Alice', 'gender': 'F'},
    ...                    {'name': 'Bob', 'gender': 'M'},
    ...                    {'name': 'Charlie', 'gender': 'M'}]) # doctest:+SKIP
    {'F': [{'gender': 'F', 'name': 'Alice'}],
     'M': [{'gender': 'M', 'name': 'Bob'},
           {'gender': 'M', 'name': 'Charlie'}]}

    Not to be confused with ``itertools.groupby``

    See Also:
        countby
    """
    cdef dict d = {}
    cdef object item, keyval
    cdef Py_ssize_t i, N
    if callable(key):
        for item in seq:
            keyval = key(item)
            _groupby_core(d, keyval, item)
    elif isinstance(key, list):
        N = PyList_GET_SIZE(key)
        for item in seq:
            keyval = PyTuple_New(N)
            for i in range(N):
                val = <object>PyList_GET_ITEM(key, i)
                val = item[val]
                Py_INCREF(val)
                PyTuple_SET_ITEM(keyval, i, val)
            _groupby_core(d, keyval, item)
    else:
        for item in seq:
            keyval = item[key]
            _groupby_core(d, keyval, item)
    return d


cdef object _merge_sorted_binary(object seqs):
    mid = len(seqs) // 2
    L1 = seqs[:mid]
    if len(L1) == 1:
        seq1 = iter(L1[0])
    else:
        seq1 = _merge_sorted_binary(L1)
    L2 = seqs[mid:]
    if len(L2) == 1:
        seq2 = iter(L2[0])
    else:
        seq2 = _merge_sorted_binary(L2)
    try:
        val2 = next(seq2)
    except StopIteration:
        return seq1
    return _merge_sorted(seq1, seq2, val2)


cdef class _merge_sorted:
    def __cinit__(self, seq1, seq2, val2):
        self.seq1 = seq1
        self.seq2 = seq2
        self.val1 = None
        self.val2 = val2
        self.loop = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.loop == 0:
            try:
                self.val1 = next(self.seq1)
            except StopIteration:
                self.loop = 2
                return self.val2
            if self.val2 < self.val1:
                self.loop = 1
                return self.val2
            return self.val1
        elif self.loop == 1:
            try:
                self.val2 = next(self.seq2)
            except StopIteration:
                self.loop = 3
                return self.val1
            if self.val2 < self.val1:
                return self.val2
            self.loop = 0
            return self.val1
        elif self.loop == 2:
            return next(self.seq2)
        return next(self.seq1)


cdef object _merge_sorted_binary_key(object seqs, object key):
    mid = len(seqs) // 2
    L1 = seqs[:mid]
    if len(L1) == 1:
        seq1 = iter(L1[0])
    else:
        seq1 = _merge_sorted_binary_key(L1, key)
    L2 = seqs[mid:]
    if len(L2) == 1:
        seq2 = iter(L2[0])
    else:
        seq2 = _merge_sorted_binary_key(L2, key)
    try:
        val2 = next(seq2)
    except StopIteration:
        return seq1
    return _merge_sorted_key(seq1, seq2, val2, key)


cdef class _merge_sorted_key:
    def __cinit__(self, seq1, seq2, val2, key):
        self.seq1 = seq1
        self.seq2 = seq2
        self.key = key
        self.val1 = None
        self.key1 = None
        self.val2 = val2
        self.key2 = key(val2)
        self.loop = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.loop == 0:
            try:
                self.val1 = next(self.seq1)
            except StopIteration:
                self.loop = 2
                return self.val2
            self.key1 = self.key(self.val1)
            if self.key2 < self.key1:
                self.loop = 1
                return self.val2
            return self.val1
        elif self.loop == 1:
            try:
                self.val2 = next(self.seq2)
            except StopIteration:
                self.loop = 3
                return self.val1
            self.key2 = self.key(self.val2)
            if self.key2 < self.key1:
                return self.val2
            self.loop = 0
            return self.val1
        elif self.loop == 2:
            return next(self.seq2)
        return next(self.seq1)


cdef object c_merge_sorted(object seqs, object key=None):
    if len(seqs) == 0:
        return iter([])
    elif len(seqs) == 1:
        return iter(seqs[0])
    elif key is None:
        return _merge_sorted_binary(seqs)
    return _merge_sorted_binary_key(seqs, key)


def merge_sorted(*seqs, **kwargs):
    """
    Merge and sort a collection of sorted collections

    This works lazily and only keeps one value from each iterable in memory.

    >>> list(merge_sorted([1, 3, 5], [2, 4, 6]))
    [1, 2, 3, 4, 5, 6]

    >>> ''.join(merge_sorted('abc', 'abc', 'abc'))
    'aaabbbccc'

    The "key" function used to sort the input may be passed as a keyword.

    >>> list(merge_sorted([2, 3], [1, 3], key=lambda x: x // 3))
    [2, 1, 3, 3]
    """
    if 'key' in kwargs:
        return c_merge_sorted(seqs, kwargs['key'])
    return c_merge_sorted(seqs)


cdef class interleave:
    """ interleave(seqs)

    Interleave a sequence of sequences

    >>> list(interleave([[1, 2], [3, 4]]))
    [1, 3, 2, 4]

    >>> ''.join(interleave(('ABC', 'XY')))
    'AXBYC'

    Both the individual sequences and the sequence of sequences may be infinite

    Returns a lazy iterator
    """
    def __cinit__(self, seqs):
        self.iters = [iter(seq) for seq in seqs]
        self.newiters = []
        self.i = 0
        self.n = PyList_GET_SIZE(self.iters)

    def __iter__(self):
        return self

    def __next__(self):
        # This implementation is similar to what is done in `toolz` in that we
        # construct a new list of iterators, `self.newiters`, when a value is
        # successfully retrieved from an iterator from `self.iters`.
        cdef PyObject *obj
        cdef object val

        if self.i == self.n:
            self.n = PyList_GET_SIZE(self.newiters)
            self.i = 0
            if self.n == 0:
                raise StopIteration
            self.iters = self.newiters
            self.newiters = []
        val = <object>PyList_GET_ITEM(self.iters, self.i)
        self.i += 1
        obj = PtrIter_Next(val)

        # TODO: optimization opportunity.  Previously, it was possible to
        # continue on given exceptions, `self.pass_exceptions`, which is
        # why this code is structured this way.  Time to clean up?
        while obj is NULL:
            obj = PyErr_Occurred()
            if obj is not NULL:
                val = <object>obj
                PyErr_Clear()
                raise val

            if self.i == self.n:
                self.n = PyList_GET_SIZE(self.newiters)
                self.i = 0
                if self.n == 0:
                    raise StopIteration
                self.iters = self.newiters
                self.newiters = []
            val = <object>PyList_GET_ITEM(self.iters, self.i)
            self.i += 1
            obj = PtrIter_Next(val)

        PyList_Append(self.newiters, val)
        val = <object>obj
        Py_XDECREF(obj)
        return val


cdef class _unique_key:
    def __cinit__(self, object seq, object key):
        self.iter_seq = iter(seq)
        self.key = key
        self.seen = set()

    def __iter__(self):
        return self

    def __next__(self):
        cdef object item, tag
        item = next(self.iter_seq)
        tag = self.key(item)
        while PySet_Contains(self.seen, tag):
            item = next(self.iter_seq)
            tag = self.key(item)
        PySet_Add(self.seen, tag)
        return item


cdef class _unique_identity:
    def __cinit__(self, object seq):
        self.iter_seq = iter(seq)
        self.seen = set()

    def __iter__(self):
        return self

    def __next__(self):
        cdef object item
        item = next(self.iter_seq)
        while PySet_Contains(self.seen, item):
            item = next(self.iter_seq)
        PySet_Add(self.seen, item)
        return item


cpdef object unique(object seq, object key=None):
    """
    Return only unique elements of a sequence

    >>> tuple(unique((1, 2, 3)))
    (1, 2, 3)
    >>> tuple(unique((1, 2, 1, 3)))
    (1, 2, 3)

    Uniqueness can be defined by key keyword

    >>> tuple(unique(['cat', 'mouse', 'dog', 'hen'], key=len))
    ('cat', 'mouse')
    """
    if key is None:
        return _unique_identity(seq)
    else:
        return _unique_key(seq, key)


cpdef object isiterable(object x):
    """
    Is x iterable?

    >>> isiterable([1, 2, 3])
    True
    >>> isiterable('abc')
    True
    >>> isiterable(5)
    False
    """
    try:
        iter(x)
        return True
    except TypeError:
        pass
    return False


cpdef object isdistinct(object seq):
    """
    All values in sequence are distinct

    >>> isdistinct([1, 2, 3])
    True
    >>> isdistinct([1, 2, 1])
    False

    >>> isdistinct("Hello")
    False
    >>> isdistinct("World")
    True
    """
    if iter(seq) is seq:
        seen = set()
        for item in seq:
            if PySet_Contains(seen, item):
                return False
            seen.add(item)
        return True
    else:
        return len(seq) == len(set(seq))


cpdef object take(Py_ssize_t n, object seq):
    """
    The first n elements of a sequence

    >>> list(take(2, [10, 20, 30, 40, 50]))
    [10, 20]

    See Also:
        drop
        tail
    """
    return islice(seq, n)


cpdef object tail(Py_ssize_t n, object seq):
    """
    The last n elements of a sequence

    >>> tail(2, [10, 20, 30, 40, 50])
    [40, 50]

    See Also:
        drop
        take
    """
    if PySequence_Check(seq):
        return seq[-n:]
    return tuple(deque(seq, n))


cpdef object drop(Py_ssize_t n, object seq):
    """
    The sequence following the first n elements

    >>> list(drop(2, [10, 20, 30, 40, 50]))
    [30, 40, 50]

    See Also:
        take
        tail
    """
    if n < 0:
        raise ValueError('n argument for drop() must be non-negative')
    cdef Py_ssize_t i
    cdef object iter_seq
    iter_seq = iter(seq)
    try:
        for i in range(n):
            next(iter_seq)
    except StopIteration:
        pass
    return iter_seq


cpdef object take_nth(Py_ssize_t n, object seq):
    """
    Every nth item in seq

    >>> list(take_nth(2, [10, 20, 30, 40, 50]))
    [10, 30, 50]
    """
    return islice(seq, 0, None, n)


cpdef object first(object seq):
    """
    The first element in a sequence

    >>> first('ABC')
    'A'
    """
    return next(iter(seq))


cpdef object second(object seq):
    """
    The second element in a sequence

    >>> second('ABC')
    'B'
    """
    seq = iter(seq)
    next(seq)
    return next(seq)


cpdef object nth(Py_ssize_t n, object seq):
    """
    The nth element in a sequence

    >>> nth(1, 'ABC')
    'B'
    """
    if PySequence_Check(seq):
        return seq[n]
    if n < 0:
        raise ValueError('"n" must be positive when indexing an iterator')
    seq = iter(seq)
    while n > 0:
        n -= 1
        next(seq)
    return next(seq)


cpdef object last(object seq):
    """
    The last element in a sequence

    >>> last('ABC')
    'C'
    """
    cdef object val
    if PySequence_Check(seq):
        return seq[-1]
    val = no_default
    for val in seq:
        pass
    if val == no_default:
        raise IndexError
    return val


cpdef object rest(object seq):
    seq = iter(seq)
    next(seq)
    return seq


cdef tuple _get_exceptions = (IndexError, KeyError, TypeError)
cdef tuple _get_list_exc = (IndexError, KeyError)


cpdef object get(object ind, object seq, object default='__no__default__'):
    """
    Get element in a sequence or dict

    Provides standard indexing

    >>> get(1, 'ABC')       # Same as 'ABC'[1]
    'B'

    Pass a list to get multiple values

    >>> get([1, 2], 'ABC')  # ('ABC'[1], 'ABC'[2])
    ('B', 'C')

    Works on any value that supports indexing/getitem
    For example here we see that it works with dictionaries

    >>> phonebook = {'Alice':  '555-1234',
    ...              'Bob':    '555-5678',
    ...              'Charlie':'555-9999'}
    >>> get('Alice', phonebook)
    '555-1234'

    >>> get(['Alice', 'Bob'], phonebook)
    ('555-1234', '555-5678')

    Provide a default for missing values

    >>> get(['Alice', 'Dennis'], phonebook, None)
    ('555-1234', None)

    See Also:
        pluck
    """
    cdef Py_ssize_t i
    cdef object val
    cdef tuple result
    cdef PyObject *obj
    if isinstance(ind, list):
        i = PyList_GET_SIZE(ind)
        result = PyTuple_New(i)
        # List of indices, no default
        if default == no_default:
            for i, val in enumerate(ind):
                val = seq[val]
                Py_INCREF(val)
                PyTuple_SET_ITEM(result, i, val)
            return result

        # List of indices with default
        for i, val in enumerate(ind):
            obj = PtrObject_GetItem(seq, val)
            if obj is NULL:
                val = <object>PyErr_Occurred()
                PyErr_Clear()
                if not PyErr_GivenExceptionMatches(val, _get_list_exc):
                    raise val
                Py_INCREF(default)
                PyTuple_SET_ITEM(result, i, default)
            else:
                val = <object>obj
                PyTuple_SET_ITEM(result, i, val)
        return result

    obj = PtrObject_GetItem(seq, ind)
    if obj is NULL:
        val = <object>PyErr_Occurred()
        PyErr_Clear()
        if default == no_default:
            raise val
        if PyErr_GivenExceptionMatches(val, _get_exceptions):
            return default
        raise val
    val = <object>obj
    Py_XDECREF(obj)
    return val


cpdef object concat(object seqs):
    """
    Concatenate zero or more iterables, any of which may be infinite.

    An infinite sequence will prevent the rest of the arguments from
    being included.

    We use chain.from_iterable rather than ``chain(*seqs)`` so that seqs
    can be a generator.

    >>> list(concat([[], [1], [2, 3]]))
    [1, 2, 3]

    See also:
        itertools.chain.from_iterable  equivalent
    """
    return chain.from_iterable(seqs)


def concatv(*seqs):
    """
    Variadic version of concat

    >>> list(concatv([], ["a"], ["b", "c"]))
    ['a', 'b', 'c']

    See also:
        itertools.chain
    """
    return chain.from_iterable(seqs)


cpdef object mapcat(object func, object seqs):
    """
    Apply func to each sequence in seqs, concatenating results.

    >>> list(mapcat(lambda s: [c.upper() for c in s],
    ...             [["a", "b"], ["c", "d", "e"]]))
    ['A', 'B', 'C', 'D', 'E']
    """
    return concat(map(func, seqs))


cpdef object cons(object el, object seq):
    """
    Add el to beginning of (possibly infinite) sequence seq.

    >>> list(cons(1, [2, 3]))
    [1, 2, 3]
    """
    return chain((el,), seq)


cdef class interpose:
    """ interpose(el, seq)

    Introduce element between each pair of elements in seq

    >>> list(interpose("a", [1, 2, 3]))
    [1, 'a', 2, 'a', 3]
    """
    def __cinit__(self, object el, object seq):
        self.el = el
        self.iter_seq = iter(seq)
        self.do_el = False
        try:
            self.val = next(self.iter_seq)
        except StopIteration:
            self.do_el = True

    def __iter__(self):
        return self

    def __next__(self):
        if self.do_el:
            self.val = next(self.iter_seq)
            self.do_el = False
            return self.el
        else:
            self.do_el = True
            return self.val


cpdef dict frequencies(object seq):
    """
    Find number of occurrences of each value in seq

    >>> frequencies(['cat', 'cat', 'ox', 'pig', 'pig', 'cat'])  #doctest: +SKIP
    {'cat': 3, 'ox': 1, 'pig': 2}

    See Also:
        countby
        groupby
    """
    cdef dict d = {}
    cdef PyObject *obj
    cdef Py_ssize_t val
    for item in seq:
        obj = PyDict_GetItem(d, item)
        if obj is NULL:
            d[item] = 1
        else:
            val = <object>obj
            d[item] = val + 1
    return d


cdef inline object _reduceby_core(dict d, object key, object item, object binop,
                                object init, bint skip_init, bint call_init):
    cdef PyObject *obj = PyDict_GetItem(d, key)
    if obj is not NULL:
        PyDict_SetItem(d, key, binop(<object>obj, item))
    elif skip_init:
        PyDict_SetItem(d, key, item)
    elif call_init:
        PyDict_SetItem(d, key, binop(init(), item))
    else:
        PyDict_SetItem(d, key, binop(init, item))


cpdef dict reduceby(object key, object binop, object seq, object init='__no__default__'):
    """
    Perform a simultaneous groupby and reduction

    The computation:

    >>> result = reduceby(key, binop, seq, init)      # doctest: +SKIP

    is equivalent to the following:

    >>> def reduction(group):                           # doctest: +SKIP
    ...     return reduce(binop, group, init)           # doctest: +SKIP

    >>> groups = groupby(key, seq)                    # doctest: +SKIP
    >>> result = valmap(reduction, groups)              # doctest: +SKIP

    But the former does not build the intermediate groups, allowing it to
    operate in much less space.  This makes it suitable for larger datasets
    that do not fit comfortably in memory

    The ``init`` keyword argument is the default initialization of the
    reduction.  This can be either a constant value like ``0`` or a callable
    like ``lambda : 0`` as might be used in ``defaultdict``.

    Simple Examples
    ---------------

    >>> from operator import add, mul
    >>> iseven = lambda x: x % 2 == 0

    >>> data = [1, 2, 3, 4, 5]

    >>> reduceby(iseven, add, data)  # doctest: +SKIP
    {False: 9, True: 6}

    >>> reduceby(iseven, mul, data)  # doctest: +SKIP
    {False: 15, True: 8}

    Complex Example
    ---------------

    >>> projects = [{'name': 'build roads', 'state': 'CA', 'cost': 1000000},
    ...             {'name': 'fight crime', 'state': 'IL', 'cost': 100000},
    ...             {'name': 'help farmers', 'state': 'IL', 'cost': 2000000},
    ...             {'name': 'help farmers', 'state': 'CA', 'cost': 200000}]

    >>> reduceby('state',                        # doctest: +SKIP
    ...          lambda acc, x: acc + x['cost'],
    ...          projects, 0)
    {'CA': 1200000, 'IL': 2100000}

    Example Using ``init``
    ----------------------

    >>> def set_add(s, i):
    ...     s.add(i)
    ...     return s

    >>> reduceby(iseven, set_add, [1, 2, 3, 4, 1, 2, 3], set)  # doctest: +SKIP
    {True:  set([2, 4]),
     False: set([1, 3])}
    """
    cdef dict d = {}
    cdef object item, keyval
    cdef Py_ssize_t i, N
    cdef bint skip_init = init == no_default
    cdef bint call_init = callable(init)
    if callable(key):
        for item in seq:
            keyval = key(item)
            _reduceby_core(d, keyval, item, binop, init, skip_init, call_init)
    elif isinstance(key, list):
        N = PyList_GET_SIZE(key)
        for item in seq:
            keyval = PyTuple_New(N)
            for i in range(N):
                val = <object>PyList_GET_ITEM(key, i)
                val = item[val]
                Py_INCREF(val)
                PyTuple_SET_ITEM(keyval, i, val)
            _reduceby_core(d, keyval, item, binop, init, skip_init, call_init)
    else:
        for item in seq:
            keyval = item[key]
            _reduceby_core(d, keyval, item, binop, init, skip_init, call_init)
    return d


cdef class iterate:
    """ iterate(func, x)

    Repeatedly apply a function func onto an original input

    Yields x, then func(x), then func(func(x)), then func(func(func(x))), etc..

    >>> def inc(x):  return x + 1
    >>> counter = iterate(inc, 0)
    >>> next(counter)
    0
    >>> next(counter)
    1
    >>> next(counter)
    2

    >>> double = lambda x: x * 2
    >>> powers_of_two = iterate(double, 1)
    >>> next(powers_of_two)
    1
    >>> next(powers_of_two)
    2
    >>> next(powers_of_two)
    4
    >>> next(powers_of_two)
    8
    """
    def __cinit__(self, object func, object x):
        self.func = func
        self.x = x
        self.val = self  # sentinel

    def __iter__(self):
        return self

    def __next__(self):
        if self.val is self:
            self.val = self.x
        else:
            self.x = self.func(self.x)
        return self.x


cdef class sliding_window:
    """ sliding_window(n, seq)

    A sequence of overlapping subsequences

    >>> list(sliding_window(2, [1, 2, 3, 4]))
    [(1, 2), (2, 3), (3, 4)]

    This function creates a sliding window suitable for transformations like
    sliding means / smoothing

    >>> mean = lambda seq: float(sum(seq)) / len(seq)
    >>> list(map(mean, sliding_window(2, [1, 2, 3, 4])))
    [1.5, 2.5, 3.5]
    """
    def __cinit__(self, Py_ssize_t n, object seq):
        cdef Py_ssize_t i
        self.iterseq = iter(seq)
        self.prev = PyTuple_New(n)
        Py_INCREF(None)
        PyTuple_SET_ITEM(self.prev, 0, None)
        for i, seq in enumerate(islice(self.iterseq, n-1), 1):
            Py_INCREF(seq)
            PyTuple_SET_ITEM(self.prev, i, seq)
        self.n = n

    def __iter__(self):
        return self

    def __next__(self):
        cdef tuple current
        cdef object item
        cdef Py_ssize_t i

        item = next(self.iterseq)
        current = PyTuple_New(self.n)
        Py_INCREF(item)
        PyTuple_SET_ITEM(current, self.n-1, item)
        for i in range(1, self.n):
            item = self.prev[i]
            Py_INCREF(item)
            PyTuple_SET_ITEM(current, i-1, item)
        self.prev = current
        return current


no_pad = '__no__pad__'


cpdef object partition(Py_ssize_t n, object seq, object pad='__no__pad__'):
    """
    Partition sequence into tuples of length n

    >>> list(partition(2, [1, 2, 3, 4]))
    [(1, 2), (3, 4)]

    If the length of ``seq`` is not evenly divisible by ``n``, the final tuple
    is dropped if ``pad`` is not specified, or filled to length ``n`` by pad:

    >>> list(partition(2, [1, 2, 3, 4, 5]))
    [(1, 2), (3, 4)]

    >>> list(partition(2, [1, 2, 3, 4, 5], pad=None))
    [(1, 2), (3, 4), (5, None)]

    See Also:
        partition_all
    """
    args = [iter(seq)] * n
    if pad == '__no__pad__':
        return zip(*args)
    else:
        return zip_longest(*args, fillvalue=pad)


cdef class partition_all:
    """ partition_all(n, seq)

    Partition all elements of sequence into tuples of length at most n

    The final tuple may be shorter to accommodate extra elements.

    >>> list(partition_all(2, [1, 2, 3, 4]))
    [(1, 2), (3, 4)]

    >>> list(partition_all(2, [1, 2, 3, 4, 5]))
    [(1, 2), (3, 4), (5,)]

    See Also:
        partition
    """
    def __cinit__(self, Py_ssize_t n, object seq):
        self.n = n
        self.iterseq = iter(seq)

    def __iter__(self):
        return self

    def __next__(self):
        cdef tuple result
        cdef object item
        cdef Py_ssize_t i = 0
        result = PyTuple_New(self.n)
        for item in self.iterseq:
            Py_INCREF(item)
            PyTuple_SET_ITEM(result, i, item)
            i += 1
            if i == self.n:
                return result
        # iterable exhausted before filling the tuple
        if i == 0:
            raise StopIteration
        for j in range(i, self.n):
            Py_INCREF(None)
            PyTuple_SET_ITEM(result, j, None)
        return PyTuple_GetSlice(result, 0, i)


cpdef object count(object seq):
    """
    Count the number of items in seq

    Like the builtin ``len`` but works on lazy sequences.

    Not to be confused with ``itertools.count``

    See also:
        len
    """
    if iter(seq) is not seq and hasattr(seq, '__len__'):
        return len(seq)
    cdef Py_ssize_t i = 0
    for _ in seq:
        i += 1
    return i


cdef class _pluck_index:
    def __cinit__(self, object ind, object seqs):
        self.ind = ind
        self.iterseqs = iter(seqs)

    def __iter__(self):
        return self

    def __next__(self):
        val = next(self.iterseqs)
        return val[self.ind]


cdef class _pluck_index_default:
    def __cinit__(self, object ind, object seqs, object default):
        self.ind = ind
        self.iterseqs = iter(seqs)
        self.default = default

    def __iter__(self):
        return self

    def __next__(self):
        cdef PyObject *obj
        cdef object val
        val = next(self.iterseqs)
        obj = PtrObject_GetItem(val, self.ind)
        if obj is NULL:
            val = <object>PyErr_Occurred()
            PyErr_Clear()
            if not PyErr_GivenExceptionMatches(val, _get_exceptions):
                raise val
            return self.default
        val = <object>obj
        Py_XDECREF(obj)
        return val


cdef class _pluck_list:
    def __cinit__(self, list ind not None, object seqs):
        self.ind = ind
        self.iterseqs = iter(seqs)
        self.n = len(ind)

    def __iter__(self):
        return self

    def __next__(self):
        cdef Py_ssize_t i
        cdef tuple result
        cdef object val, seq
        seq = next(self.iterseqs)
        result = PyTuple_New(self.n)
        for i, val in enumerate(self.ind):
            val = seq[val]
            Py_INCREF(val)
            PyTuple_SET_ITEM(result, i, val)
        return result


cdef class _pluck_list_default:
    def __cinit__(self, list ind not None, object seqs, object default):
        self.ind = ind
        self.iterseqs = iter(seqs)
        self.default = default
        self.n = len(ind)

    def __iter__(self):
        return self

    def __next__(self):
        cdef Py_ssize_t i
        cdef object val, seq
        cdef tuple result
        seq = next(self.iterseqs)
        result = PyTuple_New(self.n)
        for i, val in enumerate(self.ind):
            obj = PtrObject_GetItem(seq, val)
            if obj is NULL:
                val = <object>PyErr_Occurred()
                PyErr_Clear()
                if not PyErr_GivenExceptionMatches(val, _get_list_exc):
                    raise val
                Py_INCREF(self.default)
                PyTuple_SET_ITEM(result, i, self.default)
            else:
                val = <object>obj
                PyTuple_SET_ITEM(result, i, val)
        return result


cpdef object pluck(object ind, object seqs, object default='__no__default__'):
    """
    plucks an element or several elements from each item in a sequence.

    ``pluck`` maps ``itertoolz.get`` over a sequence and returns one or more
    elements of each item in the sequence.

    This is equivalent to running `map(curried.get(ind), seqs)`

    ``ind`` can be either a single string/index or a list of strings/indices.
    ``seqs`` should be sequence containing sequences or dicts.

    e.g.

    >>> data = [{'id': 1, 'name': 'Cheese'}, {'id': 2, 'name': 'Pies'}]
    >>> list(pluck('name', data))
    ['Cheese', 'Pies']
    >>> list(pluck([0, 1], [[1, 2, 3], [4, 5, 7]]))
    [(1, 2), (4, 5)]

    See Also:
        get
        map
    """
    if isinstance(ind, list):
        if default != no_default:
            return _pluck_list_default(ind, seqs, default)
        if PyList_GET_SIZE(ind) < 10:
            return _pluck_list(ind, seqs)
        return map(itemgetter(*ind), seqs)
    if default == no_default:
        return _pluck_index(ind, seqs)
    return _pluck_index_default(ind, seqs, default)


cdef class _getter_index:
    def __cinit__(self, object ind):
        self.ind = ind

    def __call__(self, object seq):
        return seq[self.ind]


cdef class _getter_list:
    def __cinit__(self, list ind not None):
        self.ind = ind
        self.n = len(ind)

    def __call__(self, object seq):
        cdef Py_ssize_t i
        cdef tuple result
        cdef object val
        result = PyTuple_New(self.n)
        for i, val in enumerate(self.ind):
            val = seq[val]
            Py_INCREF(val)
            PyTuple_SET_ITEM(result, i, val)
        return result


cdef class _getter_null:
    def __call__(self, object seq):
        return ()


# TODO: benchmark getters (and compare against itemgetter)
cpdef object getter(object index):
    if isinstance(index, list):
        if PyList_GET_SIZE(index) == 0:
            return _getter_null()
        elif PyList_GET_SIZE(index) < 10:
            return _getter_list(index)
        return itemgetter(*index)
    return _getter_index(index)


cpdef object join(object leftkey, object leftseq,
                  object rightkey, object rightseq,
                  object left_default='__no__default__',
                  object right_default='__no__default__'):
    """
    Join two sequences on common attributes

    This is a semi-streaming operation.  The LEFT sequence is fully evaluated
    and placed into memory.  The RIGHT sequence is evaluated lazily and so can
    be arbitrarily large.
    (Note: If right_default is defined, then unique keys of rightseq
        will also be stored in memory.)

    >>> friends = [('Alice', 'Edith'),
    ...            ('Alice', 'Zhao'),
    ...            ('Edith', 'Alice'),
    ...            ('Zhao', 'Alice'),
    ...            ('Zhao', 'Edith')]

    >>> cities = [('Alice', 'NYC'),
    ...           ('Alice', 'Chicago'),
    ...           ('Dan', 'Sydney'),
    ...           ('Edith', 'Paris'),
    ...           ('Edith', 'Berlin'),
    ...           ('Zhao', 'Shanghai')]

    >>> # Vacation opportunities
    >>> # In what cities do people have friends?
    >>> result = join(second, friends,
    ...               first, cities)
    >>> for ((a, b), (c, d)) in sorted(unique(result)):
    ...     print((a, d))
    ('Alice', 'Berlin')
    ('Alice', 'Paris')
    ('Alice', 'Shanghai')
    ('Edith', 'Chicago')
    ('Edith', 'NYC')
    ('Zhao', 'Chicago')
    ('Zhao', 'NYC')
    ('Zhao', 'Berlin')
    ('Zhao', 'Paris')

    Specify outer joins with keyword arguments ``left_default`` and/or
    ``right_default``.  Here is a full outer join in which unmatched elements
    are paired with None.

    >>> identity = lambda x: x
    >>> list(join(identity, [1, 2, 3],
    ...           identity, [2, 3, 4],
    ...           left_default=None, right_default=None))
    [(2, 2), (3, 3), (None, 4), (1, None)]

    Usually the key arguments are callables to be applied to the sequences.  If
    the keys are not obviously callable then it is assumed that indexing was
    intended, e.g. the following is a legal change.
    The join is implemented as a hash join and the keys of leftseq must be
    hashable. Additionally, if right_default is defined, then keys of rightseq
    must also be hashable.

    >>> # result = join(second, friends, first, cities)
    >>> result = join(1, friends, 0, cities)  # doctest: +SKIP
    """
    if left_default == no_default and right_default == no_default:
        if callable(rightkey):
            return _inner_join_key(leftkey, leftseq, rightkey, rightseq,
                                   left_default, right_default)
        elif isinstance(rightkey, list):
            return _inner_join_indices(leftkey, leftseq, rightkey, rightseq,
                                       left_default, right_default)
        else:
            return _inner_join_index(leftkey, leftseq, rightkey, rightseq,
                                     left_default, right_default)
    elif left_default != no_default and right_default == no_default:
        if callable(rightkey):
            return _right_outer_join_key(leftkey, leftseq, rightkey, rightseq,
                                         left_default, right_default)
        elif isinstance(rightkey, list):
            return _right_outer_join_indices(leftkey, leftseq, rightkey, rightseq,
                                             left_default, right_default)
        else:
            return _right_outer_join_index(leftkey, leftseq, rightkey, rightseq,
                                           left_default, right_default)
    elif left_default == no_default and right_default != no_default:
        if callable(rightkey):
            return _left_outer_join_key(leftkey, leftseq, rightkey, rightseq,
                                        left_default, right_default)
        elif isinstance(rightkey, list):
            return _left_outer_join_indices(leftkey, leftseq, rightkey, rightseq,
                                            left_default, right_default)
        else:
            return _left_outer_join_index(leftkey, leftseq, rightkey, rightseq,
                                          left_default, right_default)
    else:
        if callable(rightkey):
            return _outer_join_key(leftkey, leftseq, rightkey, rightseq,
                                   left_default, right_default)
        elif isinstance(rightkey, list):
            return _outer_join_indices(leftkey, leftseq, rightkey, rightseq,
                                       left_default, right_default)
        else:
            return _outer_join_index(leftkey, leftseq, rightkey, rightseq,
                                     left_default, right_default)

cdef class _join:
    def __cinit__(self,
                  object leftkey, object leftseq,
                  object rightkey, object rightseq,
                  object left_default=no_default,
                  object right_default=no_default):
        self.left_default = left_default
        self.right_default = right_default

        self._rightkey = rightkey
        self.rightseq = iter(rightseq)
        if isinstance(rightkey, list):
            self.N = len(rightkey)

        self.d = groupby(leftkey, leftseq)
        self.seen_keys = set()
        self.matches = []
        self.right = None

        self.is_rightseq_exhausted = False

    def __iter__(self):
        return self

    cdef object rightkey(self):
        pass


cdef class _right_outer_join(_join):
    def __next__(self):
        cdef PyObject *obj
        if self.i == PyList_GET_SIZE(self.matches):
            self.right = next(self.rightseq)
            key = self.rightkey()
            obj = PyDict_GetItem(self.d, key)
            if obj is NULL:
                return (self.left_default, self.right)
            self.matches = <object>obj
            self.i = 0
        match = <object>PyList_GET_ITEM(self.matches, self.i)  # skip error checking
        self.i += 1
        return (match, self.right)


cdef class _right_outer_join_key(_right_outer_join):
    cdef object rightkey(self):
        return self._rightkey(self.right)


cdef class _right_outer_join_index(_right_outer_join):
    cdef object rightkey(self):
        return self.right[self._rightkey]


cdef class _right_outer_join_indices(_right_outer_join):
    cdef object rightkey(self):
        keyval = PyTuple_New(self.N)
        for i in range(self.N):
            val = <object>PyList_GET_ITEM(self._rightkey, i)
            val = self.right[val]
            Py_INCREF(val)
            PyTuple_SET_ITEM(keyval, i, val)
        return keyval


cdef class _outer_join(_join):
    def __next__(self):
        cdef PyObject *obj
        if not self.is_rightseq_exhausted:
            if self.i == PyList_GET_SIZE(self.matches):
                try:
                    self.right = next(self.rightseq)
                except StopIteration:
                    self.is_rightseq_exhausted = True
                    self.keys = iter(self.d)
                    return next(self)
                key = self.rightkey()
                PySet_Add(self.seen_keys, key)
                obj = PyDict_GetItem(self.d, key)
                if obj is NULL:
                    return (self.left_default, self.right)
                self.matches = <object>obj
                self.i = 0
            match = <object>PyList_GET_ITEM(self.matches, self.i)  # skip error checking
            self.i += 1
            return (match, self.right)

        else:
            if self.i == PyList_GET_SIZE(self.matches):
                key = next(self.keys)
                while key in self.seen_keys:
                    key = next(self.keys)
                obj = PyDict_GetItem(self.d, key)
                self.matches = <object>obj
                self.i = 0
            match = <object>PyList_GET_ITEM(self.matches, self.i)  # skip error checking
            self.i += 1
            return (match, self.right_default)


cdef class _outer_join_key(_outer_join):
    cdef object rightkey(self):
        return self._rightkey(self.right)


cdef class _outer_join_index(_outer_join):
    cdef object rightkey(self):
        return self.right[self._rightkey]


cdef class _outer_join_indices(_outer_join):
    cdef object rightkey(self):
        keyval = PyTuple_New(self.N)
        for i in range(self.N):
            val = <object>PyList_GET_ITEM(self._rightkey, i)
            val = self.right[val]
            Py_INCREF(val)
            PyTuple_SET_ITEM(keyval, i, val)
        return keyval


cdef class _left_outer_join(_join):
    def __next__(self):
        cdef PyObject *obj
        if not self.is_rightseq_exhausted:
            if self.i == PyList_GET_SIZE(self.matches):
                obj = NULL
                while obj is NULL:
                    try:
                        self.right = next(self.rightseq)
                    except StopIteration:
                        self.is_rightseq_exhausted = True
                        self.keys = iter(self.d)
                        return next(self)
                    key = self.rightkey()
                    PySet_Add(self.seen_keys, key)
                    obj = PyDict_GetItem(self.d, key)
                self.matches = <object>obj
                self.i = 0
            match = <object>PyList_GET_ITEM(self.matches, self.i)  # skip error checking
            self.i += 1
            return (match, self.right)

        else:
            if self.i == PyList_GET_SIZE(self.matches):
                key = next(self.keys)
                while key in self.seen_keys:
                    key = next(self.keys)
                obj = PyDict_GetItem(self.d, key)
                self.matches = <object>obj
                self.i = 0
            match = <object>PyList_GET_ITEM(self.matches, self.i)  # skip error checking
            self.i += 1
            return (match, self.right_default)


cdef class _left_outer_join_key(_left_outer_join):
    cdef object rightkey(self):
        return self._rightkey(self.right)


cdef class _left_outer_join_index(_left_outer_join):
    cdef object rightkey(self):
        return self.right[self._rightkey]


cdef class _left_outer_join_indices(_left_outer_join):
    cdef object rightkey(self):
        keyval = PyTuple_New(self.N)
        for i in range(self.N):
            val = <object>PyList_GET_ITEM(self._rightkey, i)
            val = self.right[val]
            Py_INCREF(val)
            PyTuple_SET_ITEM(keyval, i, val)
        return keyval


cdef class _inner_join(_join):
    def __next__(self):
        cdef PyObject *obj = NULL
        if self.i == PyList_GET_SIZE(self.matches):
            while obj is NULL:
                self.right = next(self.rightseq)
                key = self.rightkey()
                obj = PyDict_GetItem(self.d, key)
            self.matches = <object>obj
            self.i = 0
        match = <object>PyList_GET_ITEM(self.matches, self.i)  # skip error checking
        self.i += 1
        return (match, self.right)


cdef class _inner_join_key(_inner_join):
    cdef object rightkey(self):
        return self._rightkey(self.right)


cdef class _inner_join_index(_inner_join):
    cdef object rightkey(self):
        return self.right[self._rightkey]


cdef class _inner_join_indices(_inner_join):
    cdef object rightkey(self):
        keyval = PyTuple_New(self.N)
        for i in range(self.N):
            val = <object>PyList_GET_ITEM(self._rightkey, i)
            val = self.right[val]
            Py_INCREF(val)
            PyTuple_SET_ITEM(keyval, i, val)
        return keyval


cdef class _diff_key:
    def __cinit__(self, object seqs, object key, object default=no_default):
        self.N = len(seqs)
        if self.N < 2:
            raise TypeError('Too few sequences given (min 2 required)')
        if default == no_default:
            self.iters = zip(*seqs)
        else:
            self.iters = zip_longest(*seqs, fillvalue=default)
        self.key = key

    def __iter__(self):
        return self

    def __next__(self):
        cdef object val, val2, items
        cdef Py_ssize_t i
        while True:
            items = next(self.iters)
            val = self.key(<object>PyTuple_GET_ITEM(items, 0))
            for i in range(1, self.N):
                val2 = self.key(<object>PyTuple_GET_ITEM(items, i))
                if PyObject_RichCompareBool(val, val2, Py_NE):
                    return items

cdef class _diff_identity:
    def __cinit__(self, object seqs, object default=no_default):
        self.N = len(seqs)
        if self.N < 2:
            raise TypeError('Too few sequences given (min 2 required)')
        if default == no_default:
            self.iters = zip(*seqs)
        else:
            self.iters = zip_longest(*seqs, fillvalue=default)

    def __iter__(self):
        return self

    def __next__(self):
        cdef object val, val2, items
        cdef Py_ssize_t i
        while True:
            items = next(self.iters)
            val = <object>PyTuple_GET_ITEM(items, 0)
            for i in range(1, self.N):
                val2 = <object>PyTuple_GET_ITEM(items, i)
                if PyObject_RichCompareBool(val, val2, Py_NE):
                    return items


cdef object c_diff(object seqs, object default=no_default, object key=None):
    if key is None:
        return _diff_identity(seqs, default=default)
    else:
        return _diff_key(seqs, key, default=default)


def diff(*seqs, **kwargs):
    """
    Return those items that differ between sequences

    >>> list(diff([1, 2, 3], [1, 2, 10, 100]))
    [(3, 10)]

    Shorter sequences may be padded with a ``default`` value:

    >>> list(diff([1, 2, 3], [1, 2, 10, 100], default=None))
    [(3, 10), (None, 100)]

    A ``key`` function may also be applied to each item to use during
    comparisons:

    >>> list(diff(['apples', 'bananas'], ['Apples', 'Oranges'], key=str.lower))
    [('bananas', 'Oranges')]
    """
    N = len(seqs)
    if N == 1 and isinstance(seqs[0], list):
        seqs = seqs[0]
    default = kwargs.get('default', no_default)
    key = kwargs.get('key')
    return c_diff(seqs, default=default, key=key)


cpdef object topk(Py_ssize_t k, object seq, object key=None):
    """
    Find the k largest elements of a sequence

    Operates lazily in ``n*log(k)`` time

    >>> topk(2, [1, 100, 10, 1000])
    (1000, 100)

    Use a key function to change sorted order

    >>> topk(2, ['Alice', 'Bob', 'Charlie', 'Dan'], key=len)
    ('Charlie', 'Alice')

    See also:
        heapq.nlargest
    """
    cdef object item, val, top
    cdef object it = iter(seq)
    cdef object _heapreplace = heapreplace
    cdef Py_ssize_t i = k
    cdef list pq = []

    if key is not None and not callable(key):
        key = getter(key)

    if k < 2:
        if k < 1:
            return ()
        top = list(take(1, it))
        if len(top) == 0:
            return ()
        it = concatv(top, it)
        if key is None:
            return (max(it),)
        else:
            return (max(it, key=key),)

    for item in it:
        if key is None:
            PyList_Append(pq, (item, i))
        else:
            PyList_Append(pq, (key(item), i, item))
        i -= 1
        if i == 0:
            break
    if i != 0:
        pq.sort(reverse=True)
        k = 0 if key is None else 2
        return tuple([item[k] for item in pq])

    heapify(pq)
    top = pq[0][0]
    if key is None:
        for item in it:
            if top < item:
                _heapreplace(pq, (item, i))
                top = pq[0][0]
                i -= 1
    else:
        for item in it:
            val = key(item)
            if top < val:
                _heapreplace(pq, (val, i, item))
                top = pq[0][0]
                i -= 1

    pq.sort(reverse=True)
    k = 0 if key is None else 2
    return tuple([item[k] for item in pq])


cpdef object peek(object seq):
    """
    Retrieve the next element of a sequence

    Returns the first element and an iterable equivalent to the original
    sequence, still having the element retrieved.

    >>> seq = [0, 1, 2, 3, 4]
    >>> first, seq = peek(seq)
    >>> first
    0
    >>> list(seq)
    [0, 1, 2, 3, 4]
    """
    iterator = iter(seq)
    item = next(iterator)
    return item, chain((item,), iterator)


cpdef object peekn(Py_ssize_t n, object seq):
    """
    Retrieve the next n elements of a sequence

    Returns a tuple of the first n elements and an iterable equivalent
    to the original, still having the elements retrieved.

    >>> seq = [0, 1, 2, 3, 4]
    >>> first_two, seq = peekn(2, seq)
    >>> first_two
    (0, 1)
    >>> list(seq)
    [0, 1, 2, 3, 4]
    """
    iterator = iter(seq)
    peeked = tuple(take(n, iterator))
    return peeked, chain(iter(peeked), iterator)


cdef class random_sample:
    """ random_sample(prob, seq, random_state=None)

    Return elements from a sequence with probability of prob

    Returns a lazy iterator of random items from seq.

    ``random_sample`` considers each item independently and without
    replacement. See below how the first time it returned 13 items and the
    next time it returned 6 items.

    >>> seq = list(range(100))
    >>> list(random_sample(0.1, seq)) # doctest: +SKIP
    [6, 9, 19, 35, 45, 50, 58, 62, 68, 72, 78, 86, 95]
    >>> list(random_sample(0.1, seq)) # doctest: +SKIP
    [6, 44, 54, 61, 69, 94]

    Providing an integer seed for ``random_state`` will result in
    deterministic sampling. Given the same seed it will return the same sample
    every time.

    >>> list(random_sample(0.1, seq, random_state=2016))
    [7, 9, 19, 25, 30, 32, 34, 48, 59, 60, 81, 98]
    >>> list(random_sample(0.1, seq, random_state=2016))
    [7, 9, 19, 25, 30, 32, 34, 48, 59, 60, 81, 98]

    ``random_state`` can also be any object with a method ``random`` that
    returns floats between 0.0 and 1.0 (exclusive).

    >>> from random import Random
    >>> randobj = Random(2016)
    >>> list(random_sample(0.1, seq, random_state=randobj))
    [7, 9, 19, 25, 30, 32, 34, 48, 59, 60, 81, 98]
    """
    def __cinit__(self, object prob, object seq, random_state=None):
        float(prob)
        self.prob = prob
        self.iter_seq = iter(seq)
        if not hasattr(random_state, 'random'):
            from random import Random

            random_state = Random(random_state)
        self.random_func = random_state.random

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            if self.random_func() < self.prob:
                return next(self.iter_seq)
            next(self.iter_seq)
