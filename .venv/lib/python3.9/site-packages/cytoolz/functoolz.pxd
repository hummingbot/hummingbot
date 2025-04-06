cpdef object identity(object x)


cdef object c_thread_first(object val, object forms)


cdef object c_thread_last(object val, object forms)


cdef class curry:
    cdef readonly object _sigspec
    cdef readonly object _has_unknown_args
    cdef readonly object func
    cdef readonly tuple args
    cdef readonly dict keywords
    cdef public object __doc__
    cdef public object __name__
    cdef object _module
    cdef object _qualname


cpdef object memoize(object func, object cache=*, object key=*)


cdef class _memoize:
    cdef object func
    cdef object cache
    cdef object key
    cdef bint is_unary
    cdef bint may_have_kwargs


cdef class Compose:
    cdef public object first
    cdef public tuple funcs


cdef object c_compose(object funcs)


cdef object c_compose_left(object funcs)


cdef object c_pipe(object data, object funcs)


cdef class complement:
    cdef object func


cdef class juxt:
    cdef public tuple funcs


cpdef object do(object func, object x)


cpdef object flip(object func, object a, object b)


cpdef object return_none(object exc)


cdef class excepts:
    cdef public object exc
    cdef public object func
    cdef public object handler
