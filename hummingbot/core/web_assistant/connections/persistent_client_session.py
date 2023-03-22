import asyncio
import gc
import sys
import threading
import weakref
from asyncio import AbstractEventLoop
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Coroutine, Protocol

from aiohttp import ClientSession

from hummingbot.core.utils.weak_singleton_metaclass import ClassNotYetInstantiatedError, WeakSingletonMetaclass


class NotWithinAsyncFrameworkError(Exception):
    pass


class PCSAction(Protocol):
    def __init__(self, action: "PCSAction"):
        self.action = action

    def __str__(self):
        return self.action

    def __cmp__(self, other):
        return self.action is other.action

    # Necessary when __cmp__ or __eq__ is defined
    # in order to make this class usable as a
    # dictionary key:
    def __hash__(self):
        return hash(self.action)


@dataclass(frozen=True)
class PCSState(Protocol):
    object: "PersistentClientSession"
    index: int

    def verify(self):
        ...

    def next(self, action: PCSAction):
        ...


@dataclass(frozen=True)
class PCSStateInitialized:
    object: "PersistentClientSession"
    index: int

    def verify(self):
        assert self.object._ref_count[self.index] == 0
        assert self.object._init_count[self.index] == 0
        assert self.object._in_context_count[self.index] == 0

    def next(self, action: PCSAction):
        ...


@dataclass(frozen=True)
class PCSStateInstantiated:
    object: "PersistentClientSession"
    index: int

    def verify(self):
        assert self.object._ref_count[self.index] == 0
        assert self.object._init_count[self.index] == 0
        assert self.object._in_context_count[self.index] == 0

    def next(self, action: PCSAction):
        ...


class PCSStateLiveSession(PCSState):
    def verify(self):
        pass


class PCSStateMachine:
    def __init__(self, state: PCSState):
        self.state: PCSState = state
        self.state.verify()


class PersistentClientSession(metaclass=WeakSingletonMetaclass):
    """ A persistent class to manage aiohttp client sessions.

    The class uses a shared client object to manage aiohttp client sessions,
    with a reference count to keeps track of the number of active sessions.
    The shared client is automatically cleaned up when the reference count reaches 0.
    """
    # __slots__ here is overkill, but a nice way to make sure we don't add any new attributes
    # similar behavior could be achieved with class definitions, since this is a singleton
    __slots__ = (
        '_sessions_mutex',
        '_client_sessions',
        '_running_event_loops',
        '_finalizers',
        '_kwargs_client_sessions',
        '_original_sessions_close',
        '_ref_count',
        '_internal_state',
        # This is a special attribute that is needed by the WeakSingletonMetaclass
        '__weakref__',
    )

    def __del__(self):
        print(f"Deleting instance {self} of class {getattr(self, '__class__').__name__}")
        print(f"   refs: {gc.get_referrers(self)}")
        thread_id = threading.get_ident()
        print(sys.getrefcount(self._client_sessions[thread_id]) - 1)
        if self.has_live_session(thread_id=thread_id):
            # The session was not closed cleanly by the user (or the context manager)
            # This is not a good practice, but we can try to close the session from another loop
            # if the current loop is already closed (which is the case when the class is deleted)
            print(f"      - calling _cleanup_in_thread {thread_id}")
            self._cleanup_in_thread(thread_id=thread_id)

    def __init__(self, **kwargs):
        print("__init__", kwargs)
        # Initializing with whichever thread is initializing first
        thread_id: int = threading.get_ident()

        # __slots__ circumvent __setattr__ and __getattr__ so we need to use setattr and getattr
        setattr(self, "_finalizers", {thread_id: list()})

        setattr(self, "_sessions_mutex", {thread_id: asyncio.Lock()})
        setattr(self, "_running_event_loops", {thread_id: None})
        setattr(self, "_client_sessions", {thread_id: None})
        setattr(self, "_kwargs_client_sessions", {thread_id: kwargs})
        setattr(self, "_original_sessions_close", {thread_id: None})
        setattr(self, "_ref_count", {thread_id: 0})

    def __call__(self, **kwargs) -> ClientSession:
        """Noncontextual instantiation of the ClientSession instance.

        :param kwargs: Keyword arguments for the ClientSession constructor.
        :return: The ClientSession instance associated with the current thread.
        :rtype: Coroutine[Any, Any, ClientSession]
        """
        print("__call__")
        thread_id: int = threading.get_ident()

        # Record the event loop for the current thread (It should already be running, otherwise it raises)
        self._running_event_loops[thread_id]: AbstractEventLoop = self._get_running_loop_or_raise()

        self._kwargs_client_sessions[thread_id] = kwargs

        # Create a session if one is not in the process of being created on the event loop
        self._run_in_thread(call=self._get_or_create_session(thread_id=thread_id, should_be_locked=False))
        assert getattr(self._client_sessions[thread_id], "_loop") is self._running_event_loops[thread_id]

        self._ref_count[thread_id] = self._count_refs(thread_id=thread_id)
        return weakref.proxy(self._client_sessions[thread_id])

    async def create_session(self, *, thread_id: int):
        """
        Create a new session for the given thread id.

        :param int thread_id: The identifier for the thread to create a session for.
        """
        # If the session is already created (by another async call) and not closed, we can return
        if self.has_live_session(thread_id=thread_id):
            await asyncio.sleep(0)
            return

        self._cleanup_closed_session(thread_id=thread_id)

        # Otherwise, we need to create the session
        async with self._sessions_mutex[thread_id]:
            await self._get_or_create_session(thread_id=thread_id, should_be_locked=True)
            await asyncio.sleep(0)

        assert self._client_sessions[thread_id] is not None
        assert not self._client_sessions[thread_id].closed

    def _count_refs(self, *, thread_id: int) -> int:
        """Count the number of references to the session."""
        return sys.getrefcount(self._client_sessions[thread_id]) - 1

    async def _session_close(self, thread_id: int):
        """Wraps the original close() method of the ClientSession to clean this instance"""
        if self._original_sessions_close[thread_id] and self._original_sessions_close[thread_id]() is not None:
            await self._original_sessions_close[thread_id]()()
        self._cleanup_closed_session(thread_id=thread_id)

    async def _get_or_create_session(self, *, thread_id: int, should_be_locked: bool = True):
        """
        Create a new session if needed for the given thread id.

        :param int thread_id: The identifier for the thread to create a session for.
        :param bool should_be_locked: Whether the session mutex should be locked.
        :raises RuntimeError: Collision between sync and async calls.
        """
        if self.has_live_session(thread_id=thread_id):
            return

        # Bitwise AND to check if the lock is locked when it should be
        # For instance, in the case of a sync call, the lock should not be locked:
        # meaning, no async call in the process of creating a session
        if should_be_locked == self._sessions_mutex[thread_id].locked():
            try:
                if "loop" not in self._kwargs_client_sessions[thread_id]:
                    self._kwargs_client_sessions[thread_id]["loop"] = self._running_event_loops[thread_id]
                self._client_sessions[thread_id] = ClientSession(**self._kwargs_client_sessions[thread_id])

                self._finalizers[thread_id].append(
                    weakref.finalize(self._client_sessions[thread_id],
                                     self._cleanup_in_thread,
                                     thread_id=thread_id))

                # Monitoring the session's close outside the PersistentClientSession
                self._original_sessions_close[thread_id] = weakref.WeakMethod(
                    self._client_sessions[thread_id].close)
                self._client_sessions[thread_id].close = partial(self._session_close, thread_id=thread_id)

                self._ref_count[thread_id] = self._count_refs(thread_id=thread_id)
            except RuntimeError as e:
                # The session failed to be created
                self._cleanup_closed_session(thread_id=thread_id)
                raise e
        elif not should_be_locked:
            raise RuntimeError("The session is already being created in async context."
                               "This is not allowed in sync context and a design flaw")
        await asyncio.sleep(0)

    async def open(self, **kwargs) -> ClientSession:
        """Request out-of-context access to the shared client."""
        thread_id: int = threading.get_ident()

        # Update the kwargs if they are different
        if kwargs and kwargs != self._kwargs_client_sessions[thread_id]:
            self._kwargs_client_sessions[thread_id] = kwargs

        # Create a session if one is not in the process of being created on the event loop
        await self.create_session(thread_id=thread_id)

        # Refresh the reference count
        self._ref_count[thread_id] = self._count_refs(thread_id=thread_id)
        return self._client_sessions[thread_id]

    async def close(self):
        """Close the shared client session."""
        await self.async_session_cleanup(thread_id=threading.get_ident())

    async def __aenter__(self) -> ClientSession:
        """
        Context manager entry method. There are a few cases to consider for __aexit__:
            1. We enter context with a reference to the singleton instance
                The instance already exists, it should have a live session, the init_count >= 1
                If there is a 'as' clause, the reference count increases after __aenter__():
                    We can skip closing the session
                If there is no 'as' clause, the reference count remains the same:
                    How to know that we should not close the session?
            2. We enter context with a call without 'as'
                The instance already exist, and it should have a live session
            3. We enter context with a call and assign it with 'as'

        :return: The ClientSession instance associated with the current thread.
        :rtype: Coroutine[Any, Any, ClientSession]
        """
        print("__aenter__")
        return await self.open()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit method. There are a few cases to consider for __aexit__:
            1. We enter context with a reference to the singleton instance
                If there is a 'as' clause, the reference count increases after __aenter__():
                    We can skip closing the session on references_offset >= 1
                If there is no 'as' clause, the reference count remains the same:
                    How to know that we should not close the session?
            2. We enter context with a call without 'as'
                The instance already exist, and it should have a live session
            3. We enter context with a call and assign it with 'as'

        Decrements the reference count for the current thread, and cleans up the
        shared client if the reference count reaches 0.

        :param exc_type: Type of exception raised.
        :param exc_val: Value of exception raised.
        :param exc_tb: Traceback of exception raised.
        """
        print("__aexit__")
        thread_id: int = threading.get_ident()

        references_offset = self._count_refs(thread_id=thread_id) - self._ref_count[thread_id]

        # Are there any other references?
        print(f"  ref offset: {references_offset}")

        # If the ref count is 0 and there are no extra references, we can safely close the session
        if references_offset >= 1:
            # ref_count is zero, but an out-of-context reference exists,
            # so we can't clean up yet, let's leave that task to the finalizer
            print(f"Deferring cleanup for thread {thread_id} to the class collector."
                  f"The async context manager was either returned or the PersistentClientSession"
                  f" instantiated outside its context.")
        else:
            await self.async_session_cleanup(thread_id=thread_id)
        await asyncio.sleep(0)

    def __getattr__(self, attr):
        """
        Wraps all other method calls to the underlying `aiohttp.ClientSession` instance.

        :param attr: The name of the method to call.

        Example:
        --------
        persistent_session = PersistentClientSession(session)
        response = await persistent_session.get('https://www.example.com')
        """
        thread_id: int = threading.get_ident()
        print(f"__getattr__({attr})")
        if hasattr(self._client_sessions[thread_id], attr):
            return getattr(self._client_sessions[thread_id], attr)
        else:
            raise AttributeError(f"'{self.__class__.__name__}',"
                                 f" nor '{self._client_sessions[thread_id].__class__.__name__}'"
                                 f" object has attribute '{attr}'")

    @staticmethod
    def _get_running_loop_or_raise() -> AbstractEventLoop:
        """
        Raises an error if the current thread is not running an asyncio event loop.

        :raises NoRunningLoopError: If the current thread is not running an asyncio event loop.
        :return: True if the current thread is running an asyncio event loop.
        :rtype: bool
        """
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            raise NotWithinAsyncFrameworkError("The event loop is not running."
                                               "This method requires a running event loop")

    def _is_instantiated_or_raise(self) -> bool:
        """
        Raises an error if the class has not been instantiated yet.

        :raises ClassNotYetInstantiatedError: If the class has not been instantiated yet.
        :return: True if the class has been instantiated.
        :rtype: bool
        """
        if not self.__class__.is_instantiated():
            raise ClassNotYetInstantiatedError("Class not created yet."
                                               f"The methods of `{self.__class__.__name__}'"
                                               " can only be called after this 'Singleton'"
                                               " class has been instantiated at least once.")
        return True

    def has_session(self, *, thread_id: int) -> bool:
        """
        Returns True if the thread has a session. The session may be closed.
        :param thread_id:
        :return: True if the thread has a session.
        :rtype: bool
        """
        return thread_id in self._client_sessions and self._client_sessions[thread_id] is not None

    def has_live_session(self, *, thread_id: int) -> bool:
        """Checks if the thread has a live session"""
        return self.has_session(thread_id=thread_id) and not self._client_sessions[thread_id].closed

    async def async_session_cleanup(self, *, thread_id: int, call: Callable[[], Coroutine[Any, Any, None]] = None):
        """
        Closes the ClientSession for the thread, and cleans up the thread resources.
        :param thread_id:
        :return: None
        """
        print(f"Closing session for thread {thread_id}")
        if self.has_live_session(thread_id=thread_id):
            # Just making sure another call is not already in progress
            async with self._sessions_mutex[thread_id]:
                if self.has_live_session(thread_id=thread_id):
                    if call is not None:
                        await call()
                    else:
                        await self._client_sessions[thread_id].close()
        self._cleanup_closed_session(thread_id=thread_id)

    def _cleanup_closed_session(self, *, thread_id: int):
        """
        Cleans up the thread resources if the session is closed, does nothing otherwise.
        :param thread_id:
        :return: None
        """
        # If the session is closed, we can safely clear it, otherwise silently ignore
        self._client_sessions[thread_id] = None
        self._original_sessions_close[thread_id] = None
        self._kwargs_client_sessions[thread_id] = {}

    def _run_in_thread(self, *, call: Coroutine[Any, Any, None] = None):
        """
        Closes the ClientSession for the thread, and cleans up the thread resources. This uses a new event loop
        in a different thread to run the async cleanup.
        :return: None
        """
        # Create a new event loop in a different thread and run the call there
        # A call to asyncio.run() is not possible here because the loop is already/still running
        loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        loop.set_debug(True)
        thread: threading.Thread = threading.Thread(target=loop.run_forever, daemon=False)
        thread.start()

        result = None
        if call:
            result = asyncio.run_coroutine_threadsafe(call, loop=loop).result()

        loop.call_soon_threadsafe(loop.stop)
        thread.join()
        return result

    def _cleanup_in_thread(self, *, thread_id: int, call: Callable[[], Coroutine[Any, Any, None]] = None):
        """
        Closes the ClientSession for the thread, and cleans up the thread resources. This uses a new event loop
        in a different thread to run the async cleanup.
        :param thread_id:
        :return: None
        """
        # Create a new event loop in a different thread and run the cleanup
        # A call to asyncio.run() is not possible here because the loop is already/still running
        loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        loop.set_debug(True)
        thread: threading.Thread = threading.Thread(target=loop.run_forever, daemon=False)
        thread.start()
        if call:
            asyncio.run_coroutine_threadsafe(call(), loop=loop).result()
            asyncio.run_coroutine_threadsafe(self.async_session_cleanup(thread_id=thread_id, call=call),
                                             loop=loop).result()
        else:
            asyncio.run_coroutine_threadsafe(self.async_session_cleanup(thread_id=thread_id), loop=loop).result()
        loop.call_soon_threadsafe(loop.stop)
        thread.join()
