from functools import wraps
from concurrent.futures import ThreadPoolExecutor

from . import util
from .mp import cpu_count


def init_executor(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "_executor"):
            self._executor = self._get_executor()
        return func(self, *args, **kwargs)

    return wrapper


class _ExecutorMixin:
    """ A Mixin that provides asynchronous functionality.

    This mixin provides methods that allow a class to run
    blocking methods via asyncio in a ThreadPoolExecutor.
    It also provides methods that attempt to keep the object
    picklable despite having a non-picklable ThreadPoolExecutor
    as part of its state.

    """

    pool_workers = cpu_count()

    @init_executor
    def run_in_executor(self, callback, *args, loop=None, **kwargs):
        """ Wraps run_in_executor so we can support kwargs.

        BaseEventLoop.run_in_executor does not support kwargs, so
        we wrap our callback in a lambda if kwargs are provided.

        """
        return util.run_in_executor(
            self._executor, callback, *args, loop=loop, **kwargs
        )

    @init_executor
    def run_in_thread(self, callback, *args, **kwargs):
        """ Runs a method in an executor thread.

        This is used when a method must be run in a thread (e.g.
        to that a lock is released in the same thread it was
        acquired), but should be run in a blocking way.

        """
        fut = self._executor.submit(callback, *args, **kwargs)
        return fut.result()

    def _get_executor(self):
        return ThreadPoolExecutor(max_workers=self.pool_workers)

    def __getattr__(self, attr):
        assert attr != "_obj", (
            "Make sure that your Class has a " '"delegate" assigned'
        )
        if (
            self._obj
            and hasattr(self._obj, attr)
            and not attr.startswith("__")
        ):
            return getattr(self._obj, attr)
        raise AttributeError(attr)

    def __getstate__(self):
        self_dict = self.__dict__.copy()
        self_dict["_executor"] = None
        return self_dict

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._executor = self._get_executor()


class CoroBuilder(type):
    """ Metaclass for adding coroutines to a class.

    This metaclass has two main roles:
    1) Make _ExecutorMixin a parent of the given class
    2) For every function name listed in the class attribute "coroutines",
       add a new instance method to the class called "coro_<func_name>",
       which is a coroutine that calls func_name in a ThreadPoolExecutor.

    Each wrapper class that uses this metaclass can define three class
    attributes that will influence the behavior of the metaclass:
    coroutines - A list of methods that should get coroutine versions
                 in the wrapper. For example:
                 coroutines = ['acquire', 'wait']
                 Will mean the class gets coro_acquire and coro_wait methods.
    delegate - The class object that is being wrapped. This object will
               be instantiated when the wrapper class is instantiated, and
               will be set to the `_obj` attribute of the instance.
    pool_workers - The number of workers in the ThreadPoolExecutor internally
                   used by the wrapper class. This defaults to cpu_count(),
                   but for classes that need to acquire locks, it should
                   always be set to 1.

    """

    def __new__(cls, clsname, bases, dct, **kwargs):
        coro_list = dct.get("coroutines", [])
        existing_coros = set()

        def find_existing_coros(d):
            for attr in d:
                if attr.startswith("coro_") or attr.startswith("thread_"):
                    existing_coros.add(attr)

        # Determine if any bases include the coroutines attribute, or
        # if either this class or a base class provides an actual
        # implementation for a coroutine method.
        find_existing_coros(dct)
        for b in bases:
            b_dct = b.__dict__
            coro_list.extend(b_dct.get("coroutines", []))
            find_existing_coros(b_dct)

        # Add _ExecutorMixin to bases.
        if _ExecutorMixin not in bases:
            bases += (_ExecutorMixin,)

        # Add coro funcs to dct, but only if a definition
        # is not already provided by dct or one of our bases.
        for func in coro_list:
            coro_name = "coro_{}".format(func)
            if coro_name not in existing_coros:
                dct[coro_name] = cls.coro_maker(func)

        return super().__new__(cls, clsname, bases, dct)

    def __init__(cls, name, bases, dct):
        """ Properly initialize a coroutine wrapper class.

        Sets pool_workers and delegate on the class, and also
        adds an __init__ method to it that instantiates the
        delegate with the proper context.

        """
        super().__init__(name, bases, dct)
        pool_workers = dct.get("pool_workers")
        delegate = dct.get("delegate")
        old_init = dct.get("__init__")
        # Search bases for values we care about, if we didn't
        # find them on the current class.
        for b in bases:
            b_dct = b.__dict__
            if not pool_workers:
                pool_workers = b_dct.get("pool_workers")
            if not delegate:
                delegate = b_dct.get("delegate")
            if not old_init:
                old_init = b_dct.get("__init__")

        cls.delegate = delegate

        # If we found a value for pool_workers, set it. If not,
        # ExecutorMixin sets a default that will be used.
        if pool_workers:
            cls.pool_workers = pool_workers

        # Here's the __init__ we want every wrapper class to use.
        # It just instantiates the delegate mp object using the
        # correct context.
        @wraps(old_init)
        def init_func(self, *args, **kwargs):
            # Be sure to call the original __init__, if there
            # was one.
            if old_init:
                old_init(self, *args, **kwargs)
            # If we're wrapping a mp object, instantiate it here.
            # If a context was specified, we instaniate the mp class
            # using that context. Otherwise, we'll just use the default
            # context.
            if cls.delegate:
                ctx = kwargs.pop("ctx", None)
                if ctx:
                    clz = getattr(ctx, cls.delegate.__name__)
                else:
                    clz = cls.delegate
                self._obj = clz(*args, **kwargs)

        cls.__init__ = init_func

    @staticmethod
    def coro_maker(func):
        def coro_func(self, *args, loop=None, **kwargs):
            return self.run_in_executor(
                getattr(self, func), *args, loop=loop, **kwargs
            )

        return coro_func
