import asyncio
from multiprocessing.util import register_after_fork
from queue import Queue
from threading import (
    Barrier,
    BoundedSemaphore,
    Condition,
    Event,
    Lock,
    RLock,
    Semaphore,
)

from .locks import _ContextManager
from .executor import _ExecutorMixin
from .mp import managers as _managers


AioBaseQueueProxy = _managers.MakeProxyType(
    "AioQueueProxy",
    (
        "task_done",
        "get",
        "qsize",
        "put",
        "put_nowait",
        "get_nowait",
        "empty",
        "join",
        "_qsize",
        "full",
    ),
)


class _AioProxyMixin(_ExecutorMixin):
    _obj = None

    def _async_call(self, method, *args, loop=None, **kwargs):
        return asyncio.ensure_future(
            self.run_in_executor(
                self._callmethod, method, args, kwargs, loop=loop
            )
        )


class ProxyCoroBuilder(type):
    """ Build coroutines to proxy functions. """

    def __new__(cls, clsname, bases, dct):
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

        bases += (_AioProxyMixin,)

        for func in coro_list:
            coro_name = "coro_{}".format(func)
            if coro_name not in existing_coros:
                dct[coro_name] = cls.coro_maker(func)
        return super().__new__(cls, clsname, bases, dct)

    @staticmethod
    def coro_maker(func):
        def coro_func(self, *args, loop=None, **kwargs):
            return self._async_call(func, *args, loop=loop, **kwargs)

        return coro_func


class AioQueueProxy(AioBaseQueueProxy, metaclass=ProxyCoroBuilder):
    """ A Proxy object for AioQueue.

    Provides coroutines for calling 'get' and 'put' on the
    proxy.

    """

    coroutines = ["get", "put"]


class AioAcquirerProxy(_managers.AcquirerProxy, metaclass=ProxyCoroBuilder):
    pool_workers = 1
    coroutines = ["acquire", "release"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._threaded_acquire = False

        def _after_fork(obj):
            obj._threaded_acquire = False

        register_after_fork(self, _after_fork)

    def coro_acquire(self, *args, **kwargs):
        """ Non-blocking acquire.

        We need a custom implementation here, because we need to
        set the _threaded_acquire attribute to True once we have
        the lock. This attribute is used by release() to determine
        whether the lock should be released in the main thread,
        or in the Executor thread.

        """

        def lock_acquired(fut):
            if fut.result():
                self._threaded_acquire = True

        out = self.run_in_executor(self.acquire, *args, **kwargs)
        out.add_done_callback(lock_acquired)
        return out

    def __getstate__(self):
        state = super().__getstate__()
        state["_threaded_acquire"] = False
        return state

    def __setstate__(self, state):
        super().__setstate__(state)

    def release(self):
        """ Release the lock.

        If the lock was acquired in the same process via
        coro_acquire, we need to release the lock in the
        ThreadPoolExecutor's thread.

        """
        if self._threaded_acquire:
            out = self.run_in_thread(super().release)
        else:
            out = super().release()
        self._threaded_acquire = False
        return out

    async def __aenter__(self):
        await self.coro_acquire()
        return None

    async def __aexit__(self, *args, **kwargs):
        self.release()

    def __iter__(self):
        yield from self.coro_acquire()
        return _ContextManager(self)


class AioBarrierProxy(_managers.BarrierProxy, metaclass=ProxyCoroBuilder):
    coroutines = ["wait"]


class AioEventProxy(_managers.EventProxy, metaclass=ProxyCoroBuilder):
    coroutines = ["wait"]


class AioConditionProxy(_managers.ConditionProxy, metaclass=ProxyCoroBuilder):
    coroutines = ["wait", "wait_for"]


class AioSyncManager(_managers.SyncManager):
    """ A mp.Manager that provides asyncio-friendly objects. """

    pass


AioSyncManager.register("AioQueue", Queue, AioQueueProxy)
AioSyncManager.register("AioBarrier", Barrier, AioBarrierProxy)
AioSyncManager.register(
    "AioBoundedSemaphore", BoundedSemaphore, AioAcquirerProxy
)
AioSyncManager.register("AioCondition", Condition, AioConditionProxy)
AioSyncManager.register("AioEvent", Event, AioEventProxy)
AioSyncManager.register("AioLock", Lock, AioAcquirerProxy)
AioSyncManager.register("AioRLock", RLock, AioAcquirerProxy)
AioSyncManager.register("AioSemaphore", Semaphore, AioAcquirerProxy)
