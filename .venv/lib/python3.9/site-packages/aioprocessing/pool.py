from asyncio import Future
import asyncio

from .executor import CoroBuilder
from .mp import Pool

__all__ = ["AioPool"]


class AioPool(metaclass=CoroBuilder):
    delegate = Pool
    coroutines = ["join"]

    def _coro_func(self, funcname, *args, loop=None, **kwargs):
        """ Call the given function, and wrap the reuslt in a Future.

        funcname should be the name of a function which takes `callback`
        and `error_callback` keyword arguments (e.g. apply_async).

        """
        if not loop:
            loop = asyncio.get_event_loop()
        fut = Future()

        def set_result(result):
            loop.call_soon_threadsafe(fut.set_result, result)

        def set_exc(exc):
            loop.call_soon_threadsafe(fut.set_exception, exc)

        func = getattr(self._obj, funcname)
        func(*args, callback=set_result, error_callback=set_exc, **kwargs)
        return fut

    def coro_apply(self, func, args=(), kwds=None, *, loop=None):
        if kwds is None:
            kwds = {}
        return self._coro_func(
            "apply_async", func, args=args, kwds=kwds, loop=loop
        )

    def coro_map(self, func, iterable, chunksize=None, *, loop=None):
        return self._coro_func(
            "map_async", func, iterable, chunksize=chunksize, loop=loop
        )

    def coro_starmap(self, func, iterable, chunksize=None, *, loop=None):
        return self._coro_func(
            "starmap_async", func, iterable, chunksize=chunksize, loop=loop
        )

    def __enter__(self):
        self._obj.__enter__()
        return self

    def __exit__(self, *args, **kwargs):
        self._obj.__exit__(*args, **kwargs)
