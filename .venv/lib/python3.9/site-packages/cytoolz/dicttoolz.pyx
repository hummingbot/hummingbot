from cpython.dict cimport (PyDict_Check, PyDict_CheckExact, PyDict_GetItem,
                           PyDict_New, PyDict_Next,
                           PyDict_SetItem, PyDict_Update, PyDict_DelItem)
from cpython.list cimport PyList_Append, PyList_New
from cpython.object cimport PyObject_SetItem
from cpython.ref cimport PyObject, Py_DECREF, Py_INCREF, Py_XDECREF

# Locally defined bindings that differ from `cython.cpython` bindings
from cytoolz.cpython cimport PyDict_Next_Compat, PtrIter_Next

from copy import copy
from collections.abc import Mapping


__all__ = ['merge', 'merge_with', 'valmap', 'keymap', 'itemmap', 'valfilter',
           'keyfilter', 'itemfilter', 'assoc', 'dissoc', 'assoc_in', 'get_in',
           'update_in']


cdef class _iter_mapping:
    """ Keep a handle on the current item to prevent memory clean up too early"""
    def __cinit__(self, object it):
        self.it = it
        self.cur = None

    def __iter__(self):
        return self

    def __next__(self):
        self.cur = next(self.it)
        return self.cur


cdef int PyMapping_Next(object p, Py_ssize_t *ppos, PyObject* *pkey, PyObject* *pval) except -1:
    """Mimic "PyDict_Next" interface, but for any mapping"""
    cdef PyObject *obj
    obj = PtrIter_Next(p)
    if obj is NULL:
        return 0
    pkey[0] = <PyObject*>(<object>obj)[0]
    pval[0] = <PyObject*>(<object>obj)[1]
    Py_XDECREF(obj)  # removing this results in memory leak
    return 1


cdef f_map_next get_map_iter(object d, PyObject* *ptr) except NULL:
    """Return function pointer to perform iteration over object returned in ptr.

    The returned function signature matches "PyDict_Next".  If ``d`` is a dict,
    then the returned function *is* PyDict_Next, so iteration wil be very fast.

    The object returned through ``ptr`` needs to have its reference count
    reduced by one once the caller "owns" the object.

    This function lets us control exactly how iteration should be performed
    over a given mapping.  The current rules are:

    1) If ``d`` is exactly a dict, use PyDict_Next
    2) If ``d`` is subtype of dict, use PyMapping_Next.  This lets the user
       control the order iteration, such as for ordereddict.
    3) If using PyMapping_Next, iterate using ``iteritems`` if possible,
       otherwise iterate using ``items``.

    """
    cdef object val
    cdef f_map_next rv
    if PyDict_CheckExact(d):
        val = d
        rv = &PyDict_Next_Compat
    else:
        val = _iter_mapping(iter(d.items()))
        rv = &PyMapping_Next
    Py_INCREF(val)
    ptr[0] = <PyObject*>val
    return rv


cdef get_factory(name, kwargs):
    factory = kwargs.pop('factory', dict)
    if kwargs:
        raise TypeError("{0}() got an unexpected keyword argument "
                        "'{1}'".format(name, kwargs.popitem()[0]))
    return factory


cdef object c_merge(object dicts, object factory=dict):
    cdef object rv
    rv = factory()
    if PyDict_CheckExact(rv):
        for d in dicts:
            PyDict_Update(rv, d)
    else:
        for d in dicts:
            rv.update(d)
    return rv


def merge(*dicts, **kwargs):
    """
    Merge a collection of dictionaries

    >>> merge({1: 'one'}, {2: 'two'})
    {1: 'one', 2: 'two'}

    Later dictionaries have precedence

    >>> merge({1: 2, 3: 4}, {3: 3, 4: 4})
    {1: 2, 3: 3, 4: 4}

    See Also:
        merge_with
    """
    if len(dicts) == 1 and not isinstance(dicts[0], Mapping):
        dicts = dicts[0]
    factory = get_factory('merge', kwargs)
    return c_merge(dicts, factory)


cdef object c_merge_with(object func, object dicts, object factory=dict):
    cdef:
        dict result
        object rv, d
        list seq
        f_map_next f
        PyObject *obj
        PyObject *pkey
        PyObject *pval
        Py_ssize_t pos

    result = PyDict_New()
    rv = factory()
    for d in dicts:
        f = get_map_iter(d, &obj)
        d = <object>obj
        Py_DECREF(d)
        pos = 0
        while f(d, &pos, &pkey, &pval):
            obj = PyDict_GetItem(result, <object>pkey)
            if obj is NULL:
                seq = PyList_New(0)
                PyList_Append(seq, <object>pval)
                PyDict_SetItem(result, <object>pkey, seq)
            else:
                PyList_Append(<object>obj, <object>pval)

    f = get_map_iter(result, &obj)
    d = <object>obj
    Py_DECREF(d)
    pos = 0
    while f(d, &pos, &pkey, &pval):
        PyObject_SetItem(rv, <object>pkey, func(<object>pval))
    return rv


def merge_with(func, *dicts, **kwargs):
    """
    Merge dictionaries and apply function to combined values

    A key may occur in more than one dict, and all values mapped from the key
    will be passed to the function as a list, such as func([val1, val2, ...]).

    >>> merge_with(sum, {1: 1, 2: 2}, {1: 10, 2: 20})
    {1: 11, 2: 22}

    >>> merge_with(first, {1: 1, 2: 2}, {2: 20, 3: 30})  # doctest: +SKIP
    {1: 1, 2: 2, 3: 30}

    See Also:
        merge
    """

    if len(dicts) == 1 and not isinstance(dicts[0], Mapping):
        dicts = dicts[0]
    factory = get_factory('merge_with', kwargs)
    return c_merge_with(func, dicts, factory)


cpdef object valmap(object func, object d, object factory=dict):
    """
    Apply function to values of dictionary

    >>> bills = {"Alice": [20, 15, 30], "Bob": [10, 35]}
    >>> valmap(sum, bills)  # doctest: +SKIP
    {'Alice': 65, 'Bob': 45}

    See Also:
        keymap
        itemmap
    """
    cdef:
        object rv
        f_map_next f
        PyObject *obj
        PyObject *pkey
        PyObject *pval
        Py_ssize_t pos = 0

    rv = factory()
    f = get_map_iter(d, &obj)
    d = <object>obj
    Py_DECREF(d)
    while f(d, &pos, &pkey, &pval):
        rv[<object>pkey] = func(<object>pval)
    return rv


cpdef object keymap(object func, object d, object factory=dict):
    """
    Apply function to keys of dictionary

    >>> bills = {"Alice": [20, 15, 30], "Bob": [10, 35]}
    >>> keymap(str.lower, bills)  # doctest: +SKIP
    {'alice': [20, 15, 30], 'bob': [10, 35]}

    See Also:
        valmap
        itemmap
    """
    cdef:
        object rv
        f_map_next f
        PyObject *obj
        PyObject *pkey
        PyObject *pval
        Py_ssize_t pos = 0

    rv = factory()
    f = get_map_iter(d, &obj)
    d = <object>obj
    Py_DECREF(d)
    while f(d, &pos, &pkey, &pval):
        rv[func(<object>pkey)] = <object>pval
    return rv


cpdef object itemmap(object func, object d, object factory=dict):
    """
    Apply function to items of dictionary

    >>> accountids = {"Alice": 10, "Bob": 20}
    >>> itemmap(reversed, accountids)  # doctest: +SKIP
    {10: "Alice", 20: "Bob"}

    See Also:
        keymap
        valmap
    """
    cdef:
        object rv, k, v
        f_map_next f
        PyObject *obj
        PyObject *pkey
        PyObject *pval
        Py_ssize_t pos = 0

    rv = factory()
    f = get_map_iter(d, &obj)
    d = <object>obj
    Py_DECREF(d)
    while f(d, &pos, &pkey, &pval):
        k, v = func((<object>pkey, <object>pval))
        rv[k] = v
    return rv


cpdef object valfilter(object predicate, object d, object factory=dict):
    """
    Filter items in dictionary by value

    >>> iseven = lambda x: x % 2 == 0
    >>> d = {1: 2, 2: 3, 3: 4, 4: 5}
    >>> valfilter(iseven, d)
    {1: 2, 3: 4}

    See Also:
        keyfilter
        itemfilter
        valmap
    """
    cdef:
        object rv
        f_map_next f
        PyObject *obj
        PyObject *pkey
        PyObject *pval
        Py_ssize_t pos = 0

    rv = factory()
    f = get_map_iter(d, &obj)
    d = <object>obj
    Py_DECREF(d)
    while f(d, &pos, &pkey, &pval):
        if predicate(<object>pval):
            rv[<object>pkey] = <object>pval
    return rv


cpdef object keyfilter(object predicate, object d, object factory=dict):
    """
    Filter items in dictionary by key

    >>> iseven = lambda x: x % 2 == 0
    >>> d = {1: 2, 2: 3, 3: 4, 4: 5}
    >>> keyfilter(iseven, d)
    {2: 3, 4: 5}

    See Also:
        valfilter
        itemfilter
        keymap
    """
    cdef:
        object rv
        f_map_next f
        PyObject *obj
        PyObject *pkey
        PyObject *pval
        Py_ssize_t pos = 0

    rv = factory()
    f = get_map_iter(d, &obj)
    d = <object>obj
    Py_DECREF(d)
    while f(d, &pos, &pkey, &pval):
        if predicate(<object>pkey):
            rv[<object>pkey] = <object>pval
    return rv


cpdef object itemfilter(object predicate, object d, object factory=dict):
    """
    Filter items in dictionary by item

    >>> def isvalid(item):
    ...     k, v = item
    ...     return k % 2 == 0 and v < 4

    >>> d = {1: 2, 2: 3, 3: 4, 4: 5}
    >>> itemfilter(isvalid, d)
    {2: 3}

    See Also:
        keyfilter
        valfilter
        itemmap
    """
    cdef:
        object rv, k, v
        f_map_next f
        PyObject *obj
        PyObject *pkey
        PyObject *pval
        Py_ssize_t pos = 0

    rv = factory()
    f = get_map_iter(d, &obj)
    d = <object>obj
    Py_DECREF(d)
    while f(d, &pos, &pkey, &pval):
        k = <object>pkey
        v = <object>pval
        if predicate((k, v)):
            rv[k] = v
    return rv


cpdef object assoc(object d, object key, object value, object factory=dict):
    """
    Return a new dict with new key value pair

    New dict has d[key] set to value. Does not modify the initial dictionary.

    >>> assoc({'x': 1}, 'x', 2)
    {'x': 2}
    >>> assoc({'x': 1}, 'y', 3)   # doctest: +SKIP
    {'x': 1, 'y': 3}
    """
    cdef object rv
    rv = factory()
    if PyDict_CheckExact(rv):
        PyDict_Update(rv, d)
    else:
        rv.update(d)
    rv[key] = value
    return rv


cpdef object assoc_in(object d, object keys, object value, object factory=dict):
    """
    Return a new dict with new, potentially nested, key value pair

    >>> purchase = {'name': 'Alice',
    ...             'order': {'items': ['Apple', 'Orange'],
    ...                       'costs': [0.50, 1.25]},
    ...             'credit card': '5555-1234-1234-1234'}
    >>> assoc_in(purchase, ['order', 'costs'], [0.25, 1.00]) # doctest: +SKIP
    {'credit card': '5555-1234-1234-1234',
     'name': 'Alice',
     'order': {'costs': [0.25, 1.00], 'items': ['Apple', 'Orange']}}
    """
    cdef object prevkey, key
    cdef object rv, inner, dtemp
    prevkey, keys = keys[0], keys[1:]
    rv = factory()
    if PyDict_CheckExact(rv):
        PyDict_Update(rv, d)
    else:
        rv.update(d)
    inner = rv

    for key in keys:
        if prevkey in d:
            d = d[prevkey]
            dtemp = factory()
            if PyDict_CheckExact(dtemp):
                PyDict_Update(dtemp, d)
            else:
                dtemp.update(d)
        else:
            d = factory()
            dtemp = d
        inner[prevkey] = dtemp
        prevkey = key
        inner = dtemp

    inner[prevkey] = value
    return rv


cdef object c_dissoc(object d, object keys, object factory=dict):
    # implementation copied from toolz.  Not benchmarked.
    cdef object rv
    rv = factory()
    if len(keys) < len(d) * 0.6:
        rv.update(d)
        for key in keys:
            if key in rv:
                del rv[key]
    else:
        remaining = set(d)
        remaining.difference_update(keys)
        for k in remaining:
            rv[k] = d[k]
    return rv


def dissoc(d, *keys, **kwargs):
    """
    Return a new dict with the given key(s) removed.

    New dict has d[key] deleted for each supplied key.
    Does not modify the initial dictionary.

    >>> dissoc({'x': 1, 'y': 2}, 'y')
    {'x': 1}
    >>> dissoc({'x': 1, 'y': 2}, 'y', 'x')
    {}
    >>> dissoc({'x': 1}, 'y') # Ignores missing keys
    {'x': 1}
    """
    return c_dissoc(d, keys, get_factory('dissoc', kwargs))


cpdef object update_in(object d, object keys, object func, object default=None, object factory=dict):
    """
    Update value in a (potentially) nested dictionary

    inputs:
    d - dictionary on which to operate
    keys - list or tuple giving the location of the value to be changed in d
    func - function to operate on that value

    If keys == [k0,..,kX] and d[k0]..[kX] == v, update_in returns a copy of the
    original dictionary with v replaced by func(v), but does not mutate the
    original dictionary.

    If k0 is not a key in d, update_in creates nested dictionaries to the depth
    specified by the keys, with the innermost value set to func(default).

    >>> inc = lambda x: x + 1
    >>> update_in({'a': 0}, ['a'], inc)
    {'a': 1}

    >>> transaction = {'name': 'Alice',
    ...                'purchase': {'items': ['Apple', 'Orange'],
    ...                             'costs': [0.50, 1.25]},
    ...                'credit card': '5555-1234-1234-1234'}
    >>> update_in(transaction, ['purchase', 'costs'], sum) # doctest: +SKIP
    {'credit card': '5555-1234-1234-1234',
     'name': 'Alice',
     'purchase': {'costs': 1.75, 'items': ['Apple', 'Orange']}}

    >>> # updating a value when k0 is not in d
    >>> update_in({}, [1, 2, 3], str, default="bar")
    {1: {2: {3: 'bar'}}}
    >>> update_in({1: 'foo'}, [2, 3, 4], inc, 0)
    {1: 'foo', 2: {3: {4: 1}}}
    """
    cdef object prevkey, key
    cdef object rv, inner, dtemp
    prevkey, keys = keys[0], keys[1:]
    rv = factory()
    if PyDict_CheckExact(rv):
        PyDict_Update(rv, d)
    else:
        rv.update(d)
    inner = rv

    for key in keys:
        if prevkey in d:
            d = d[prevkey]
            dtemp = factory()
            if PyDict_CheckExact(dtemp):
                PyDict_Update(dtemp, d)
            else:
                dtemp.update(d)
        else:
            d = factory()
            dtemp = d
        inner[prevkey] = dtemp
        prevkey = key
        inner = dtemp

    if prevkey in d:
        key = func(d[prevkey])
    else:
        key = func(default)
    inner[prevkey] = key
    return rv


cdef tuple _get_in_exceptions = (KeyError, IndexError, TypeError)


cpdef object get_in(object keys, object coll, object default=None, object no_default=False):
    """
    Returns coll[i0][i1]...[iX] where [i0, i1, ..., iX]==keys.

    If coll[i0][i1]...[iX] cannot be found, returns ``default``, unless
    ``no_default`` is specified, then it raises KeyError or IndexError.

    ``get_in`` is a generalization of ``operator.getitem`` for nested data
    structures such as dictionaries and lists.

    >>> transaction = {'name': 'Alice',
    ...                'purchase': {'items': ['Apple', 'Orange'],
    ...                             'costs': [0.50, 1.25]},
    ...                'credit card': '5555-1234-1234-1234'}
    >>> get_in(['purchase', 'items', 0], transaction)
    'Apple'
    >>> get_in(['name'], transaction)
    'Alice'
    >>> get_in(['purchase', 'total'], transaction)
    >>> get_in(['purchase', 'items', 'apple'], transaction)
    >>> get_in(['purchase', 'items', 10], transaction)
    >>> get_in(['purchase', 'total'], transaction, 0)
    0
    >>> get_in(['y'], {}, no_default=True)
    Traceback (most recent call last):
        ...
    KeyError: 'y'

    See Also:
        itertoolz.get
        operator.getitem
    """
    cdef object item
    try:
        for item in keys:
            coll = coll[item]
        return coll
    except _get_in_exceptions:
        if no_default:
            raise
        return default
