from . import mp as multiprocessing  # noqa
from .connection import *  # noqa
from .managers import *  # noqa

__all__ = [
    "AioProcess",
    "AioManager",
    "AioPipe",
    "AioQueue",
    "AioSimpleQueue",
    "AioJoinableQueue",
    "AioLock",
    "AioRLock",
    "AioCondition",
    "AioPool",
    "AioSemaphore",
    "AioBoundedSemaphore",
    "AioEvent",
    "AioBarrier",
]

# version is a human-readable version number.

# version_info is a four-tuple for programmatic comparison. The first
# three numbers are the components of the version number.  The fourth
# is zero for an official release, positive for a development branch,
# or negative for a release candidate or beta (after the base version
# number has been incremented)
version = "2.0.1"
version_info = (2, 0, 1, 0)
__version__=version

if hasattr(multiprocessing, "get_context"):

    def _get_context():
        return multiprocessing.get_context()

    has_context = True
else:

    def _get_context():
        return None

    has_context = False


def AioProcess(
    group=None,
    target=None,
    name=None,
    args=(),
    kwargs=None,
    *,
    daemon=None,
    context=None
):
    """ Returns an asyncio-friendly version of multiprocessing.Process.

    Provides the following coroutines:
    coro_join()

    """
    if kwargs is None:
        kwargs = {}
    context = context if context else _get_context()
    from .process import AioProcess

    return AioProcess(
        group=group,
        target=target,
        name=name,
        args=args,
        kwargs=kwargs,
        daemon=daemon,
        ctx=context,
    )


def AioPool(
    processes=None,
    initializer=None,
    initargs=(),
    maxtasksperchild=None,
    *,
    context=None
):
    """ Returns an asyncio-friendly version of multiprocessing.Pool.

    Provides the following coroutines:
    coro_join()
    coro_apply()
    coro_map()
    coro_starmap()

    """
    context = context if context else _get_context()
    from .pool import AioPool

    return AioPool(
        processes=processes,
        initializer=initializer,
        initargs=initargs,
        maxtasksperchild=maxtasksperchild,
        ctx=context,
    )


def AioManager(*, context=None):
    """ Starts and returns an asyncio-friendly mp.SyncManager.

    Provides the follow asyncio-friendly objects:

    AioQueue
    AioBarrier
    AioBoundedSemaphore
    AioCondition
    AioEvent
    AioLock
    AioRLock
    AioSemaphore

    """
    context = context if context else _get_context()
    from .managers import AioSyncManager

    # For Python 3.3 support, don't always pass ctx.
    kwargs = {"ctx": context} if has_context else {}
    m = AioSyncManager(**kwargs)
    m.start()
    return m


def AioPipe(duplex=True):
    """ Returns a pair of AioConnection objects. """
    from .connection import AioConnection

    conn1, conn2 = multiprocessing.Pipe(duplex=duplex)
    # Transform the returned connection instances into
    # instance of AioConnection.
    conn1 = AioConnection(conn1)
    conn2 = AioConnection(conn2)
    return conn1, conn2


# queues


def AioQueue(maxsize=0, *, context=None):
    """ Returns an asyncio-friendly version of a multiprocessing.Queue

    Returns an AioQueue objects with the given context. If a context
    is not provided, the default for the platform will be used.

    """
    context = context = context if context else _get_context()
    from .queues import AioQueue

    return AioQueue(maxsize, ctx=context)


def AioJoinableQueue(maxsize=0, *, context=None):
    """ Returns an asyncio-friendly version of a multiprocessing.JoinableQueue

    Returns an AioJoinableQueue object with the given context. If a context
    is not provided, the default for the platform will be used.

    """
    context = context = context if context else _get_context()
    from .queues import AioJoinableQueue

    return AioJoinableQueue(maxsize, ctx=context)


def AioSimpleQueue(*, context=None):
    """ Returns an asyncio-friendly version of a multiprocessing.SimpleQueue

    Returns an AioSimpleQueue object with the given context. If a context
    is not provided, the default for the platform will be used.

    """
    context = context = context if context else _get_context()
    from .queues import AioSimpleQueue

    return AioSimpleQueue(ctx=context)


# locks


def AioLock(*, context=None):
    """ Returns a non-recursive lock object. """
    context = context = context if context else _get_context()
    from .locks import AioLock

    return AioLock(ctx=context)


def AioRLock(*, context=None):
    """ Returns a recursive lock object. """
    context = context = context if context else _get_context()
    from .locks import AioRLock

    return AioRLock(ctx=context)


def AioCondition(lock=None, *, context=None):
    """ Returns a condition object. """
    context = context = context if context else _get_context()
    from .locks import AioCondition

    return AioCondition(lock, ctx=context)


def AioSemaphore(value=1, *, context=None):
    """ Returns a semaphore object. """
    context = context = context if context else _get_context()
    from .locks import AioSemaphore

    return AioSemaphore(value, ctx=context)


def AioBoundedSemaphore(value=1, *, context=None):
    """ Returns a bounded semaphore object. """
    context = context = context if context else _get_context()
    from .locks import AioBoundedSemaphore

    return AioBoundedSemaphore(value, ctx=context)


def AioEvent(*, context=None):
    """ Returns an event object. """
    context = context = context if context else _get_context()
    from .locks import AioEvent

    return AioEvent(ctx=context)


def AioBarrier(parties, action=None, timeout=None, *, context=None):
    """ Returns a barrier object. """
    context = context = context if context else _get_context()
    from .locks import AioBarrier

    return AioBarrier(parties, action, timeout, ctx=context)
