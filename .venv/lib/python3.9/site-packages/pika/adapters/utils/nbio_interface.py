"""Non-blocking I/O interface for pika connection adapters.

I/O interface expected by `pika.adapters.base_connection.BaseConnection`

NOTE: This API is modeled after asyncio in python3 for a couple of reasons
    1. It's a sensible API
    2. To make it easy to implement at least on top of the built-in asyncio

Furthermore, the API caters to the needs of pika core and lack of generalization
is intentional for the sake of reducing complexity of the implementation and
testing and lessening the maintenance burden.

"""
import abc

import pika.compat


class AbstractIOServices(pika.compat.AbstractBase):
    """Interface to I/O services required by `pika.adapters.BaseConnection` and
    related utilities.

    NOTE: This is not a public API. Pika users should rely on the native I/O
    loop APIs (e.g., asyncio event loop, tornado ioloop, twisted reactor, etc.)
    that corresponds to the chosen Connection adapter.

    """

    @abc.abstractmethod
    def get_native_ioloop(self):
        """Returns the native I/O loop instance, such as Twisted reactor,
        asyncio's or tornado's event loop

        """
        raise NotImplementedError

    @abc.abstractmethod
    def close(self):
        """Release IOLoop's resources.

        the `close()` method is intended to be called by Pika's own test
        code only after `start()` returns. After calling `close()`, no other
        interaction with the closed instance of `IOLoop` should be performed.

        NOTE: This method is provided for Pika's own test scripts that need to
        be able to run I/O loops generically to test multiple Connection Adapter
        implementations. Pika users should use the native I/O loop's API
        instead.

        """
        raise NotImplementedError

    @abc.abstractmethod
    def run(self):
        """Run the I/O loop. It will loop until requested to exit. See `stop()`.

        NOTE: the outcome or restarting an instance that had been stopped is
        UNDEFINED!

        NOTE: This method is provided for Pika's own test scripts that need to
        be able to run I/O loops generically to test multiple Connection Adapter
        implementations (not all of the supported I/O Loop frameworks have
        methods named start/stop). Pika users should use the native I/O loop's
        API instead.

        """
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self):
        """Request exit from the ioloop. The loop is NOT guaranteed to
        stop before this method returns.

        NOTE: The outcome of calling `stop()` on a non-running instance is
        UNDEFINED!

        NOTE: This method is provided for Pika's own test scripts that need to
        be able to run I/O loops generically to test multiple Connection Adapter
        implementations (not all of the supported I/O Loop frameworks have
        methods named start/stop). Pika users should use the native I/O loop's
        API instead.

        To invoke `stop()` safely from a thread other than this IOLoop's thread,
        call it via `add_callback_threadsafe`; e.g.,

            `ioloop.add_callback_threadsafe(ioloop.stop)`

        """
        raise NotImplementedError

    @abc.abstractmethod
    def add_callback_threadsafe(self, callback):
        """Requests a call to the given function as soon as possible. It will be
        called from this IOLoop's thread.

        NOTE: This is the only thread-safe method offered by the IOLoop adapter.
              All other manipulations of the IOLoop adapter and objects governed
              by it must be performed from the IOLoop's thread.

        NOTE: if you know that the requester is running on the same thread as
              the connection it is more efficient to use the
              `ioloop.call_later()` method with a delay of 0.

        :param callable callback: The callback method; must be callable.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def call_later(self, delay, callback):
        """Add the callback to the IOLoop timer to be called after delay seconds
        from the time of call on best-effort basis. Returns a handle to the
        timeout.

        If two are scheduled for the same time, it's undefined which one will
        be called first.

        :param float delay: The number of seconds to wait to call callback
        :param callable callback: The callback method
        :returns: A handle that can be used to cancel the request.
        :rtype: AbstractTimerReference

        """
        raise NotImplementedError

    @abc.abstractmethod
    def getaddrinfo(self,
                    host,
                    port,
                    on_done,
                    family=0,
                    socktype=0,
                    proto=0,
                    flags=0):
        """Perform the equivalent of `socket.getaddrinfo()` asynchronously.

        See `socket.getaddrinfo()` for the standard args.

        :param callable on_done: user callback that takes the return value of
            `socket.getaddrinfo()` upon successful completion or exception upon
            failure (check for `BaseException`) as its only arg. It will not be
            called if the operation was cancelled.
        :rtype: AbstractIOReference
        """
        raise NotImplementedError

    @abc.abstractmethod
    def connect_socket(self, sock, resolved_addr, on_done):
        """Perform the equivalent of `socket.connect()` on a previously-resolved
        address asynchronously.

        IMPLEMENTATION NOTE: Pika's connection logic resolves the addresses
            prior to making socket connections, so we don't need to burden the
            implementations of this method with the extra logic of asynchronous
            DNS resolution. Implementations can use `socket.inet_pton()` to
            verify the address.

        :param socket.socket sock: non-blocking socket that needs to be
            connected via `socket.socket.connect()`
        :param tuple resolved_addr: resolved destination address/port two-tuple
            as per `socket.socket.connect()`, except that the first element must
            be an actual IP address that's consistent with the given socket's
            address family.
        :param callable on_done: user callback that takes None upon successful
            completion or exception (check for `BaseException`) upon error as
            its only arg. It will not be called if the operation was cancelled.

        :rtype: AbstractIOReference
        :raises ValueError: if host portion of `resolved_addr` is not an IP
            address or is inconsistent with the socket's address family as
            validated via `socket.inet_pton()`
        """
        raise NotImplementedError

    @abc.abstractmethod
    def create_streaming_connection(self,
                                    protocol_factory,
                                    sock,
                                    on_done,
                                    ssl_context=None,
                                    server_hostname=None):
        """Perform SSL session establishment, if requested, on the already-
        connected socket and link the streaming transport/protocol pair.

        NOTE: This method takes ownership of the socket.

        :param callable protocol_factory: called without args, returns an
            instance with the `AbstractStreamProtocol` interface. The protocol's
            `connection_made(transport)` method will be called to link it to
            the transport after remaining connection activity (e.g., SSL session
            establishment), if any, is completed successfully.
        :param socket.socket sock: Already-connected, non-blocking
            `socket.SOCK_STREAM` socket to be used by the transport. We take
            ownership of this socket.
        :param callable on_done: User callback
            `on_done(BaseException | (transport, protocol))` to be notified when
            the asynchronous operation completes. An exception arg indicates
            failure (check for `BaseException`); otherwise the two-tuple will
            contain the linked transport/protocol pair having
            AbstractStreamTransport and AbstractStreamProtocol interfaces
            respectively.
        :param None | ssl.SSLContext ssl_context: if None, this will proceed as
            a plaintext connection; otherwise, if not None, SSL session
            establishment will be performed prior to linking the transport and
            protocol.
        :param str | None server_hostname: For use during SSL session
            establishment to match against the target server's certificate. The
            value `None` disables this check (which is a huge security risk)
        :rtype: AbstractIOReference
        """
        raise NotImplementedError


class AbstractFileDescriptorServices(pika.compat.AbstractBase):
    """Interface definition of common non-blocking file descriptor services
    required by some utility implementations.

    NOTE: This is not a public API. Pika users should rely on the native I/O
    loop APIs (e.g., asyncio event loop, tornado ioloop, twisted reactor, etc.)
    that corresponds to the chosen Connection adapter.

    """

    @abc.abstractmethod
    def set_reader(self, fd, on_readable):
        """Call the given callback when the file descriptor is readable.
        Replace prior reader, if any, for the given file descriptor.

        :param fd: file descriptor
        :param callable on_readable: a callback taking no args to be notified
            when fd becomes readable.

        """
        raise NotImplementedError

    @abc.abstractmethod
    def remove_reader(self, fd):
        """Stop watching the given file descriptor for readability

        :param fd: file descriptor
        :returns: True if reader was removed; False if none was registered.
        :rtype: bool

        """
        raise NotImplementedError

    @abc.abstractmethod
    def set_writer(self, fd, on_writable):
        """Call the given callback whenever the file descriptor is writable.
        Replace prior writer callback, if any, for the given file descriptor.

        IMPLEMENTATION NOTE: For portability, implementations of
            `set_writable()` should also watch for indication of error on the
            socket and treat it as equivalent to the writable indication (e.g.,
            also adding the socket to the `exceptfds` arg of `socket.select()`
            and calling the `on_writable` callback if `select.select()`
            indicates that the socket is in error state). Specifically, Windows
            (unlike POSIX) only indicates error on the socket (but not writable)
            when connection establishment fails.

        :param fd: file descriptor
        :param callable on_writable: a callback taking no args to be notified
            when fd becomes writable.

        """
        raise NotImplementedError

    @abc.abstractmethod
    def remove_writer(self, fd):
        """Stop watching the given file descriptor for writability

        :param fd: file descriptor
        :returns: True if reader was removed; False if none was registered.
        :rtype: bool

        """
        raise NotImplementedError


class AbstractTimerReference(pika.compat.AbstractBase):
    """Reference to asynchronous operation"""

    @abc.abstractmethod
    def cancel(self):
        """Cancel callback. If already cancelled, has no affect.
        """
        raise NotImplementedError


class AbstractIOReference(pika.compat.AbstractBase):
    """Reference to asynchronous I/O operation"""

    @abc.abstractmethod
    def cancel(self):
        """Cancel pending operation

        :returns: False if was already done or cancelled; True otherwise
        :rtype: bool
        """
        raise NotImplementedError


class AbstractStreamProtocol(pika.compat.AbstractBase):
    """Stream protocol interface. It's compatible with a subset of
    `asyncio.protocols.Protocol` for compatibility with asyncio-based
    `AbstractIOServices` implementation.

    """

    @abc.abstractmethod
    def connection_made(self, transport):
        """Introduces transport to protocol after transport is connected.

        :param AbstractStreamTransport transport:
        :raises Exception: Exception-based exception on error
        """
        raise NotImplementedError

    @abc.abstractmethod
    def connection_lost(self, error):
        """Called upon loss or closing of connection.

        NOTE: `connection_made()` and `connection_lost()` are each called just
        once and in that order. All other callbacks are called between them.

        :param BaseException | None error: An exception (check for
            `BaseException`) indicates connection failure. None indicates that
            connection was closed on this side, such as when it's aborted or
            when `AbstractStreamProtocol.eof_received()` returns a result that
            doesn't evaluate to True.
        :raises Exception: Exception-based exception on error
        """
        raise NotImplementedError

    @abc.abstractmethod
    def eof_received(self):
        """Called after the remote peer shuts its write end of the connection.

        :returns: A falsy value (including None) will cause the transport to
            close itself, resulting in an eventual `connection_lost()` call
            from the transport. If a truthy value is returned, it will be the
            protocol's responsibility to close/abort the transport.
        :rtype: falsy|truthy
        :raises Exception: Exception-based exception on error
        """
        raise NotImplementedError

    @abc.abstractmethod
    def data_received(self, data):
        """Called to deliver incoming data to the protocol.

        :param data: Non-empty data bytes.
        :raises Exception: Exception-based exception on error
        """
        raise NotImplementedError

    # pylint: disable=W0511
    # TODO Undecided whether we need write flow-control yet, although it seems
    #      like a good idea.
    # @abc.abstractmethod
    # def pause_writing(self):
    #     """Called when the transport's write buffer size becomes greater than or
    #     equal to the transport's high-water mark. It won't be called again until
    #     the transport's write buffer gets back to its low-water mark and then
    #     returns to/past the hight-water mark again.
    #     """
    #     raise NotImplementedError
    #
    # @abc.abstractmethod
    # def resume_writing(self):
    #     """Called when the transport's write buffer size becomes less than or
    #     equal to the transport's low-water mark.
    #     """
    #     raise NotImplementedError


class AbstractStreamTransport(pika.compat.AbstractBase):
    """Stream transport interface. It's compatible with a subset of
    `asyncio.transports.Transport` for compatibility with asyncio-based
    `AbstractIOServices` implementation.

    """

    @abc.abstractmethod
    def abort(self):
        """Close connection abruptly without waiting for pending I/O to
        complete. Will invoke the corresponding protocol's `connection_lost()`
        method asynchronously (not in context of the abort() call).

        :raises Exception: Exception-based exception on error
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_protocol(self):
        """Return the protocol linked to this transport.

        :rtype: AbstractStreamProtocol
        :raises Exception: Exception-based exception on error
        """
        raise NotImplementedError

    @abc.abstractmethod
    def write(self, data):
        """Buffer the given data until it can be sent asynchronously.

        :param bytes data:
        :raises ValueError: if called with empty data
        :raises Exception: Exception-based exception on error
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_write_buffer_size(self):
        """
        :returns: Current size of output data buffered by the transport
        :rtype: int
        """
        raise NotImplementedError

    # pylint: disable=W0511
    # TODO Udecided whether we need write flow-control yet, although it seems
    #      like a good idea.
    # @abc.abstractmethod
    # def set_write_buffer_limits(self, high, low):
    #     """Set thresholds for calling the protocol's `pause_writing()`
    #     and `resume_writing()` methods. `low` must be less than or equal to
    #     `high`.
    #
    #     NOTE The unintuitive order of the args is preserved to match the
    #     corresponding method in `asyncio.WriteTransport`. I would expect `low`
    #     to be the first arg, especially since
    #     `asyncio.WriteTransport.get_write_buffer_limits()` returns them in the
    #     opposite order. This seems error-prone.
    #
    #     See `asyncio.WriteTransport.get_write_buffer_limits()` for more details
    #     about the args.
    #
    #     :param int high: non-negative high-water mark.
    #     :param int low: non-negative low-water mark.
    #     """
    #     raise NotImplementedError
