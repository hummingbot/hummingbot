from cpython.ref cimport PyObject

# utility functions to perform iteration over dicts or generic mapping
cdef class _iter_mapping:
    cdef object it
    cdef object cur

ctypedef int (*f_map_next)(object p, Py_ssize_t *ppos, PyObject* *pkey, PyObject* *pval) except -1

cdef f_map_next get_map_iter(object d, PyObject* *ptr) except NULL

cdef int PyMapping_Next(object p, Py_ssize_t *ppos, PyObject* *pkey, PyObject* *pval) except -1


cdef object c_merge(object dicts, object factory=*)


cdef object c_merge_with(object func, object dicts, object factory=*)


cpdef object valmap(object func, object d, object factory=*)


cpdef object keymap(object func, object d, object factory=*)


cpdef object itemmap(object func, object d, object factory=*)


cpdef object valfilter(object predicate, object d, object factory=*)


cpdef object keyfilter(object predicate, object d, object factory=*)


cpdef object itemfilter(object predicate, object d, object factory=*)


cpdef object assoc(object d, object key, object value, object factory=*)


cpdef object assoc_in(object d, object keys, object value, object factory=*)


cdef object c_dissoc(object d, object keys, object factory=*)


cpdef object update_in(object d, object keys, object func, object default=*, object factory=*)


cpdef object get_in(object keys, object coll, object default=*, object no_default=*)
