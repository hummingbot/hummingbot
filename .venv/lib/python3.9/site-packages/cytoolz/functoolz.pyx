import inspect
import sys
from functools import partial
from importlib import import_module
from operator import attrgetter
from types import MethodType
from cytoolz.utils import no_default
import cytoolz._signatures as _sigs

from toolz.functoolz import (InstanceProperty, instanceproperty, is_arity,
                             num_required_args, has_varargs, has_keywords,
                             is_valid_args, is_partial_args)

cimport cython
from cpython.dict cimport PyDict_Merge, PyDict_New
from cpython.object cimport (PyCallable_Check, PyObject_Call, PyObject_CallObject,
                             PyObject_RichCompare, Py_EQ, Py_NE)
from cpython.ref cimport PyObject
from cpython.sequence cimport PySequence_Concat
from cpython.set cimport PyFrozenSet_New
from cpython.tuple cimport PyTuple_Check, PyTuple_GET_SIZE


__all__ = ['identity', 'thread_first', 'thread_last', 'memoize', 'compose', 'compose_left',
           'pipe', 'complement', 'juxt', 'do', 'curry', 'memoize', 'flip',
           'excepts', 'apply']


cpdef object identity(object x):
    """ Identity function. Return x

    >>> identity(3)
    3
    """
    return x


def apply(*func_and_args, **kwargs):
    """
    Applies a function and returns the results

    >>> def double(x): return 2*x
    >>> def inc(x):    return x + 1
    >>> apply(double, 5)
    10

    >>> tuple(map(apply, [double, inc, double], [10, 500, 8000]))
    (20, 501, 16000)
    """
    if not func_and_args:
        raise TypeError('func argument is required')
    return func_and_args[0](*func_and_args[1:], **kwargs)


cdef object c_thread_first(object val, object forms):
    cdef object form, func
    cdef tuple args
    for form in forms:
        if PyCallable_Check(form):
            val = form(val)
        elif PyTuple_Check(form):
            func, args = form[0], (val,) + form[1:]
            val = PyObject_CallObject(func, args)
        else:
            val = None
    return val


def thread_first(val, *forms):
    """
    Thread value through a sequence of functions/forms

    >>> def double(x): return 2*x
    >>> def inc(x):    return x + 1
    >>> thread_first(1, inc, double)
    4

    If the function expects more than one input you can specify those inputs
    in a tuple.  The value is used as the first input.

    >>> def add(x, y): return x + y
    >>> def pow(x, y): return x**y
    >>> thread_first(1, (add, 4), (pow, 2))  # pow(add(1, 4), 2)
    25

    So in general
        thread_first(x, f, (g, y, z))
    expands to
        g(f(x), y, z)

    See Also:
        thread_last
    """
    return c_thread_first(val, forms)


cdef object c_thread_last(object val, object forms):
    cdef object form, func
    cdef tuple args
    for form in forms:
        if PyCallable_Check(form):
            val = form(val)
        elif PyTuple_Check(form):
            func, args = form[0], form[1:] + (val,)
            val = PyObject_CallObject(func, args)
        else:
            val = None
    return val


def thread_last(val, *forms):
    """
    Thread value through a sequence of functions/forms

    >>> def double(x): return 2*x
    >>> def inc(x):    return x + 1
    >>> thread_last(1, inc, double)
    4

    If the function expects more than one input you can specify those inputs
    in a tuple.  The value is used as the last input.

    >>> def add(x, y): return x + y
    >>> def pow(x, y): return x**y
    >>> thread_last(1, (add, 4), (pow, 2))  # pow(2, add(4, 1))
    32

    So in general
        thread_last(x, f, (g, y, z))
    expands to
        g(y, z, f(x))

    >>> def iseven(x):
    ...     return x % 2 == 0
    >>> list(thread_last([1, 2, 3], (map, inc), (filter, iseven)))
    [2, 4]

    See Also:
        thread_first
    """
    return c_thread_last(val, forms)


cdef struct partialobject:
    PyObject _
    PyObject *fn
    PyObject *args
    PyObject *kw
    PyObject *dict
    PyObject *weakreflist


cdef object _partial = partial(lambda: None)


cdef object _empty_kwargs():
    if <object> (<partialobject*> _partial).kw is None:
        return None
    return PyDict_New()


cdef class curry:
    """ curry(self, *args, **kwargs)

    Curry a callable function

    Enables partial application of arguments through calling a function with an
    incomplete set of arguments.

    >>> def mul(x, y):
    ...     return x * y
    >>> mul = curry(mul)

    >>> double = mul(2)
    >>> double(10)
    20

    Also supports keyword arguments

    >>> @curry                  # Can use curry as a decorator
    ... def f(x, y, a=10):
    ...     return a * (x + y)

    >>> add = f(a=1)
    >>> add(2, 3)
    5

    See Also:
        cytoolz.curried - namespace of curried functions
                        https://toolz.readthedocs.io/en/latest/curry.html
    """

    def __cinit__(self, *args, **kwargs):
        if not args:
            raise TypeError('__init__() takes at least 2 arguments (1 given)')
        func, args = args[0], args[1:]
        if not PyCallable_Check(func):
            raise TypeError("Input must be callable")

        # curry- or functools.partial-like object?  Unpack and merge arguments
        if (hasattr(func, 'func')
                and hasattr(func, 'args')
                and hasattr(func, 'keywords')
                and isinstance(func.args, tuple)):
            if func.keywords:
                PyDict_Merge(kwargs, func.keywords, False)
                ## Equivalent to:
                # for key, val in func.keywords.items():
                #     if key not in kwargs:
                #         kwargs[key] = val
            args = func.args + args
            func = func.func

        self.func = func
        self.args = args
        self.keywords = kwargs if kwargs else _empty_kwargs()
        self.__doc__ = getattr(func, '__doc__', None)
        self.__name__ = getattr(func, '__name__', '<curry>')
        self._module = getattr(func, '__module__', None)
        self._qualname = getattr(func, '__qualname__', None)
        self._sigspec = None
        self._has_unknown_args = None

    property __module__:
        def __get__(self):
            return self._module

        def __set__(self, val):
            self._module = val

    property __qualname__:
        def __get__(self):
            return self._qualname

        def __set__(self, val):
            self._qualname = val

    def __str__(self):
        return str(self.func)

    def __repr__(self):
        return repr(self.func)

    def __hash__(self):
        return hash((self.func, self.args,
                     frozenset(self.keywords.items()) if self.keywords
                     else None))

    def __richcmp__(self, other, int op):
        is_equal = (isinstance(other, curry) and self.func == other.func and
                self.args == other.args and self.keywords == other.keywords)
        if op == Py_EQ:
            return is_equal
        if op == Py_NE:
            return not is_equal
        return PyObject_RichCompare(id(self), id(other), op)

    def __call__(self, *args, **kwargs):
        cdef object val

        if PyTuple_GET_SIZE(args) == 0:
            args = self.args
        elif PyTuple_GET_SIZE(self.args) != 0:
            args = PySequence_Concat(self.args, args)
        if self.keywords is not None:
            PyDict_Merge(kwargs, self.keywords, False)
        try:
            return self.func(*args, **kwargs)
        except TypeError as val:
            if self._should_curry_internal(args, kwargs, val):
                return type(self)(self.func, *args, **kwargs)
            raise

    def _should_curry(self, args, kwargs, exc=None):
        if PyTuple_GET_SIZE(args) == 0:
            args = self.args
        elif PyTuple_GET_SIZE(self.args) != 0:
            args = PySequence_Concat(self.args, args)
        if self.keywords is not None:
            PyDict_Merge(kwargs, self.keywords, False)
        return self._should_curry_internal(args, kwargs)

    def _should_curry_internal(self, args, kwargs, exc=None):
        func = self.func

        # `toolz` has these three lines
        #args = self.args + args
        #if self.keywords:
        #    kwargs = dict(self.keywords, **kwargs)

        if self._sigspec is None:
            sigspec = self._sigspec = _sigs.signature_or_spec(func)
            self._has_unknown_args = has_varargs(func, sigspec) is not False
        else:
            sigspec = self._sigspec

        if is_partial_args(func, args, kwargs, sigspec) is False:
            # Nothing can make the call valid
            return False
        elif self._has_unknown_args:
            # The call may be valid and raised a TypeError, but we curry
            # anyway because the function may have `*args`.  This is useful
            # for decorators with signature `func(*args, **kwargs)`.
            return True
        elif not is_valid_args(func, args, kwargs, sigspec):
            # Adding more arguments may make the call valid
            return True
        else:
            # There was a genuine TypeError
            return False

    def bind(self, *args, **kwargs):
        return type(self)(self, *args, **kwargs)

    def call(self, *args, **kwargs):
        cdef object val

        if PyTuple_GET_SIZE(args) == 0:
            args = self.args
        elif PyTuple_GET_SIZE(self.args) != 0:
            args = PySequence_Concat(self.args, args)
        if self.keywords is not None:
            PyDict_Merge(kwargs, self.keywords, False)
        return self.func(*args, **kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return type(self)(self, instance)

    property __signature__:
        def __get__(self):
            sig = inspect.signature(self.func)
            args = self.args or ()
            keywords = self.keywords or {}
            if is_partial_args(self.func, args, keywords, sig) is False:
                raise TypeError('curry object has incorrect arguments')

            params = list(sig.parameters.values())
            skip = 0
            for param in params[:len(args)]:
                if param.kind == param.VAR_POSITIONAL:
                    break
                skip += 1

            kwonly = False
            newparams = []
            for param in params[skip:]:
                kind = param.kind
                default = param.default
                if kind == param.VAR_KEYWORD:
                    pass
                elif kind == param.VAR_POSITIONAL:
                    if kwonly:
                        continue
                elif param.name in keywords:
                    default = keywords[param.name]
                    kind = param.KEYWORD_ONLY
                    kwonly = True
                else:
                    if kwonly:
                        kind = param.KEYWORD_ONLY
                    if default is param.empty:
                        default = no_default
                newparams.append(param.replace(default=default, kind=kind))

            return sig.replace(parameters=newparams)

    def __reduce__(self):
        func = self.func
        modname = getattr(func, '__module__', None)
        qualname = getattr(func, '__qualname__', None)
        if qualname is None:
            qualname = getattr(func, '__name__', None)
        is_decorated = None
        if modname and qualname:
            attrs = []
            obj = import_module(modname)
            for attr in qualname.split('.'):
                if isinstance(obj, curry):
                    attrs.append('func')
                    obj = obj.func
                obj = getattr(obj, attr, None)
                if obj is None:
                    break
                attrs.append(attr)
            if isinstance(obj, curry) and obj.func is func:
                is_decorated = obj is self
                qualname = '.'.join(attrs)
                func = '%s:%s' % (modname, qualname)

        state = (type(self), func, self.args, self.keywords, is_decorated)
        return (_restore_curry, state)


cpdef object _restore_curry(cls, func, args, kwargs, is_decorated):
    if isinstance(func, str):
        modname, qualname = func.rsplit(':', 1)
        obj = import_module(modname)
        for attr in qualname.split('.'):
            obj = getattr(obj, attr)
        if is_decorated:
            return obj
        func = obj.func
    obj = cls(func, *args, **(kwargs or {}))
    return obj


cpdef object memoize(object func, object cache=None, object key=None):
    """
    Cache a function's result for speedy future evaluation

    Considerations:
        Trades memory for speed.
        Only use on pure functions.

    >>> def add(x, y):  return x + y
    >>> add = memoize(add)

    Or use as a decorator

    >>> @memoize
    ... def add(x, y):
    ...     return x + y

    Use the ``cache`` keyword to provide a dict-like object as an initial cache

    >>> @memoize(cache={(1, 2): 3})
    ... def add(x, y):
    ...     return x + y

    Note that the above works as a decorator because ``memoize`` is curried.

    It is also possible to provide a ``key(args, kwargs)`` function that
    calculates keys used for the cache, which receives an ``args`` tuple and
    ``kwargs`` dict as input, and must return a hashable value.  However,
    the default key function should be sufficient most of the time.

    >>> # Use key function that ignores extraneous keyword arguments
    >>> @memoize(key=lambda args, kwargs: args)
    ... def add(x, y, verbose=False):
    ...     if verbose:
    ...         print('Calculating %s + %s' % (x, y))
    ...     return x + y
    """
    return _memoize(func, cache, key)


cdef class _memoize:

    property __doc__:
        def __get__(self):
            return self.func.__doc__

    property __name__:
        def __get__(self):
            return self.func.__name__

    property __wrapped__:
        def __get__(self):
            return self.func

    def __cinit__(self, func, cache, key):
        self.func = func
        if cache is None:
            self.cache = PyDict_New()
        else:
            self.cache = cache
        self.key = key

        try:
            self.may_have_kwargs = has_keywords(func) is not False
            # Is unary function (single arg, no variadic argument or keywords)?
            self.is_unary = is_arity(1, func)
        except TypeError:
            self.is_unary = False
            self.may_have_kwargs = True

    def __call__(self, *args, **kwargs):
        cdef object key
        if self.key is not None:
            key = self.key(args, kwargs)
        elif self.is_unary:
            key = args[0]
        elif self.may_have_kwargs:
            key = (args or None,
                   PyFrozenSet_New(kwargs.items()) if kwargs else None)
        else:
            key = args

        if key in self.cache:
            return self.cache[key]
        else:
            result = PyObject_Call(self.func, args, kwargs)
            self.cache[key] = result
            return result

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return curry(self, instance)


cdef class Compose:
    """ Compose(self, *funcs)

    A composition of functions

    See Also:
        compose
    """
    # fix for #103, note: we cannot use __name__ at module-scope in cython
    __module__ = 'cytooz.functoolz'

    def __cinit__(self, *funcs):
        self.first = funcs[-1]
        self.funcs = tuple(reversed(funcs[:-1]))

    def __call__(self, *args, **kwargs):
        cdef object func, ret
        ret = PyObject_Call(self.first, args, kwargs)
        for func in self.funcs:
            ret = func(ret)
        return ret

    def __reduce__(self):
        return (Compose, (self.first,), self.funcs)

    def __setstate__(self, state):
        self.funcs = state

    def __repr__(self):
        return '{.__class__.__name__}{!r}'.format(
            self, tuple(reversed((self.first, ) + self.funcs)))

    def __eq__(self, other):
        if isinstance(other, Compose):
            return other.first == self.first and other.funcs == self.funcs
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, Compose):
            return other.first != self.first or other.funcs != self.funcs
        return NotImplemented

    def __hash__(self):
        return hash(self.first) ^ hash(self.funcs)

    def __get__(self, obj, objtype):
        if obj is None:
            return self
        else:
            return MethodType(self, obj)

    property __wrapped__:
        def __get__(self):
            return self.first

    property __signature__:
        def __get__(self):
            base = inspect.signature(self.first)
            last = inspect.signature(self.funcs[-1])
            return base.replace(return_annotation=last.return_annotation)

    property __name__:
        def __get__(self):
            try:
                return '_of_'.join(
                    f.__name__ for f in reversed((self.first,) + self.funcs)
                )
            except AttributeError:
                return type(self).__name__

    property __doc__:
        def __get__(self):
            def composed_doc(*fs):
                """Generate a docstring for the composition of fs.
                """
                if not fs:
                    # Argument name for the docstring.
                    return '*args, **kwargs'

                return '{f}({g})'.format(f=fs[0].__name__, g=composed_doc(*fs[1:]))

            try:
                return (
                    'lambda *args, **kwargs: ' +
                    composed_doc(*reversed((self.first,) + self.funcs))
                )
            except AttributeError:
                # One of our callables does not have a `__name__`, whatever.
                return 'A composition of functions'


cdef object c_compose(object funcs):
    if not funcs:
        return identity
    elif len(funcs) == 1:
        return funcs[0]
    else:
        return Compose(*funcs)


def compose(*funcs):
    """
    Compose functions to operate in series.

    Returns a function that applies other functions in sequence.

    Functions are applied from right to left so that
    ``compose(f, g, h)(x, y)`` is the same as ``f(g(h(x, y)))``.

    If no arguments are provided, the identity function (f(x) = x) is returned.

    >>> inc = lambda i: i + 1
    >>> compose(str, inc)(3)
    '4'

    See Also:
        compose_left
        pipe
    """
    return c_compose(funcs)


cdef object c_compose_left(object funcs):
    if not funcs:
        return identity
    elif len(funcs) == 1:
        return funcs[0]
    else:
        return Compose(*reversed(funcs))


def compose_left(*funcs):
    """
    Compose functions to operate in series.

    Returns a function that applies other functions in sequence.

    Functions are applied from left to right so that
    ``compose_left(f, g, h)(x, y)`` is the same as ``h(g(f(x, y)))``.

    If no arguments are provided, the identity function (f(x) = x) is returned.

    >>> inc = lambda i: i + 1
    >>> compose_left(inc, str)(3)
    '4'

    See Also:
        compose
        pipe
    """
    return c_compose_left(funcs)


cdef object c_pipe(object data, object funcs):
    cdef object func
    for func in funcs:
        data = func(data)
    return data


def pipe(data, *funcs):
    """
    Pipe a value through a sequence of functions

    I.e. ``pipe(data, f, g, h)`` is equivalent to ``h(g(f(data)))``

    We think of the value as progressing through a pipe of several
    transformations, much like pipes in UNIX

    ``$ cat data | f | g | h``

    >>> double = lambda i: 2 * i
    >>> pipe(3, double, str)
    '6'

    See Also:
        compose
        compose_left
        thread_first
        thread_last
    """
    return c_pipe(data, funcs)


cdef class complement:
    """ complement(func)

    Convert a predicate function to its logical complement.

    In other words, return a function that, for inputs that normally
    yield True, yields False, and vice-versa.

    >>> def iseven(n): return n % 2 == 0
    >>> isodd = complement(iseven)
    >>> iseven(2)
    True
    >>> isodd(2)
    False
    """
    def __cinit__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        return not PyObject_Call(self.func, args, kwargs)  # use PyObject_Not?

    def __reduce__(self):
        return (complement, (self.func,))


cdef class juxt:
    """ juxt(self, *funcs)

    Creates a function that calls several functions with the same arguments

    Takes several functions and returns a function that applies its arguments
    to each of those functions then returns a tuple of the results.

    Name comes from juxtaposition: the fact of two things being seen or placed
    close together with contrasting effect.

    >>> inc = lambda x: x + 1
    >>> double = lambda x: x * 2
    >>> juxt(inc, double)(10)
    (11, 20)
    >>> juxt([inc, double])(10)
    (11, 20)
    """
    def __cinit__(self, *funcs):
        if len(funcs) == 1 and not PyCallable_Check(funcs[0]):
            funcs = funcs[0]
        self.funcs = tuple(funcs)

    def __call__(self, *args, **kwargs):
        if kwargs:
            return tuple(PyObject_Call(func, args, kwargs) for func in self.funcs)
        else:
            return tuple(PyObject_CallObject(func, args) for func in self.funcs)

    def __reduce__(self):
        return (juxt, (self.funcs,))


cpdef object do(object func, object x):
    """
    Runs ``func`` on ``x``, returns ``x``

    Because the results of ``func`` are not returned, only the side
    effects of ``func`` are relevant.

    Logging functions can be made by composing ``do`` with a storage function
    like ``list.append`` or ``file.write``

    >>> from cytoolz import compose
    >>> from cytoolz.curried import do

    >>> log = []
    >>> inc = lambda x: x + 1
    >>> inc = compose(inc, do(log.append))
    >>> inc(1)
    2
    >>> inc(11)
    12
    >>> log
    [1, 11]
    """
    func(x)
    return x


cpdef object flip(object func, object a, object b):
    """
    Call the function call with the arguments flipped

    This function is curried.

    >>> def div(a, b):
    ...     return a // b
    ...
    >>> flip(div, 2, 6)
    3
    >>> div_by_two = flip(div, 2)
    >>> div_by_two(4)
    2

    This is particularly useful for built in functions and functions defined
    in C extensions that accept positional only arguments. For example:
    isinstance, issubclass.

    >>> data = [1, 'a', 'b', 2, 1.5, object(), 3]
    >>> only_ints = list(filter(flip(isinstance, int), data))
    >>> only_ints
    [1, 2, 3]
    """
    return PyObject_CallObject(func, (b, a))


_flip = flip  # uncurried


cpdef object return_none(object exc):
    """
    Returns None.
    """
    return None


cdef class excepts:
    """ excepts(self, exc, func, handler=return_none)

    A wrapper around a function to catch exceptions and
    dispatch to a handler.

    This is like a functional try/except block, in the same way that
    ifexprs are functional if/else blocks.

    Examples
    --------
    >>> excepting = excepts(
    ...     ValueError,
    ...     lambda a: [1, 2].index(a),
    ...     lambda _: -1,
    ... )
    >>> excepting(1)
    0
    >>> excepting(3)
    -1

    Multiple exceptions and default except clause.

    >>> excepting = excepts((IndexError, KeyError), lambda a: a[0])
    >>> excepting([])
    >>> excepting([1])
    1
    >>> excepting({})
    >>> excepting({0: 1})
    1
    """

    def __cinit__(self, exc, func, handler=return_none):
        self.exc = exc
        self.func = func
        self.handler = handler

    def __call__(self, *args, **kwargs):
        try:
            return self.func(*args, **kwargs)
        except self.exc as e:
            return self.handler(e)

    property __name__:
        def __get__(self):
            exc = self.exc
            try:
                if isinstance(exc, tuple):
                    exc_name = '_or_'.join(map(attrgetter('__name__'), exc))
                else:
                    exc_name = exc.__name__
                return '%s_excepting_%s' % (self.func.__name__, exc_name)
            except AttributeError:
                return 'excepting'

    property __doc__:
        def __get__(self):
            from textwrap import dedent

            exc = self.exc
            try:
                if isinstance(exc, tuple):
                    exc_name = '(%s)' % ', '.join(
                        map(attrgetter('__name__'), exc),
                    )
                else:
                    exc_name = exc.__name__

                return dedent(
                    """\
                    A wrapper around {inst.func.__name__!r} that will except:
                    {exc}
                    and handle any exceptions with {inst.handler.__name__!r}.

                    Docs for {inst.func.__name__!r}:
                    {inst.func.__doc__}

                    Docs for {inst.handler.__name__!r}:
                    {inst.handler.__doc__}
                    """
                ).format(
                    inst=self,
                    exc=exc_name,
                )
            except AttributeError:
                return type(self).__doc__
