from .executor import CoroBuilder
from .mp import Queue, SimpleQueue, JoinableQueue


class AioBaseQueue(metaclass=CoroBuilder):
    coroutines = ["get", "put"]


class AioSimpleQueue(AioBaseQueue):
    """ An asyncio-friendly version of mp.SimpleQueue.

    Provides two coroutines: coro_get and coro_put,
    which are asynchronous version of get and put, respectively.

    """

    delegate = SimpleQueue


class AioQueue(AioBaseQueue):
    """ An asyncio-friendly version of mp.SimpleQueue.

    Provides two coroutines: coro_get and coro_put,
    which are asynchronous version of get and put, respectively.

    """

    delegate = Queue


class AioJoinableQueue(AioBaseQueue):
    """ An asyncio-friendly version of mp.JoinableQueue.

    Provides three coroutines: coro_get, coro_put, and
    coro_join, which are asynchronous version of get put, and
    join, respectively.

    """

    coroutines = ["join"]
    delegate = JoinableQueue
