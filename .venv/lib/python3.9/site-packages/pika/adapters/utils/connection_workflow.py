"""Implements `AMQPConnectionWorkflow` - the default workflow of performing
multiple TCP/[SSL]/AMQP connection attempts with timeouts and retries until one
succeeds or all attempts fail.

Defines the interface `AbstractAMQPConnectionWorkflow` that facilitates
implementing custom connection workflows.

"""

import functools
import logging
import socket

import pika.compat
import pika.exceptions
import pika.tcp_socket_opts
from pika import __version__

_LOG = logging.getLogger(__name__)


class AMQPConnectorException(Exception):
    """Base exception for this module"""


class AMQPConnectorStackTimeout(AMQPConnectorException):
    """Overall TCP/[SSL]/AMQP stack connection attempt timed out."""


class AMQPConnectorAborted(AMQPConnectorException):
    """Asynchronous request was aborted"""


class AMQPConnectorWrongState(AMQPConnectorException):
    """AMQPConnector operation requested in wrong state, such as aborting after
    completion was reported.
    """


class AMQPConnectorPhaseErrorBase(AMQPConnectorException):
    """Wrapper for exception that occurred during a particular bring-up phase.

    """

    def __init__(self, exception, *args):
        """

        :param BaseException exception: error that occurred while waiting for a
            subclass-specific protocol bring-up phase to complete.
        :param args: args for parent class
        """
        super(AMQPConnectorPhaseErrorBase, self).__init__(*args)
        self.exception = exception

    def __repr__(self):
        return '{}: {!r}'.format(self.__class__.__name__, self.exception)


class AMQPConnectorSocketConnectError(AMQPConnectorPhaseErrorBase):
    """Error connecting TCP socket to remote peer"""


class AMQPConnectorTransportSetupError(AMQPConnectorPhaseErrorBase):
    """Error setting up transport after TCP connected but before AMQP handshake.

    """


class AMQPConnectorAMQPHandshakeError(AMQPConnectorPhaseErrorBase):
    """Error during AMQP handshake"""


class AMQPConnectionWorkflowAborted(AMQPConnectorException):
    """AMQP Connection workflow was aborted."""


class AMQPConnectionWorkflowWrongState(AMQPConnectorException):
    """AMQP Connection Workflow operation requested in wrong state, such as
    aborting after completion was reported.
    """


class AMQPConnectionWorkflowFailed(AMQPConnectorException):
    """Indicates that AMQP connection workflow failed.

    """

    def __init__(self, exceptions, *args):
        """
        :param sequence exceptions: Exceptions that occurred during the
            workflow.
        :param args: args to pass to base class

        """
        super(AMQPConnectionWorkflowFailed, self).__init__(*args)
        self.exceptions = tuple(exceptions)

    def __repr__(self):
        return ('{}: {} exceptions in all; last exception - {!r}; first '
                'exception - {!r}').format(
                    self.__class__.__name__, len(self.exceptions),
                    self.exceptions[-1],
                    self.exceptions[0] if len(self.exceptions) > 1 else None)


class AMQPConnector(object):
    """Performs a single TCP/[SSL]/AMQP connection workflow.

    """

    _STATE_INIT = 0  # start() hasn't been called yet
    _STATE_TCP = 1  # TCP/IP connection establishment
    _STATE_TRANSPORT = 2  # [SSL] and transport linkup
    _STATE_AMQP = 3  # AMQP connection handshake
    _STATE_TIMEOUT = 4  # overall TCP/[SSL]/AMQP timeout
    _STATE_ABORTING = 5  # abort() called - aborting workflow
    _STATE_DONE = 6  # result reported to client

    def __init__(self, conn_factory, nbio):
        """

        :param callable conn_factory: A function that takes
            `pika.connection.Parameters` as its only arg and returns a brand new
            `pika.connection.Connection`-based adapter instance each time it is
            called. The factory must instantiate the connection with
            `internal_connection_workflow=False`.
        :param pika.adapters.utils.nbio_interface.AbstractIOServices nbio:

        """
        self._conn_factory = conn_factory
        self._nbio = nbio
        self._addr_record = None  # type: tuple
        self._conn_params = None  # type: pika.connection.Parameters
        self._on_done = None  # will be provided via start()
        # TCP connection timeout
        # pylint: disable=C0301
        self._tcp_timeout_ref = None  # type: pika.adapters.utils.nbio_interface.AbstractTimerReference
        # Overall TCP/[SSL]/AMQP timeout
        self._stack_timeout_ref = None  # type: pika.adapters.utils.nbio_interface.AbstractTimerReference
        # Current task
        self._task_ref = None  # type: pika.adapters.utils.nbio_interface.AbstractIOReference
        self._sock = None  # type: socket.socket
        self._amqp_conn = None  # type: pika.connection.Connection

        self._state = self._STATE_INIT

    def start(self, addr_record, conn_params, on_done):
        """Asynchronously perform a single TCP/[SSL]/AMQP connection attempt.

        :param tuple addr_record: a single resolved address record compatible
            with `socket.getaddrinfo()` format.
        :param pika.connection.Parameters conn_params:
        :param callable on_done: Function to call upon completion of the
            workflow: `on_done(pika.connection.Connection | BaseException)`. If
            exception, it's going to be one of the following:
                `AMQPConnectorSocketConnectError`
                `AMQPConnectorTransportSetupError`
                `AMQPConnectorAMQPHandshakeError`
                `AMQPConnectorAborted`

        """
        if self._state != self._STATE_INIT:
            raise AMQPConnectorWrongState(
                'Already in progress or finished; state={}'.format(self._state))

        self._addr_record = addr_record
        self._conn_params = conn_params
        self._on_done = on_done

        # Create socket and initiate TCP/IP connection
        self._state = self._STATE_TCP
        self._sock = socket.socket(*self._addr_record[:3])
        self._sock.setsockopt(pika.compat.SOL_TCP, socket.TCP_NODELAY, 1)
        pika.tcp_socket_opts.set_sock_opts(self._conn_params.tcp_options,
                                           self._sock)
        self._sock.setblocking(False)

        addr = self._addr_record[4]
        _LOG.info('Pika version %s connecting to %r', __version__, addr)
        self._task_ref = self._nbio.connect_socket(
            self._sock, addr, on_done=self._on_tcp_connection_done)

        # Start socket connection timeout timer
        self._tcp_timeout_ref = None
        if self._conn_params.socket_timeout is not None:
            self._tcp_timeout_ref = self._nbio.call_later(
                self._conn_params.socket_timeout,
                self._on_tcp_connection_timeout)

        # Start overall TCP/[SSL]/AMQP stack connection timeout timer
        self._stack_timeout_ref = None
        if self._conn_params.stack_timeout is not None:
            self._stack_timeout_ref = self._nbio.call_later(
                self._conn_params.stack_timeout, self._on_overall_timeout)

    def abort(self):
        """Abort the workflow asynchronously. The completion callback will be
        called with an instance of AMQPConnectorAborted.

        NOTE: we can't cancel/close synchronously because aborting pika
        Connection and its transport requires an asynchronous operation.

        :raises AMQPConnectorWrongState: If called after completion has been
            reported or the workflow not started yet.
        """
        if self._state == self._STATE_INIT:
            raise AMQPConnectorWrongState('Cannot abort before starting.')

        if self._state == self._STATE_DONE:
            raise AMQPConnectorWrongState('Cannot abort after completion was reported')

        self._state = self._STATE_ABORTING
        self._deactivate()

        _LOG.info(
            'AMQPConnector: beginning client-initiated asynchronous '
            'abort; %r/%s', self._conn_params.host, self._addr_record)

        if self._amqp_conn is None:
            _LOG.debug('AMQPConnector.abort(): no connection, so just '
                       'scheduling completion report via I/O loop.')
            self._nbio.add_callback_threadsafe(
                functools.partial(self._report_completion_and_cleanup,
                                  AMQPConnectorAborted()))
        else:
            if not self._amqp_conn.is_closing:
                # Initiate close of AMQP connection and wait for asynchronous
                # callback from the Connection instance before reporting
                # completion to client
                _LOG.debug('AMQPConnector.abort(): closing Connection.')
                self._amqp_conn.close(
                    320, 'Client-initiated abort of AMQP Connection Workflow.')
            else:
                # It's already closing, must be due to our timeout processing,
                # so we'll just piggy back on the callback it registered
                _LOG.debug('AMQPConnector.abort(): closing of Connection was '
                           'already initiated.')
                assert self._state == self._STATE_TIMEOUT, \
                    ('Connection is closing, but not in TIMEOUT state; state={}'
                     .format(self._state))

    def _close(self):
        """Cancel asynchronous tasks and clean up to assist garbage collection.

        Transition to STATE_DONE.

        """
        self._deactivate()

        if self._sock is not None:
            self._sock.close()
            self._sock = None

        self._conn_factory = None
        self._nbio = None
        self._addr_record = None
        self._on_done = None

        self._state = self._STATE_DONE

    def _deactivate(self):
        """Cancel asynchronous tasks.

        """
        # NOTE: self._amqp_conn requires special handling as it doesn't support
        # synchronous closing. We special-case it elsewhere in the code where
        # needed.
        assert self._amqp_conn is None, \
            '_deactivate called with self._amqp_conn not None; state={}'.format(
                self._state)

        if self._tcp_timeout_ref is not None:
            self._tcp_timeout_ref.cancel()
            self._tcp_timeout_ref = None

        if self._stack_timeout_ref is not None:
            self._stack_timeout_ref.cancel()
            self._stack_timeout_ref = None

        if self._task_ref is not None:
            self._task_ref.cancel()
            self._task_ref = None

    def _report_completion_and_cleanup(self, result):
        """Clean up and invoke client's `on_done` callback.

        :param pika.connection.Connection | BaseException result: value to pass
            to user's `on_done` callback.
        """
        if isinstance(result, BaseException):
            _LOG.error('AMQPConnector - reporting failure: %r', result)
        else:
            _LOG.info('AMQPConnector - reporting success: %r', result)

        on_done = self._on_done
        self._close()

        on_done(result)

    def _on_tcp_connection_timeout(self):
        """Handle TCP connection timeout

        Reports AMQPConnectorSocketConnectError with socket.timeout inside.

        """
        self._tcp_timeout_ref = None

        error = AMQPConnectorSocketConnectError(
            socket.timeout('TCP connection attempt timed out: {!r}/{}'.format(
                self._conn_params.host, self._addr_record)))
        self._report_completion_and_cleanup(error)

    def _on_overall_timeout(self):
        """Handle overall TCP/[SSL]/AMQP connection attempt timeout by reporting
        `Timeout` error to the client.

        Reports AMQPConnectorSocketConnectError if timeout occurred during
            socket TCP connection attempt.
        Reports AMQPConnectorTransportSetupError if timeout occurred during
            tramsport [SSL] setup attempt.
        Reports AMQPConnectorAMQPHandshakeError if timeout occurred during
            AMQP handshake.

        """
        self._stack_timeout_ref = None

        prev_state = self._state
        self._state = self._STATE_TIMEOUT

        if prev_state == self._STATE_AMQP:
            msg = ('Timeout while setting up AMQP to {!r}/{}; ssl={}'.format(
                self._conn_params.host, self._addr_record,
                bool(self._conn_params.ssl_options)))
            _LOG.error(msg)
            # Initiate close of AMQP connection and wait for asynchronous
            # callback from the Connection instance before reporting completion
            # to client
            assert not self._amqp_conn.is_open, \
                'Unexpected open state of {!r}'.format(self._amqp_conn)
            if not self._amqp_conn.is_closing:
                self._amqp_conn.close(320, msg)
            return

        if prev_state == self._STATE_TCP:
            error = AMQPConnectorSocketConnectError(
                AMQPConnectorStackTimeout(
                    'Timeout while connecting socket to {!r}/{}'.format(
                        self._conn_params.host, self._addr_record)))
        else:
            assert prev_state == self._STATE_TRANSPORT
            error = AMQPConnectorTransportSetupError(
                AMQPConnectorStackTimeout(
                    'Timeout while setting up transport to {!r}/{}; ssl={}'.
                    format(self._conn_params.host, self._addr_record,
                           bool(self._conn_params.ssl_options))))

        self._report_completion_and_cleanup(error)

    def _on_tcp_connection_done(self, exc):
        """Handle completion of asynchronous socket connection attempt.

        Reports AMQPConnectorSocketConnectError if TCP socket connection
            failed.

        :param None|BaseException exc: None on success; exception object on
            failure

        """
        self._task_ref = None
        if self._tcp_timeout_ref is not None:
            self._tcp_timeout_ref.cancel()
            self._tcp_timeout_ref = None

        if exc is not None:
            _LOG.error('TCP Connection attempt failed: %r; dest=%r', exc,
                       self._addr_record)
            self._report_completion_and_cleanup(
                AMQPConnectorSocketConnectError(exc))
            return

        # We succeeded in making a TCP/IP connection to the server
        _LOG.debug('TCP connection to broker established: %r.', self._sock)

        # Now set up the transport
        self._state = self._STATE_TRANSPORT

        ssl_context = server_hostname = None
        if self._conn_params.ssl_options is not None:
            ssl_context = self._conn_params.ssl_options.context
            server_hostname = self._conn_params.ssl_options.server_hostname
            if server_hostname is None:
                server_hostname = self._conn_params.host

        self._task_ref = self._nbio.create_streaming_connection(
            protocol_factory=functools.partial(self._conn_factory,
                                               self._conn_params),
            sock=self._sock,
            ssl_context=ssl_context,
            server_hostname=server_hostname,
            on_done=self._on_transport_establishment_done)

        self._sock = None  # create_streaming_connection() takes ownership

    def _on_transport_establishment_done(self, result):
        """Handle asynchronous completion of
        `AbstractIOServices.create_streaming_connection()`

        Reports AMQPConnectorTransportSetupError if transport ([SSL]) setup
            failed.

        :param sequence|BaseException result: On success, a two-tuple
            (transport, protocol); on failure, exception instance.

        """
        self._task_ref = None

        if isinstance(result, BaseException):
            _LOG.error(
                'Attempt to create the streaming transport failed: %r; '
                '%r/%s; ssl=%s', result, self._conn_params.host,
                self._addr_record, bool(self._conn_params.ssl_options))
            self._report_completion_and_cleanup(
                AMQPConnectorTransportSetupError(result))
            return

        # We succeeded in setting up the streaming transport!
        # result is a two-tuple (transport, protocol)
        _LOG.info('Streaming transport linked up: %r.', result)
        _transport, self._amqp_conn = result

        # AMQP handshake is in progress - initiated during transport link-up
        self._state = self._STATE_AMQP
        # We explicitly remove default handler because it raises an exception.
        self._amqp_conn.add_on_open_error_callback(
            self._on_amqp_handshake_done, remove_default=True)
        self._amqp_conn.add_on_open_callback(self._on_amqp_handshake_done)

    def _on_amqp_handshake_done(self, connection, error=None):
        """Handle completion of AMQP connection handshake attempt.

        NOTE: we handle two types of callbacks - success with just connection
        arg as well as the open-error callback with connection and error

        Reports AMQPConnectorAMQPHandshakeError if AMQP handshake failed.

        :param pika.connection.Connection connection:
        :param BaseException | None error: None on success, otherwise
            failure

        """
        _LOG.debug(
            'AMQPConnector: AMQP handshake attempt completed; state=%s; '
            'error=%r; %r/%s', self._state, error, self._conn_params.host,
            self._addr_record)

        # Don't need it any more; and _deactivate() checks that it's None
        self._amqp_conn = None

        if self._state == self._STATE_ABORTING:
            # Client-initiated abort takes precedence over timeout
            result = AMQPConnectorAborted()
        elif self._state == self._STATE_TIMEOUT:
            result = AMQPConnectorAMQPHandshakeError(
                AMQPConnectorStackTimeout(
                    'Timeout during AMQP handshake{!r}/{}; ssl={}'.format(
                        self._conn_params.host, self._addr_record,
                        bool(self._conn_params.ssl_options))))
        elif self._state == self._STATE_AMQP:
            if error is None:
                _LOG.debug(
                    'AMQPConnector: AMQP connection established for %r/%s: %r',
                    self._conn_params.host, self._addr_record, connection)
                result = connection
            else:
                _LOG.debug(
                    'AMQPConnector: AMQP connection handshake failed for '
                    '%r/%s: %r', self._conn_params.host, self._addr_record,
                    error)
                result = AMQPConnectorAMQPHandshakeError(error)
        else:
            # We timed out or aborted and initiated closing of the connection,
            # but this callback snuck in
            _LOG.debug(
                'AMQPConnector: Ignoring AMQP handshake completion '
                'notification due to wrong state=%s; error=%r; conn=%r',
                self._state, error, connection)
            return

        self._report_completion_and_cleanup(result)


class AbstractAMQPConnectionWorkflow(pika.compat.AbstractBase):
    """Interface for implementing a custom TCP/[SSL]/AMQP connection workflow.

    """

    def start(self, connection_configs, connector_factory, native_loop,
              on_done):
        """Asynchronously perform the workflow until success or all retries
        are exhausted. Called by the adapter.

        :param sequence connection_configs: A sequence of one or more
            `pika.connection.Parameters`-based objects. Will attempt to connect
            using each config in the given order.
        :param callable connector_factory: call it without args to obtain a new
            instance of `AMQPConnector` for each connection attempt.
            See `AMQPConnector` for details.
        :param native_loop: Native I/O loop passed by app to the adapter or
            obtained by the adapter by default.
        :param callable on_done: Function to call upon completion of the
            workflow:
            `on_done(pika.connection.Connection |
                     AMQPConnectionWorkflowFailed |
                     AMQPConnectionWorkflowAborted)`.
            `Connection`-based adapter on success,
            `AMQPConnectionWorkflowFailed` on failure,
            `AMQPConnectionWorkflowAborted` if workflow was aborted.

        :raises AMQPConnectionWorkflowWrongState: If called in wrong state, such
            as after starting the workflow.
        """
        raise NotImplementedError

    def abort(self):
        """Abort the workflow asynchronously. The completion callback will be
        called with an instance of AMQPConnectionWorkflowAborted.

        NOTE: we can't cancel/close synchronously because aborting pika
        Connection and its transport requires an asynchronous operation.

        :raises AMQPConnectionWorkflowWrongState: If called in wrong state, such
            as before starting or after completion has been reported.
        """
        raise NotImplementedError


class AMQPConnectionWorkflow(AbstractAMQPConnectionWorkflow):
    """Implements Pika's default workflow for performing multiple TCP/[SSL]/AMQP
    connection attempts with timeouts and retries until one succeeds or all
    attempts fail.

    The workflow:
        while not success and retries remain:
            1. For each given config (pika.connection.Parameters object):
                A. Perform DNS resolution of the config's host.
                B. Attempt to establish TCP/[SSL]/AMQP for each resolved address
                   until one succeeds, in which case we're done.
            2. If all configs failed but retries remain, resume from beginning
               after the given retry pause. NOTE: failure of DNS resolution
               is equivalent to one cycle and will be retried after the pause
               if retries remain.

    """

    _SOCK_TYPE = socket.SOCK_STREAM
    _IPPROTO = socket.IPPROTO_TCP

    _STATE_INIT = 0
    _STATE_ACTIVE = 1
    _STATE_ABORTING = 2
    _STATE_DONE = 3

    def __init__(self, _until_first_amqp_attempt=False):
        """
        :param int | float retry_pause: Non-negative number of seconds to wait
            before retrying the config sequence. Meaningful only if retries is
            greater than 0. Defaults to 2 seconds.
        :param bool _until_first_amqp_attempt: INTERNAL USE ONLY; ends workflow
            after first AMQP handshake attempt, regardless of outcome (success
            or failure). The automatic connection logic in
            `pika.connection.Connection` enables this because it's not
            designed/tested to reset all state properly to handle more than one
            AMQP handshake attempt.

        TODO: Do we need getaddrinfo timeout?
        TODO: Would it be useful to implement exponential back-off?

        """
        self._attempts_remaining = None  # supplied by start()
        self._retry_pause = None  # supplied by start()
        self._until_first_amqp_attempt = _until_first_amqp_attempt

        # Provided by set_io_services()
        # pylint: disable=C0301
        self._nbio = None  # type: pika.adapters.utils.nbio_interface.AbstractIOServices

        # Current index within `_connection_configs`; initialized when
        # starting a new connection sequence.
        self._current_config_index = None

        self._connection_configs = None  # supplied by start()
        self._connector_factory = None  # supplied by start()
        self._on_done = None  # supplied by start()

        self._connector = None  # type: AMQPConnector

        self._task_ref = None  # current cancelable asynchronous task or timer
        self._addrinfo_iter = None

        # Exceptions from all failed connection attempts in this workflow
        self._connection_errors = []

        self._state = self._STATE_INIT

    def set_io_services(self, nbio):
        """Called by the conneciton adapter only on pika's
        `AMQPConnectionWorkflow` instance to provide it the adapter-specific
        `AbstractIOServices` object before calling the `start()` method.

        NOTE: Custom workflow implementations should use the native I/O loop
        directly because `AbstractIOServices` is private to Pika
        implementation and its interface may change without notice.

        :param pika.adapters.utils.nbio_interface.AbstractIOServices nbio:

        """
        self._nbio = nbio

    def start(
            self,
            connection_configs,
            connector_factory,
            native_loop,  # pylint: disable=W0613
            on_done):
        """Override `AbstractAMQPConnectionWorkflow.start()`.

        NOTE: This implementation uses `connection_attempts` and `retry_delay`
        values from the last element of the given `connection_configs` sequence
        as the overall number of connection attempts of the entire
        `connection_configs` sequence and pause between each sequence.

        """
        if self._state != self._STATE_INIT:
            raise AMQPConnectorWrongState(
                'Already in progress or finished; state={}'.format(self._state))

        try:
            iter(connection_configs)
        except Exception as error:
            raise TypeError(
                'connection_configs does not support iteration: {!r}'.format(
                    error))
        if not connection_configs:
            raise ValueError(
                'connection_configs is empty: {!r}.'.format(connection_configs))

        self._connection_configs = connection_configs
        self._connector_factory = connector_factory
        self._on_done = on_done

        self._attempts_remaining = connection_configs[-1].connection_attempts
        self._retry_pause = connection_configs[-1].retry_delay

        self._state = self._STATE_ACTIVE

        _LOG.debug('Starting AMQP Connection workflow asynchronously.')

        # Begin from our own I/O loop context to avoid calling back into client
        # from client's call here
        self._task_ref = self._nbio.call_later(
            0, functools.partial(self._start_new_cycle_async, first=True))

    def abort(self):
        """Override `AbstractAMQPConnectionWorkflow.abort()`.

        """
        if self._state == self._STATE_INIT:
            raise AMQPConnectorWrongState('Cannot abort before starting.')
        elif self._state == self._STATE_DONE:
            raise AMQPConnectorWrongState(
                'Cannot abort after completion was reported')

        self._state = self._STATE_ABORTING
        self._deactivate()

        _LOG.info('AMQPConnectionWorkflow: beginning client-initiated '
                  'asynchronous abort.')

        if self._connector is None:
            _LOG.debug('AMQPConnectionWorkflow.abort(): no connector, so just '
                       'scheduling completion report via I/O loop.')
            self._nbio.add_callback_threadsafe(
                functools.partial(self._report_completion_and_cleanup,
                                  AMQPConnectionWorkflowAborted()))
        else:
            _LOG.debug('AMQPConnectionWorkflow.abort(): requesting '
                       'connector.abort().')
            self._connector.abort()

    def _close(self):
        """Cancel asynchronous tasks and clean up to assist garbage collection.

        Transition to _STATE_DONE.

        """
        self._deactivate()

        self._connection_configs = None
        self._nbio = None
        self._connector_factory = None
        self._on_done = None
        self._connector = None
        self._addrinfo_iter = None
        self._connection_errors = None

        self._state = self._STATE_DONE

    def _deactivate(self):
        """Cancel asynchronous tasks.

        """
        if self._task_ref is not None:
            self._task_ref.cancel()
            self._task_ref = None

    def _report_completion_and_cleanup(self, result):
        """Clean up and invoke client's `on_done` callback.

        :param pika.connection.Connection | AMQPConnectionWorkflowFailed result:
            value to pass to user's `on_done` callback.
        """
        if isinstance(result, BaseException):
            _LOG.error('AMQPConnectionWorkflow - reporting failure: %r', result)
        else:
            _LOG.info('AMQPConnectionWorkflow - reporting success: %r', result)

        on_done = self._on_done
        self._close()

        on_done(result)

    def _start_new_cycle_async(self, first):
        """Start a new workflow cycle (if any more attempts are left) beginning
        with the first Parameters object in self._connection_configs. If out of
        attempts, report `AMQPConnectionWorkflowFailed`.

        :param bool first: if True, don't delay; otherwise delay next attempt by
            `self._retry_pause` seconds.
        """
        self._task_ref = None

        assert self._attempts_remaining >= 0, self._attempts_remaining

        if self._attempts_remaining <= 0:
            error = AMQPConnectionWorkflowFailed(self._connection_errors)
            _LOG.error('AMQP connection workflow failed: %r.', error)
            self._report_completion_and_cleanup(error)
            return

        self._attempts_remaining -= 1
        _LOG.debug(
            'Beginning a new AMQP connection workflow cycle; attempts '
            'remaining after this: %s', self._attempts_remaining)

        self._current_config_index = None

        self._task_ref = self._nbio.call_later(
            0 if first else self._retry_pause, self._try_next_config_async)

    def _try_next_config_async(self):
        """Attempt to connect using the next Parameters config. If there are no
        more configs, start a new cycle.

        """
        self._task_ref = None

        if self._current_config_index is None:
            self._current_config_index = 0
        else:
            self._current_config_index += 1

        if self._current_config_index >= len(self._connection_configs):
            _LOG.debug('_try_next_config_async: starting a new cycle.')
            self._start_new_cycle_async(first=False)
            return

        params = self._connection_configs[self._current_config_index]

        _LOG.debug('_try_next_config_async: %r:%s', params.host, params.port)

        # Begin with host address resolution
        assert self._task_ref is None
        self._task_ref = self._nbio.getaddrinfo(
            host=params.host,
            port=params.port,
            socktype=self._SOCK_TYPE,
            proto=self._IPPROTO,
            on_done=self._on_getaddrinfo_async_done)

    def _on_getaddrinfo_async_done(self, addrinfos_or_exc):
        """Handles completion callback from asynchronous `getaddrinfo()`.

        :param list | BaseException addrinfos_or_exc: resolved address records
            returned by `getaddrinfo()` or an exception object from failure.
        """
        self._task_ref = None

        if isinstance(addrinfos_or_exc, BaseException):
            _LOG.error('getaddrinfo failed: %r.', addrinfos_or_exc)
            self._connection_errors.append(addrinfos_or_exc)
            self._start_new_cycle_async(first=False)
            return

        _LOG.debug('getaddrinfo returned %s records', len(addrinfos_or_exc))
        self._addrinfo_iter = iter(addrinfos_or_exc)

        self._try_next_resolved_address()

    def _try_next_resolved_address(self):
        """Try connecting using next resolved address. If there aren't any left,
        continue with next Parameters config.

        """
        try:
            addr_record = next(self._addrinfo_iter)
        except StopIteration:
            _LOG.debug(
                '_try_next_resolved_address: continuing with next config.')
            self._try_next_config_async()
            return

        _LOG.debug('Attempting to connect using address record %r', addr_record)

        self._connector = self._connector_factory()  # type: AMQPConnector

        self._connector.start(
            addr_record=addr_record,
            conn_params=self._connection_configs[self._current_config_index],
            on_done=self._on_connector_done)

    def _on_connector_done(self, conn_or_exc):
        """Handle completion of connection attempt by `AMQPConnector`.

        :param pika.connection.Connection | BaseException conn_or_exc: See
            `AMQPConnector.start()` for exception details.

        """
        self._connector = None
        _LOG.debug('Connection attempt completed with %r', conn_or_exc)

        if isinstance(conn_or_exc, BaseException):
            self._connection_errors.append(conn_or_exc)

            if isinstance(conn_or_exc, AMQPConnectorAborted):
                assert self._state == self._STATE_ABORTING, \
                    'Expected _STATE_ABORTING, but got {!r}'.format(self._state)

                self._report_completion_and_cleanup(
                    AMQPConnectionWorkflowAborted())
            elif (self._until_first_amqp_attempt and
                  isinstance(conn_or_exc, AMQPConnectorAMQPHandshakeError)):
                _LOG.debug('Ending AMQP connection workflow after first failed '
                           'AMQP handshake due to _until_first_amqp_attempt.')
                if isinstance(conn_or_exc.exception,
                              pika.exceptions.ConnectionOpenAborted):
                    error = AMQPConnectionWorkflowAborted
                else:
                    error = AMQPConnectionWorkflowFailed(
                        self._connection_errors)

                self._report_completion_and_cleanup(error)
            else:
                self._try_next_resolved_address()
        else:
            # Success!
            self._report_completion_and_cleanup(conn_or_exc)
