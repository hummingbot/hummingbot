import inspect
import cytoolz

from types import BuiltinFunctionType, FunctionType
from cytoolz import curry, identity, keyfilter, valfilter, merge_with
from dev_skip_test import dev_skip_test


@curry
def isfrommod(modname, func):
    mod = getattr(func, '__module__', '') or ''
    return mod.startswith(modname) or 'toolz.functoolz.curry' in str(type(func))


@dev_skip_test
def test_class_sigs():
    """ Test that all ``cdef class`` extension types in ``cytoolz`` have
        correctly embedded the function signature as done in ``toolz``.
    """
    import toolz
    # only consider items created in both `toolz` and `cytoolz`
    toolz_dict = valfilter(isfrommod('toolz'), toolz.__dict__)
    cytoolz_dict = valfilter(isfrommod('cytoolz'), cytoolz.__dict__)

    # only test `cdef class` extensions from `cytoolz`
    cytoolz_dict = valfilter(lambda x: not isinstance(x, BuiltinFunctionType),
                             cytoolz_dict)

    # full API coverage should be tested elsewhere
    toolz_dict = keyfilter(lambda x: x in cytoolz_dict, toolz_dict)
    cytoolz_dict = keyfilter(lambda x: x in toolz_dict, cytoolz_dict)

    class wrap:
        """e.g., allow `factory=<class 'dict'>` to instead be `factory=dict` in signature"""
        def __init__(self, obj):
            self.obj = obj

        def __repr__(self):
            return getattr(self.obj, '__name__', repr(self.obj))

    d = merge_with(identity, toolz_dict, cytoolz_dict)
    for key, (toolz_func, cytoolz_func) in d.items():
        if isinstance(toolz_func, FunctionType):
            # function
            toolz_spec = inspect.signature(toolz_func)
        elif isinstance(toolz_func, toolz.curry):
            # curried object
            toolz_spec = inspect.signature(toolz_func.func)
        else:
            # class
            toolz_spec = inspect.signature(toolz_func.__init__)
        toolz_spec = toolz_spec.replace(
            parameters=[
                v.replace(default=wrap(v.default))
                if v.default is not inspect._empty
                else v
                for v in toolz_spec.parameters.values()
            ]
        )
        # Hmm, Cython is showing str as unicode, such as `default=u'__no__default__'`
        doc = cytoolz_func.__doc__
        doc_alt = doc.replace('Py_ssize_t ', '').replace("=u'", "='")
        toolz_sig = toolz_func.__name__ +  str(toolz_spec)
        if not (toolz_sig in doc or toolz_sig in doc_alt):
            message = ('cytoolz.%s does not have correct function signature.'
                       '\n\nExpected: %s'
                       '\n\nDocstring in cytoolz is:\n%s'
                       % (key, toolz_sig, cytoolz_func.__doc__))
            assert False, message


skip_sigs = ['identity']
aliases = {'comp': 'compose'}


@dev_skip_test
def test_sig_at_beginning():
    """ Test that the function signature is at the beginning of the docstring
        and is followed by exactly one blank line.
    """
    cytoolz_dict = valfilter(isfrommod('cytoolz'), cytoolz.__dict__)
    cytoolz_dict = keyfilter(lambda x: x not in skip_sigs, cytoolz_dict)

    for key, val in cytoolz_dict.items():
        doclines = val.__doc__.splitlines()
        assert len(doclines) > 2, (
            'cytoolz.%s docstring too short:\n\n%s' % (key, val.__doc__))

        sig = '%s(' % aliases.get(key, key)
        assert sig in doclines[0], (
            'cytoolz.%s docstring missing signature at beginning:\n\n%s'
            % (key, val.__doc__))

        assert not doclines[1], (
            'cytoolz.%s docstring missing blank line after signature:\n\n%s'
            % (key, val.__doc__))

        assert doclines[2], (
            'cytoolz.%s docstring too many blank lines after signature:\n\n%s'
            % (key, val.__doc__))
