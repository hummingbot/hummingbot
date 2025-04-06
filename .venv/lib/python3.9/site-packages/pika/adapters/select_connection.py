"""A connection adapter that tries to use the best polling method for the
platform pika is running on.

"""
import abc
import collections
import errno
import heapq
import logging
import select
import time
import threading

import pika.compat

from pika.adapters.utils import nbio_interface
from pika.adapters.base_connection import BaseConnection
from pika.adapters.utils.selector_ioloop_adapter import (
    SelectorIOServicesAdapter, AbstractSelectorIOLoop)

LOGGER = logging.getLogger(__name__)

# One of select, epoll, kqueue or poll
SELECT_TYPE = None

# Reason for this unconventional dict initialization is the fact that on some
# platforms select.error is an aliases for OSError. We don't want the lambda
# for select.error to win over one for OSError.
_SELECT_ERROR_CHECKERS = {}
if pika.compat.PY3:
    # InterruptedError is undefined in PY2
    # pylint: disable=E0602
    _SELECT_ERROR_CHECKERS[InterruptedError] = lambda e: True

_SELECT_ERROR_CHECKERS[select.error] = lambda e: e.args[0] == errno.EINTR
_SELECT_ERROR_CHECKERS[IOError] = lambda e: e.errno == errno.EINTR
_SELECT_ERROR_CHECKERS[OSError] = lambda e: e.errno == errno.EINTR

# We can reduce the number of elements in the list by looking at super-sub
# class relationship because only the most generic ones needs to be caught.
# For now the optimization is left out.
# Following is better but still incomplete.
# _SELECT_ERRORS = tuple(filter(lambda e: not isinstance(e, OSError),
#                              _SELECT_ERROR_CHECKERS.keys())
#                       + [OSError])
_SELECT_ERRORS = tuple(_SELECT_ERROR_CHECKERS.keys())


def _is_resumable(exc):
    """Check if caught exception represents EINTR error.
    :param exc: exception; must be one of classes in _SELECT_ERRORS

    """
    checker = _SELECT_ERROR_CHECKERS.get(exc.__class__, None)
    if checker is not None:
        return checker(exc)
    else:
        return False


class SelectConnection(BaseConnection):
    """An asynchronous connection adapter that attempts to use the fastest
    event loop adapter for the given platform.

    """

    def __init__(
            self,  # pylint: disable=R0913
            parameters=None,
            on_open_callback=None,
            on_open_error_callback=None,
            on_close_callback=None,
            custom_ioloop=None,
            internal_connection_workflow=True):
        """Create a new instance of the Connection object.

        :param pika.connection.Parameters parameters: Connection parameters
        :param callable on_open_callback: Method to call on connection open
        :param None | method on_open_error_callback: Called if the connection
            can't be established or connection establishment is interrupted by
            `Connection.close()`: on_open_error_callback(Connection, exception).
        :param None | method on_close_callback: Called when a previously fully
            open connection is closed:
            `on_close_callback(Connection, exception)`, where `exception` is
            either an instance of `exceptions.ConnectionClosed` if closed by
            user or broker or exception of another type that describes the cause
            of connection failure.
        :param None | IOLoop | nbio_interface.AbstractIOServices custom_ioloop:
            Provide a custom I/O Loop object.
        :param bool internal_connection_workflow: True for autonomous connection
            establishment which is default; False for externally-managed
            connection workflow via the `create_connection()` factory.
        :raises: RuntimeError

        """
        if isinstance(custom_ioloop, nbio_interface.AbstractIOServices):
            nbio = custom_ioloop
        else:
            nbio = SelectorIOServicesAdapter(custom_ioloop or IOLoop())

        super(SelectConnection, self).__init__(
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
        nbio = SelectorIOServicesAdapter(custom_ioloop or IOLoop())

        def connection_factory(params):
            """Connection factory."""
            if params is None:
                raise ValueError('Expected pika.connection.Parameters '
                                 'instance, but got None in params arg.')
            return cls(
                parameters=params,
                custom_ioloop=nbio,
                internal_connection_workflow=False)

        return cls._start_connection_workflow(
            connection_configs=connection_configs,
            connection_factory=connection_factory,
            nbio=nbio,
            workflow=workflow,
            on_done=on_done)

    def _get_write_buffer_size(self):
        """
        :returns: Current size of output data buffered by the transport
        :rtype: int
        """
        return self._transport.get_write_buffer_size()


class _Timeout(object):
    """Represents a timeout"""

    __slots__ = (
        'deadline',
        'callback',
    )

    def __init__(self, deadline, callback):
        """
        :param float deadline: timer expiration as non-negative epoch number
        :param callable callback: callback to call when timeout expires
        :raises ValueError, TypeError:
        """

        if deadline < 0:
            raise ValueError(
                'deadline must be non-negative epoch number, but got %r' %
                (deadline,))

        if not callable(callback):
            raise TypeError(
                'callback must be a callable, but got %r' % (callback,))

        self.deadline = deadline
        self.callback = callback

    def __eq__(self, other):
        """NOTE: not supporting sort stability"""
        if isinstance(other, _Timeout):
            return self.deadline == other.deadline
        return NotImplemented

    def __ne__(self, other):
        """NOTE: not supporting sort stability"""
        result = self.__eq__(other)
        if result is not NotImplemented:
            return not result
        return NotImplemented

    def __lt__(self, other):
        """NOTE: not supporting sort stability"""
        if isinstance(other, _Timeout):
            return self.deadline < other.deadline
        return NotImplemented

    def __gt__(self, other):
        """NOTE: not supporting sort stability"""
        if isinstance(other, _Timeout):
            return self.deadline > other.deadline
        return NotImplemented

    def __le__(self, other):
        """NOTE: not supporting sort stability"""
        if isinstance(other, _Timeout):
            return self.deadline <= other.deadline
        return NotImplemented

    def __ge__(self, other):
        """NOTE: not supporting sort stability"""
        if isinstance(other, _Timeout):
            return self.deadline >= other.deadline
        return NotImplemented


class _Timer(object):
    """Manage timeouts for use in ioloop"""

    # Cancellation count threshold for triggering garbage collection of
    # cancelled timers
    _GC_CANCELLATION_THRESHOLD = 1024

    def __init__(self):
        self._timeout_heap = []

        # Number of canceled timeouts on heap; for scheduling garbage
        # collection of canceled timeouts
        self._num_cancellations = 0

    def close(self):
        """Release resources. Don't use the `_Timer` instance after closing
        it
        """
        # Eliminate potential reference cycles to aid garbage-collection
        if self._timeout_heap is not None:
            for timeout in self._timeout_heap:
                timeout.callback = None
            self._timeout_heap = None

    def call_later(self, delay, callback):
        """Schedule a one-shot timeout given delay seconds.

        NOTE: you may cancel the timer before dispatch of the callback. Timer
            Manager cancels the timer upon dispatch of the callback.

        :param float delay: Non-negative number of seconds from now until
            expiration
        :param callable callback: The callback method, having the signature
            `callback()`

        :rtype: _Timeout
        :raises ValueError, TypeError

        """
        if self._timeout_heap is None:
            raise ValueError("Timeout closed before call")

        if delay < 0:
            raise ValueError(
                'call_later: delay must be non-negative, but got %r' % (delay,))

        now = pika.compat.time_now()

        timeout = _Timeout(now + delay, callback)

        heapq.heappush(self._timeout_heap, timeout)

        LOGGER.debug(
            'call_later: added timeout %r with deadline=%r and '
            'callback=%r; now=%s; delay=%s', timeout, timeout.deadline,
            timeout.callback, now, delay)

        return timeout

    def remove_timeout(self, timeout):
        """Cancel the timeout

        :param _Timeout timeout: The timer to cancel

        """
        # NOTE removing from the heap is difficult, so we just deactivate the
        # timeout and garbage-collect it at a later time; see discussion
        # in http://docs.python.org/library/heapq.html
        if timeout.callback is None:
            LOGGER.debug(
                'remove_timeout: timeout was already removed or called %r',
                timeout)
        else:
            LOGGER.debug(
                'remove_timeout: removing timeout %r with deadline=%r '
                'and callback=%r', timeout, timeout.deadline, timeout.callback)
            timeout.callback = None
            self._num_cancellations += 1

    def get_remaining_interval(self):
        """Get the interval to the next timeout expiration

        :returns: non-negative number of seconds until next timer expiration;
                  None if there are no timers
        :rtype: float

        """
        if self._timeout_heap:
            now = pika.compat.time_now()
            interval = max(0, self._timeout_heap[0].deadline - now)
        else:
            interval = None

        return interval

    def process_timeouts(self):
        """Process pending timeouts, invoking callbacks for those whose time has
        come

        """
        if self._timeout_heap:
            now = pika.compat.time_now()

            # Remove ready timeouts from the heap now to prevent IO starvation
            # from timeouts added during callback processing
            ready_timeouts = []

            while self._timeout_heap and self._timeout_heap[0].deadline <= now:
                timeout = heapq.heappop(self._timeout_heap)
                if timeout.callback is not None:
                    ready_timeouts.append(timeout)
                else:
                    self._num_cancellations -= 1

            # Invoke ready timeout callbacks
            for timeout in ready_timeouts:
                if timeout.callback is None:
                    # Must have been canceled from a prior callback
                    self._num_cancellations -= 1
                    continue

                timeout.callback()
                timeout.callback = None

            # Garbage-collect canceled timeouts if they exceed threshold
            if (self._num_cancellations >= self._GC_CANCELLATION_THRESHOLD and
                    self._num_cancellations > (len(self._timeout_heap) >> 1)):
                self._num_cancellations = 0
                self._timeout_heap = [
                    t for t in self._timeout_heap if t.callback is not None
                ]
                heapq.heapify(self._timeout_heap)


class PollEvents(object):
    """Event flags for I/O"""

    # Use epoll's constants to keep life easy
    READ = getattr(select, 'POLLIN', 0x01)  # available for read
    WRITE = getattr(select, 'POLLOUT', 0x04)  # available for write
    ERROR = getattr(select, 'POLLERR', 0x08)  # error on associated fd


class IOLoop(AbstractSelectorIOLoop):
    """I/O loop implementation that picks a suitable poller (`select`,
     `poll`, `epoll`, `kqueue`) to use based on platform.

     Implements the
     `pika.adapters.utils.selector_ioloop_adapter.AbstractSelectorIOLoop`
     interface.

    """
    # READ/WRITE/ERROR per `AbstractSelectorIOLoop` requirements
    READ = PollEvents.READ
    WRITE = PollEvents.WRITE
    ERROR = PollEvents.ERROR

    def __init__(self):
        self._timer = _Timer()

        # Callbacks requested via `add_callback`
        self._callbacks = collections.deque()

        self._poller = self._get_poller(self._get_remaining_interval,
                                        self.process_timeouts)

    def close(self):
        """Release IOLoop's resources.

        `IOLoop.close` is intended to be called by the application or test code
        only after `IOLoop.start()` returns. After calling `close()`, no other
        interaction with the closed instance of `IOLoop` should be performed.

        """
        if self._callbacks is not None:
            self._poller.close()
            self._timer.close()
            # Set _callbacks to empty list rather than None so that race from
            # another thread calling add_callback_threadsafe() won't result in
            # AttributeError
            self._callbacks = []

    @staticmethod
    def _get_poller(get_wait_seconds, process_timeouts):
        """Determine the best poller to use for this environment and instantiate
        it.

        :param get_wait_seconds: Function for getting the maximum number of
                                 seconds to wait for IO for use by the poller
        :param process_timeouts: Function for processing timeouts for use by the
                                 poller

        :returns: The instantiated poller instance supporting `_PollerBase` API
        :rtype: object
        """

        poller = None

        kwargs = dict(
            get_wait_seconds=get_wait_seconds,
            process_timeouts=process_timeouts)

        if hasattr(select, 'epoll'):
            if not SELECT_TYPE or SELECT_TYPE == 'epoll':
                LOGGER.debug('Using EPollPoller')
                poller = EPollPoller(**kwargs)

        if not poller and hasattr(select, 'kqueue'):
            if not SELECT_TYPE or SELECT_TYPE == 'kqueue':
                LOGGER.debug('Using KQueuePoller')
                poller = KQueuePoller(**kwargs)

        if (not poller and hasattr(select, 'poll') and
                hasattr(select.poll(), 'modify')):  # pylint: disable=E1101
            if not SELECT_TYPE or SELECT_TYPE == 'poll':
                LOGGER.debug('Using PollPoller')
                poller = PollPoller(**kwargs)

        if not poller:
            LOGGER.debug('Using SelectPoller')
            poller = SelectPoller(**kwargs)

        return poller

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
        return self._timer.call_later(delay, callback)

    def remove_timeout(self, timeout_handle):
        """Remove a timeout

        :param timeout_handle: Handle of timeout to remove

        """
        self._timer.remove_timeout(timeout_handle)

    def add_callback_threadsafe(self, callback):
        """Requests a call to the given function as soon as possible in the
        context of this IOLoop's thread.

        NOTE: This is the only thread-safe method in IOLoop. All other
        manipulations of IOLoop must be performed from the IOLoop's thread.

        For example, a thread may request a call to the `stop` method of an
        ioloop that is running in a different thread via
        `ioloop.add_callback_threadsafe(ioloop.stop)`

        :param callable callback: The callback method

        """
        if not callable(callback):
            raise TypeError(
                'callback must be a callable, but got %r' % (callback,))

        # NOTE: `deque.append` is atomic
        self._callbacks.append(callback)

        # Wake up the IOLoop which may be running in another thread
        self._poller.wake_threadsafe()

        LOGGER.debug('add_callback_threadsafe: added callback=%r', callback)

    # To satisfy `AbstractSelectorIOLoop` requirement
    add_callback = add_callback_threadsafe

    def process_timeouts(self):
        """[Extension] Process pending callbacks and timeouts, invoking those
        whose time has come. Internal use only.

        """
        # Avoid I/O starvation by postponing new callbacks to the next iteration
        for _ in pika.compat.xrange(len(self._callbacks)):
            callback = self._callbacks.popleft()
            LOGGER.debug('process_timeouts: invoking callback=%r', callback)
            callback()

        self._timer.process_timeouts()

    def _get_remaining_interval(self):
        """Get the remaining interval to the next callback or timeout
        expiration.

        :returns: non-negative number of seconds until next callback or timer
                  expiration; None if there are no callbacks and timers
        :rtype: float

        """
        if self._callbacks:
            return 0

        return self._timer.get_remaining_interval()

    def add_handler(self, fd, handler, events):
        """Start watching the given file descriptor for events

        :param int fd: The file descriptor
        :param callable handler: When requested event(s) occur,
            `handler(fd, events)` will be called.
        :param int events: The event mask using READ, WRITE, ERROR.

        """
        self._poller.add_handler(fd, handler, events)

    def update_handler(self, fd, events):
        """Changes the events we watch for

        :param int fd: The file descriptor
        :param int events: The event mask using READ, WRITE, ERROR

        """
        self._poller.update_handler(fd, events)

    def remove_handler(self, fd):
        """Stop watching the given file descriptor for events

        :param int fd: The file descriptor

        """
        self._poller.remove_handler(fd)

    def start(self):
        """[API] Start the main poller loop. It will loop until requested to
        exit. See `IOLoop.stop`.

        """
        self._poller.start()

    def stop(self):
        """[API] Request exit from the ioloop. The loop is NOT guaranteed to
        stop before this method returns.

        To invoke `stop()` safely from a thread other than this IOLoop's thread,
        call it via `add_callback_threadsafe`; e.g.,

            `ioloop.add_callback_threadsafe(ioloop.stop)`

        """
        self._poller.stop()

    def activate_poller(self):
        """[Extension] Activate the poller

        """
        self._poller.activate_poller()

    def deactivate_poller(self):
        """[Extension] Deactivate the poller

        """
        self._poller.deactivate_poller()

    def poll(self):
        """[Extension] Wait for events of interest on registered file
        descriptors until an event of interest occurs or next timer deadline or
        `_PollerBase._MAX_POLL_TIMEOUT`, whichever is sooner, and dispatch the
        corresponding event handlers.

        """
        self._poller.poll()


class _PollerBase(pika.compat.AbstractBase):  # pylint: disable=R0902
    """Base class for select-based IOLoop implementations"""

    # Drop out of the poll loop every _MAX_POLL_TIMEOUT secs as a worst case;
    # this is only a backstop value; we will run timeouts when they are
    # scheduled.
    _MAX_POLL_TIMEOUT = 5

    # if the poller uses MS override with 1000
    POLL_TIMEOUT_MULT = 1

    def __init__(self, get_wait_seconds, process_timeouts):
        """
        :param get_wait_seconds: Function for getting the maximum number of
                                 seconds to wait for IO for use by the poller
        :param process_timeouts: Function for processing timeouts for use by the
                                 poller

        """
        self._get_wait_seconds = get_wait_seconds
        self._process_timeouts = process_timeouts

        # We guard access to the waking file descriptors to avoid races from
        # closing them while another thread is calling our `wake()` method.
        self._waking_mutex = threading.Lock()

        # fd-to-handler function mappings
        self._fd_handlers = dict()

        # event-to-fdset mappings
        self._fd_events = {
            PollEvents.READ: set(),
            PollEvents.WRITE: set(),
            PollEvents.ERROR: set()
        }

        self._processing_fd_event_map = {}

        # Reentrancy tracker of the `start` method
        self._running = False

        self._stopping = False

        # Create ioloop-interrupt socket pair and register read handler.
        self._r_interrupt, self._w_interrupt = self._get_interrupt_pair()
        self.add_handler(self._r_interrupt.fileno(), self._read_interrupt,
                         PollEvents.READ)

    def close(self):
        """Release poller's resources.

        `close()` is intended to be called after the poller's `start()` method
        returns. After calling `close()`, no other interaction with the closed
        poller instance should be performed.

        """
        # Unregister and close ioloop-interrupt socket pair; mutual exclusion is
        # necessary to avoid race condition with `wake_threadsafe` executing in
        # another thread's context
        assert not self._running, 'Cannot call close() before start() unwinds.'

        with self._waking_mutex:
            if self._w_interrupt is not None:
                self.remove_handler(self._r_interrupt.fileno())  # pylint: disable=E1101
                self._r_interrupt.close()
                self._r_interrupt = None
                self._w_interrupt.close()
                self._w_interrupt = None

        self.deactivate_poller()

        self._fd_handlers = None
        self._fd_events = None
        self._processing_fd_event_map = None

    def wake_threadsafe(self):
        """Wake up the poller as soon as possible. As the name indicates, this
        method is thread-safe.

        """
        with self._waking_mutex:
            if self._w_interrupt is None:
                return

            try:
                # Send byte to interrupt the poll loop, use send() instead of
                # os.write for Windows compatibility
                self._w_interrupt.send(b'X')
            except pika.compat.SOCKET_ERROR as err:
                if err.errno != errno.EWOULDBLOCK:
                    raise
            except Exception as err:
                # There's nothing sensible to do here, we'll exit the interrupt
                # loop after POLL_TIMEOUT secs in worst case anyway.
                LOGGER.warning("Failed to send interrupt to poller: %s", err)
                raise

    def _get_max_wait(self):
        """Get the interval to the next timeout event, or a default interval

        :returns: maximum number of self.POLL_TIMEOUT_MULT-scaled time units
                  to wait for IO events
        :rtype: int

        """
        delay = self._get_wait_seconds()
        if delay is None:
            delay = self._MAX_POLL_TIMEOUT
        else:
            delay = min(delay, self._MAX_POLL_TIMEOUT)

        return delay * self.POLL_TIMEOUT_MULT

    def add_handler(self, fileno, handler, events):
        """Add a new fileno to the set to be monitored

        :param int fileno: The file descriptor
        :param callable handler: What is called when an event happens
        :param int events: The event mask using READ, WRITE, ERROR

        """
        self._fd_handlers[fileno] = handler
        self._set_handler_events(fileno, events)

        # Inform the derived class
        self._register_fd(fileno, events)

    def update_handler(self, fileno, events):
        """Set the events to the current events

        :param int fileno: The file descriptor
        :param int events: The event mask using READ, WRITE, ERROR

        """
        # Record the change
        events_cleared, events_set = self._set_handler_events(fileno, events)

        # Inform the derived class
        self._modify_fd_events(
            fileno,
            events=events,
            events_to_clear=events_cleared,
            events_to_set=events_set)

    def remove_handler(self, fileno):
        """Remove a file descriptor from the set

        :param int fileno: The file descriptor

        """
        try:
            del self._processing_fd_event_map[fileno]
        except KeyError:
            pass

        events_cleared, _ = self._set_handler_events(fileno, 0)
        del self._fd_handlers[fileno]

        # Inform the derived class
        self._unregister_fd(fileno, events_to_clear=events_cleared)

    def _set_handler_events(self, fileno, events):
        """Set the handler's events to the given events; internal to
        `_PollerBase`.

        :param int fileno: The file descriptor
        :param int events: The event mask (READ, WRITE, ERROR)

        :returns: a 2-tuple (events_cleared, events_set)
        :rtype: tuple
        """
        events_cleared = 0
        events_set = 0

        for evt in (PollEvents.READ, PollEvents.WRITE, PollEvents.ERROR):
            if events & evt:
                if fileno not in self._fd_events[evt]:
                    self._fd_events[evt].add(fileno)
                    events_set |= evt
            else:
                if fileno in self._fd_events[evt]:
                    self._fd_events[evt].discard(fileno)
                    events_cleared |= evt

        return events_cleared, events_set

    def activate_poller(self):
        """Activate the poller

        """
        # Activate the underlying poller and register current events
        self._init_poller()
        fd_to_events = collections.defaultdict(int)
        for event, file_descriptors in self._fd_events.items():
            for fileno in file_descriptors:
                fd_to_events[fileno] |= event

        for fileno, events in fd_to_events.items():
            self._register_fd(fileno, events)

    def deactivate_poller(self):
        """Deactivate the poller

        """
        self._uninit_poller()

    def start(self):
        """Start the main poller loop. It will loop until requested to exit.
        This method is not reentrant and will raise an error if called
        recursively (pika/pika#1095)

        :raises: RuntimeError

        """
        if self._running:
            raise RuntimeError('IOLoop is not reentrant and is already running')

        LOGGER.debug('Entering IOLoop')
        self._running = True
        self.activate_poller()

        try:
            # Run event loop
            while not self._stopping:
                self.poll()
                self._process_timeouts()
        finally:
            try:
                LOGGER.debug('Deactivating poller')
                self.deactivate_poller()
            finally:
                self._stopping = False
                self._running = False

    def stop(self):
        """Request exit from the ioloop. The loop is NOT guaranteed to stop
        before this method returns.

        """
        LOGGER.debug('Stopping IOLoop')
        self._stopping = True
        self.wake_threadsafe()

    @abc.abstractmethod
    def poll(self):
        """Wait for events on interested filedescriptors.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _init_poller(self):
        """Notify the implementation to allocate the poller resource"""
        raise NotImplementedError

    @abc.abstractmethod
    def _uninit_poller(self):
        """Notify the implementation to release the poller resource"""
        raise NotImplementedError

    @abc.abstractmethod
    def _register_fd(self, fileno, events):
        """The base class invokes this method to notify the implementation to
        register the file descriptor with the polling object. The request must
        be ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events: The event mask (READ, WRITE, ERROR)
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _modify_fd_events(self, fileno, events, events_to_clear, events_to_set):
        """The base class invoikes this method to notify the implementation to
        modify an already registered file descriptor. The request must be
        ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events: absolute events (READ, WRITE, ERROR)
        :param int events_to_clear: The events to clear (READ, WRITE, ERROR)
        :param int events_to_set: The events to set (READ, WRITE, ERROR)
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _unregister_fd(self, fileno, events_to_clear):
        """The base class invokes this method to notify the implementation to
        unregister the file descriptor being tracked by the polling object. The
        request must be ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events_to_clear: The events to clear (READ, WRITE, ERROR)
        """
        raise NotImplementedError

    def _dispatch_fd_events(self, fd_event_map):
        """ Helper to dispatch callbacks for file descriptors that received
        events.

        Before doing so we re-calculate the event mask based on what is
        currently set in case it has been changed under our feet by a
        previous callback. We also take a store a refernce to the
        fd_event_map so that we can detect removal of an
        fileno during processing of another callback and not generate
        spurious callbacks on it.

        :param dict fd_event_map: Map of fds to events received on them.
        """
        # Reset the prior map; if the call is nested, this will suppress the
        # remaining dispatch in the earlier call.
        self._processing_fd_event_map.clear()

        self._processing_fd_event_map = fd_event_map

        for fileno in pika.compat.dictkeys(fd_event_map):
            if fileno not in fd_event_map:
                # the fileno has been removed from the map under our feet.
                continue

            events = fd_event_map[fileno]
            for evt in [PollEvents.READ, PollEvents.WRITE, PollEvents.ERROR]:
                if fileno not in self._fd_events[evt]:
                    events &= ~evt

            if events:
                handler = self._fd_handlers[fileno]
                handler(fileno, events)

    @staticmethod
    def _get_interrupt_pair():
        """ Use a socketpair to be able to interrupt the ioloop if called
        from another thread. Socketpair() is not supported on some OS (Win)
        so use a pair of simple TCP sockets instead. The sockets will be
        closed and garbage collected by python when the ioloop itself is.
        """
        return pika.compat._nonblocking_socketpair()  # pylint: disable=W0212

    def _read_interrupt(self, _interrupt_fd, _events):
        """ Read the interrupt byte(s). We ignore the event mask as we can ony
        get here if there's data to be read on our fd.

        :param int _interrupt_fd: (unused) The file descriptor to read from
        :param int _events: (unused) The events generated for this fd
        """
        try:
            # NOTE Use recv instead of os.read for windows compatibility
            self._r_interrupt.recv(512)  # pylint: disable=E1101
        except pika.compat.SOCKET_ERROR as err:
            if err.errno != errno.EAGAIN:
                raise


class SelectPoller(_PollerBase):
    """Default behavior is to use Select since it's the widest supported and has
    all of the methods we need for child classes as well. One should only need
    to override the update_handler and start methods for additional types.

    """
    # if the poller uses MS specify 1000
    POLL_TIMEOUT_MULT = 1

    def poll(self):
        """Wait for events of interest on registered file descriptors until an
        event of interest occurs or next timer deadline or _MAX_POLL_TIMEOUT,
        whichever is sooner, and dispatch the corresponding event handlers.

        """
        while True:
            try:
                if (self._fd_events[PollEvents.READ] or
                        self._fd_events[PollEvents.WRITE] or
                        self._fd_events[PollEvents.ERROR]):
                    read, write, error = select.select(
                        self._fd_events[PollEvents.READ],
                        self._fd_events[PollEvents.WRITE],
                        self._fd_events[PollEvents.ERROR], self._get_max_wait())
                else:
                    # NOTE When called without any FDs, select fails on
                    # Windows with error 10022, 'An invalid argument was
                    # supplied'.
                    time.sleep(self._get_max_wait())
                    read, write, error = [], [], []
                break
            except _SELECT_ERRORS as error:
                if _is_resumable(error):
                    continue
                else:
                    raise

        # Build an event bit mask for each fileno we've received an event for
        fd_event_map = collections.defaultdict(int)
        for fd_set, evt in zip(
                (read, write, error),
                (PollEvents.READ, PollEvents.WRITE, PollEvents.ERROR)):
            for fileno in fd_set:
                fd_event_map[fileno] |= evt

        self._dispatch_fd_events(fd_event_map)

    def _init_poller(self):
        """Notify the implementation to allocate the poller resource"""
        # It's a no op in SelectPoller

    def _uninit_poller(self):
        """Notify the implementation to release the poller resource"""
        # It's a no op in SelectPoller

    def _register_fd(self, fileno, events):
        """The base class invokes this method to notify the implementation to
        register the file descriptor with the polling object. The request must
        be ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events: The event mask using READ, WRITE, ERROR
        """
        # It's a no op in SelectPoller

    def _modify_fd_events(self, fileno, events, events_to_clear, events_to_set):
        """The base class invoikes this method to notify the implementation to
        modify an already registered file descriptor. The request must be
        ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events: absolute events (READ, WRITE, ERROR)
        :param int events_to_clear: The events to clear (READ, WRITE, ERROR)
        :param int events_to_set: The events to set (READ, WRITE, ERROR)
        """
        # It's a no op in SelectPoller

    def _unregister_fd(self, fileno, events_to_clear):
        """The base class invokes this method to notify the implementation to
        unregister the file descriptor being tracked by the polling object. The
        request must be ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events_to_clear: The events to clear (READ, WRITE, ERROR)
        """
        # It's a no op in SelectPoller


class KQueuePoller(_PollerBase):
    # pylint: disable=E1101

    """KQueuePoller works on BSD based systems and is faster than select"""

    def __init__(self, get_wait_seconds, process_timeouts):
        """Create an instance of the KQueuePoller
        """
        self._kqueue = None
        super(KQueuePoller, self).__init__(get_wait_seconds, process_timeouts)

    @staticmethod
    def _map_event(kevent):
        """return the event type associated with a kevent object

        :param kevent kevent: a kevent object as returned by kqueue.control()

        """
        mask = 0
        if kevent.filter == select.KQ_FILTER_READ:
            mask = PollEvents.READ
        elif kevent.filter == select.KQ_FILTER_WRITE:
            mask = PollEvents.WRITE
            if kevent.flags & select.KQ_EV_EOF:
                # May be set when the peer reader disconnects. We don't check
                # KQ_EV_EOF for KQ_FILTER_READ because in that case it may be
                # set before the remaining data is consumed from sockbuf.
                mask |= PollEvents.ERROR
        elif kevent.flags & select.KQ_EV_ERROR:
            mask = PollEvents.ERROR
        else:
            LOGGER.critical('Unexpected kevent: %s', kevent)

        return mask

    def poll(self):
        """Wait for events of interest on registered file descriptors until an
        event of interest occurs or next timer deadline or _MAX_POLL_TIMEOUT,
        whichever is sooner, and dispatch the corresponding event handlers.

        """
        while True:
            try:
                kevents = self._kqueue.control(None, 1000, self._get_max_wait())
                break
            except _SELECT_ERRORS as error:
                if _is_resumable(error):
                    continue
                else:
                    raise

        fd_event_map = collections.defaultdict(int)
        for event in kevents:
            fd_event_map[event.ident] |= self._map_event(event)

        self._dispatch_fd_events(fd_event_map)

    def _init_poller(self):
        """Notify the implementation to allocate the poller resource"""
        assert self._kqueue is None

        self._kqueue = select.kqueue()

    def _uninit_poller(self):
        """Notify the implementation to release the poller resource"""
        if self._kqueue is not None:
            self._kqueue.close()
            self._kqueue = None

    def _register_fd(self, fileno, events):
        """The base class invokes this method to notify the implementation to
        register the file descriptor with the polling object. The request must
        be ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events: The event mask using READ, WRITE, ERROR
        """
        self._modify_fd_events(
            fileno, events=events, events_to_clear=0, events_to_set=events)

    def _modify_fd_events(self, fileno, events, events_to_clear, events_to_set):
        """The base class invoikes this method to notify the implementation to
        modify an already registered file descriptor. The request must be
        ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events: absolute events (READ, WRITE, ERROR)
        :param int events_to_clear: The events to clear (READ, WRITE, ERROR)
        :param int events_to_set: The events to set (READ, WRITE, ERROR)
        """
        if self._kqueue is None:
            return

        kevents = list()

        if events_to_clear & PollEvents.READ:
            kevents.append(
                select.kevent(
                    fileno,
                    filter=select.KQ_FILTER_READ,
                    flags=select.KQ_EV_DELETE))
        if events_to_set & PollEvents.READ:
            kevents.append(
                select.kevent(
                    fileno,
                    filter=select.KQ_FILTER_READ,
                    flags=select.KQ_EV_ADD))
        if events_to_clear & PollEvents.WRITE:
            kevents.append(
                select.kevent(
                    fileno,
                    filter=select.KQ_FILTER_WRITE,
                    flags=select.KQ_EV_DELETE))
        if events_to_set & PollEvents.WRITE:
            kevents.append(
                select.kevent(
                    fileno,
                    filter=select.KQ_FILTER_WRITE,
                    flags=select.KQ_EV_ADD))

        self._kqueue.control(kevents, 0)

    def _unregister_fd(self, fileno, events_to_clear):
        """The base class invokes this method to notify the implementation to
        unregister the file descriptor being tracked by the polling object. The
        request must be ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events_to_clear: The events to clear (READ, WRITE, ERROR)
        """
        self._modify_fd_events(
            fileno, events=0, events_to_clear=events_to_clear, events_to_set=0)


class PollPoller(_PollerBase):
    """Poll works on Linux and can have better performance than EPoll in
    certain scenarios.  Both are faster than select.

    """
    POLL_TIMEOUT_MULT = 1000

    def __init__(self, get_wait_seconds, process_timeouts):
        """Create an instance of the KQueuePoller

        """
        self._poll = None
        super(PollPoller, self).__init__(get_wait_seconds, process_timeouts)

    @staticmethod
    def _create_poller():
        """
        :rtype: `select.poll`
        """
        return select.poll()  # pylint: disable=E1101

    def poll(self):
        """Wait for events of interest on registered file descriptors until an
        event of interest occurs or next timer deadline or _MAX_POLL_TIMEOUT,
        whichever is sooner, and dispatch the corresponding event handlers.

        """
        while True:
            try:
                events = self._poll.poll(self._get_max_wait())
                break
            except _SELECT_ERRORS as error:
                if _is_resumable(error):
                    continue
                else:
                    raise

        fd_event_map = collections.defaultdict(int)
        for fileno, event in events:
            # NOTE: On OS X, when poll() sets POLLHUP, it's mutually-exclusive with
            # POLLOUT and it doesn't seem to set POLLERR along with POLLHUP when
            # socket connection fails, for example. So, we need to at least add
            # POLLERR when we see POLLHUP
            if (event & select.POLLHUP) and pika.compat.ON_OSX:
                event |= select.POLLERR

            fd_event_map[fileno] |= event

        self._dispatch_fd_events(fd_event_map)

    def _init_poller(self):
        """Notify the implementation to allocate the poller resource"""
        assert self._poll is None

        self._poll = self._create_poller()

    def _uninit_poller(self):
        """Notify the implementation to release the poller resource"""
        if self._poll is not None:
            if hasattr(self._poll, "close"):
                self._poll.close()

            self._poll = None

    def _register_fd(self, fileno, events):
        """The base class invokes this method to notify the implementation to
        register the file descriptor with the polling object. The request must
        be ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events: The event mask using READ, WRITE, ERROR
        """
        if self._poll is not None:
            self._poll.register(fileno, events)

    def _modify_fd_events(self, fileno, events, events_to_clear, events_to_set):
        """The base class invoikes this method to notify the implementation to
        modify an already registered file descriptor. The request must be
        ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events: absolute events (READ, WRITE, ERROR)
        :param int events_to_clear: The events to clear (READ, WRITE, ERROR)
        :param int events_to_set: The events to set (READ, WRITE, ERROR)
        """
        if self._poll is not None:
            self._poll.modify(fileno, events)

    def _unregister_fd(self, fileno, events_to_clear):
        """The base class invokes this method to notify the implementation to
        unregister the file descriptor being tracked by the polling object. The
        request must be ignored if the poller is not activated.

        :param int fileno: The file descriptor
        :param int events_to_clear: The events to clear (READ, WRITE, ERROR)
        """
        if self._poll is not None:
            self._poll.unregister(fileno)


class EPollPoller(PollPoller):
    """EPoll works on Linux and can have better performance than Poll in
    certain scenarios. Both are faster than select.

    """
    POLL_TIMEOUT_MULT = 1

    @staticmethod
    def _create_poller():
        """
        :rtype: `select.poll`
        """
        return select.epoll()  # pylint: disable=E1101
