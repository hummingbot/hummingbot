"""Use pika with the Gevent IOLoop."""

import functools
import logging
import os
import threading
import weakref

try:
    import queue
except ImportError:  # Python <= v2.7
    import Queue as queue

import gevent
import gevent.hub
import gevent.socket

import pika.compat
from pika.adapters.base_connection import BaseConnection
from pika.adapters.utils.io_services_utils import check_callback_arg
from pika.adapters.utils.nbio_interface import (
    AbstractIOReference,
    AbstractIOServices,
)
from pika.adapters.utils.selector_ioloop_adapter import (
    AbstractSelectorIOLoop,
    SelectorIOServicesAdapter,
)

LOGGER = logging.getLogger(__name__)


class GeventConnection(BaseConnection):
    """Implementation of pika's ``BaseConnection``.

    An async selector-based connection which integrates with Gevent.
    """

    def __init__(self,
                 parameters=None,
                 on_open_callback=None,
                 on_open_error_callback=None,
                 on_close_callback=None,
                 custom_ioloop=None,
                 internal_connection_workflow=True):
        """Create a new GeventConnection instance and connect to RabbitMQ on
        Gevent's event-loop.

        :param pika.connection.Parameters|None parameters: The connection
            parameters
        :param callable|None on_open_callback: The method to call when the
            connection is open
        :param callable|None on_open_error_callback: Called if the connection
            can't be established or connection establishment is interrupted by
            `Connection.close()`:
            on_open_error_callback(Connection, exception)
        :param callable|None on_close_callback: Called when a previously fully
            open connection is closed:
            `on_close_callback(Connection, exception)`, where `exception` is
            either an instance of `exceptions.ConnectionClosed` if closed by
            user or broker or exception of another type that describes the
            cause of connection failure
        :param gevent._interfaces.ILoop|nbio_interface.AbstractIOServices|None
            custom_ioloop: Use a custom Gevent ILoop.
        :param bool internal_connection_workflow: True for autonomous connection
            establishment which is default; False for externally-managed
            connection workflow via the `create_connection()` factory
        """
        if pika.compat.ON_WINDOWS:
            raise RuntimeError('GeventConnection is not supported on Windows.')

        custom_ioloop = (custom_ioloop or
                         _GeventSelectorIOLoop(gevent.get_hub()))

        if isinstance(custom_ioloop, AbstractIOServices):
            nbio = custom_ioloop
        else:
            nbio = _GeventSelectorIOServicesAdapter(custom_ioloop)

        super(GeventConnection, self).__init__(
            parameters,
            on_open_callback,
            on_open_error_callback,
            on_close_callback,
            nbio,
            internal_connection_workflow=internal_connection_workflow)

    @classmethod
    def create_connection(cls,
                          connection_configs,
                          on_done,
                          custom_ioloop=None,
                          workflow=None):
        """Implement
        :py:classmethod::`pika.adapters.BaseConnection.create_connection()`.
        """
        custom_ioloop = (custom_ioloop or
                         _GeventSelectorIOLoop(gevent.get_hub()))

        nbio = _GeventSelectorIOServicesAdapter(custom_ioloop)

        def connection_factory(params):
            """Connection factory."""
            if params is None:
                raise ValueError('Expected pika.connection.Parameters '
                                 'instance, but got None in params arg.')
            return cls(parameters=params,
                       custom_ioloop=nbio,
                       internal_connection_workflow=False)

        return cls._start_connection_workflow(
            connection_configs=connection_configs,
            connection_factory=connection_factory,
            nbio=nbio,
            workflow=workflow,
            on_done=on_done)


class _TSafeCallbackQueue(object):
    """Dispatch callbacks from any thread to be executed in the main thread
    efficiently with IO events.
    """

    def __init__(self):
        """
        :param _GeventSelectorIOLoop loop: IO loop to add callbacks to.
        """
        # Thread-safe, blocking queue.
        self._queue = queue.Queue()
        # PIPE to trigger an event when the queue is ready.
        self._read_fd, self._write_fd = os.pipe()
        # Lock around writes to the PIPE in case some platform/implementation
        # requires this.
        self._write_lock = threading.RLock()

    @property
    def fd(self):
        """The file-descriptor to register for READ events in the IO loop."""
        return self._read_fd

    def add_callback_threadsafe(self, callback):
        """Add an item to the queue from any thread. The configured handler
        will be invoked with the item in the main thread.

        :param item: Object to add to the queue.
        """
        self._queue.put(callback)
        with self._write_lock:
            # The value written is not important.
            os.write(self._write_fd, b'\xFF')

    def run_next_callback(self):
        """Invoke the next callback from the queue.

        MUST run in the main thread. If no callback was added to the queue,
        this will block the IO loop.

        Performs a blocking READ on the pipe so must only be called when the
        pipe is ready for reading.
        """
        try:
            callback = self._queue.get_nowait()
        except queue.Empty:
            # Should never happen.
            LOGGER.warning("Callback queue was empty.")
        else:
            # Read the byte from the pipe so the event doesn't re-fire.
            os.read(self._read_fd, 1)
            callback()


class _GeventSelectorIOLoop(AbstractSelectorIOLoop):
    """Implementation of `AbstractSelectorIOLoop` using the Gevent event loop.

    Required by implementations of `SelectorIOServicesAdapter`.
    """
    # Gevent's READ and WRITE masks are defined as 1 and 2 respectively. No
    # ERROR mask is defined.
    # See http://www.gevent.org/api/gevent.hub.html#gevent._interfaces.ILoop.io
    READ = 1
    WRITE = 2
    ERROR = 0

    def __init__(self, gevent_hub=None):
        """
        :param gevent._interfaces.ILoop gevent_loop:
        """
        self._hub = gevent_hub or gevent.get_hub()
        self._io_watchers_by_fd = {}
        # Used to start/stop the loop.
        self._waiter = gevent.hub.Waiter()

        # For adding callbacks from other threads. See `add_callback(..)`.
        self._callback_queue = _TSafeCallbackQueue()

        def run_callback_in_main_thread(fd, events):
            """Swallow the fd and events arguments."""
            del fd
            del events
            self._callback_queue.run_next_callback()

        self.add_handler(self._callback_queue.fd, run_callback_in_main_thread,
                         self.READ)

    def close(self):
        """Release the loop's resources."""
        self._hub.loop.destroy()
        self._hub = None

    def start(self):
        """Run the I/O loop. It will loop until requested to exit. See `stop()`.
        """
        LOGGER.debug("Passing control to Gevent's IOLoop")
        self._waiter.get()  # Block until 'stop()' is called.

        LOGGER.debug("Control was passed back from Gevent's IOLoop")
        self._waiter.clear()

    def stop(self):
        """Request exit from the ioloop. The loop is NOT guaranteed to
        stop before this method returns.

        To invoke `stop()` safely from a thread other than this IOLoop's thread,
        call it via `add_callback_threadsafe`; e.g.,

            `ioloop.add_callback(ioloop.stop)`
        """
        self._waiter.switch(None)

    def add_callback(self, callback):
        """Requests a call to the given function as soon as possible in the
        context of this IOLoop's thread.

        NOTE: This is the only thread-safe method in IOLoop. All other
        manipulations of IOLoop must be performed from the IOLoop's thread.

        For example, a thread may request a call to the `stop` method of an
        ioloop that is running in a different thread via
        `ioloop.add_callback_threadsafe(ioloop.stop)`

        :param callable callback: The callback method
        """
        if gevent.get_hub() == self._hub:
            # We're in the main thread; just add the callback.
            LOGGER.debug("Adding callback from main thread")
            self._hub.loop.run_callback(callback)
        else:
            # This isn't the main thread and Gevent's hub/loop don't provide
            # any thread-safety so enqueue the callback for it to be registered
            # in the main thread.
            LOGGER.debug("Adding callback from another thread")
            callback = functools.partial(self._hub.loop.run_callback, callback)
            self._callback_queue.add_callback_threadsafe(callback)

    def call_later(self, delay, callback):
        """Add the callback to the IOLoop timer to be called after delay seconds
        from the time of call on best-effort basis. Returns a handle to the
        timeout.

        :param float delay: The number of seconds to wait to call callback
        :param callable callback: The callback method
        :returns: handle to the created timeout that may be passed to
            `remove_timeout()`
        :rtype: object
        """
        timer = self._hub.loop.timer(delay)
        timer.start(callback)
        return timer

    def remove_timeout(self, timeout_handle):
        """Remove a timeout

        :param timeout_handle: Handle of timeout to remove
        """
        timeout_handle.close()

    def add_handler(self, fd, handler, events):
        """Start watching the given file descriptor for events

        :param int fd: The file descriptor
        :param callable handler: When requested event(s) occur,
            `handler(fd, events)` will be called.
        :param int events: The event mask (READ|WRITE)
        """
        io_watcher = self._hub.loop.io(fd, events)
        self._io_watchers_by_fd[fd] = io_watcher
        io_watcher.start(handler, fd, events)

    def update_handler(self, fd, events):
        """Change the events being watched for.

        :param int fd: The file descriptor
        :param int events: The new event mask (READ|WRITE)
        """
        io_watcher = self._io_watchers_by_fd[fd]
        # Save callback from the original watcher. The close the old watcher
        # and create a new one using the saved callback and the new events.
        callback = io_watcher.callback
        io_watcher.close()
        del self._io_watchers_by_fd[fd]
        self.add_handler(fd, callback, events)

    def remove_handler(self, fd):
        """Stop watching the given file descriptor for events

        :param int fd: The file descriptor
        """
        io_watcher = self._io_watchers_by_fd[fd]
        io_watcher.close()
        del self._io_watchers_by_fd[fd]


class _GeventSelectorIOServicesAdapter(SelectorIOServicesAdapter):
    """SelectorIOServicesAdapter implementation using Gevent's DNS resolver."""

    def getaddrinfo(self,
                    host,
                    port,
                    on_done,
                    family=0,
                    socktype=0,
                    proto=0,
                    flags=0):
        """Implement :py:meth:`.nbio_interface.AbstractIOServices.getaddrinfo()`.
        """
        resolver = _GeventAddressResolver(native_loop=self._loop,
                                          host=host,
                                          port=port,
                                          family=family,
                                          socktype=socktype,
                                          proto=proto,
                                          flags=flags,
                                          on_done=on_done)
        resolver.start()
        # Return needs an implementation of `AbstractIOReference`.
        return _GeventIOLoopIOHandle(resolver)


class _GeventIOLoopIOHandle(AbstractIOReference):
    """Implement `AbstractIOReference`.

    Only used to wrap the _GeventAddressResolver.
    """

    def __init__(self, subject):
        """
        :param subject: subject of the reference containing a `cancel()` method
        """
        self._cancel = subject.cancel

    def cancel(self):
        """Cancel pending operation

        :returns: False if was already done or cancelled; True otherwise
        :rtype: bool
        """
        return self._cancel()


class _GeventAddressResolver(object):
    """Performs getaddrinfo asynchronously Gevent's configured resolver in a
    separate greenlet and invoking the provided callback with the result.

    See: http://www.gevent.org/dns.html
    """
    __slots__ = (
        '_loop',
        '_on_done',
        '_greenlet',
        # getaddrinfo(..) args:
        '_ga_host',
        '_ga_port',
        '_ga_family',
        '_ga_socktype',
        '_ga_proto',
        '_ga_flags')

    def __init__(self, native_loop, host, port, family, socktype, proto, flags,
                 on_done):
        """Initialize the `_GeventAddressResolver`.

        :param AbstractSelectorIOLoop native_loop:
        :param host: `see socket.getaddrinfo()`
        :param port: `see socket.getaddrinfo()`
        :param family: `see socket.getaddrinfo()`
        :param socktype: `see socket.getaddrinfo()`
        :param proto: `see socket.getaddrinfo()`
        :param flags: `see socket.getaddrinfo()`
        :param on_done: on_done(records|BaseException) callback for reporting
            result from the given I/O loop. The single arg will be either an
            exception object (check for `BaseException`) in case of failure or
            the result returned by `socket.getaddrinfo()`.
        """
        check_callback_arg(on_done, 'on_done')

        self._loop = native_loop
        self._on_done = on_done
        # Reference to the greenlet performing `getaddrinfo`.
        self._greenlet = None
        # getaddrinfo(..) args.
        self._ga_host = host
        self._ga_port = port
        self._ga_family = family
        self._ga_socktype = socktype
        self._ga_proto = proto
        self._ga_flags = flags

    def start(self):
        """Start an asynchronous getaddrinfo invocation."""
        if self._greenlet is None:
            self._greenlet = gevent.spawn_raw(self._resolve)
        else:
            LOGGER.warning("_GeventAddressResolver already started")

    def cancel(self):
        """Cancel the pending resolver."""
        changed = False

        if self._greenlet is not None:
            changed = True
            self._stop_greenlet()

        self._cleanup()
        return changed

    def _cleanup(self):
        """Stop the resolver and release any resources."""
        self._stop_greenlet()
        self._loop = None
        self._on_done = None

    def _stop_greenlet(self):
        """Stop the greenlet performing getaddrinfo if running.

        Otherwise, this is a no-op.
        """
        if self._greenlet is not None:
            gevent.kill(self._greenlet)
            self._greenlet = None

    def _resolve(self):
        """Call `getaddrinfo()` and return result via user's callback
        function on the configured IO loop.
        """
        try:
            # NOTE(JG): Can't use kwargs with getaddrinfo on Python <= v2.7.
            result = gevent.socket.getaddrinfo(self._ga_host, self._ga_port,
                                               self._ga_family,
                                               self._ga_socktype,
                                               self._ga_proto, self._ga_flags)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error('Address resolution failed: %r', exc)
            result = exc

        callback = functools.partial(self._dispatch_callback, result)
        self._loop.add_callback(callback)

    def _dispatch_callback(self, result):
        """Invoke the configured completion callback and any subsequent cleanup.

        :param result: result from getaddrinfo, or the exception if raised.
        """
        try:
            LOGGER.debug(
                'Invoking async getaddrinfo() completion callback; host=%r',
                self._ga_host)
            self._on_done(result)
        finally:
            self._cleanup()
