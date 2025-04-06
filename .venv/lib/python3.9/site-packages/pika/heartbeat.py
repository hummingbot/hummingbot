"""Handle AMQP Heartbeats"""
import logging

import pika.exceptions
from pika import frame

LOGGER = logging.getLogger(__name__)


class HeartbeatChecker(object):
    """Sends heartbeats to the broker. The provided timeout is used to
    determine if the connection is stale - no received heartbeats or
    other activity will close the connection. See the parameter list for more
    details.

    """
    _STALE_CONNECTION = "No activity or too many missed heartbeats in the last %i seconds"

    def __init__(self, connection, timeout):
        """Create an object that will check for activity on the provided
        connection as well as receive heartbeat frames from the broker. The
        timeout parameter defines a window within which this activity must
        happen. If not, the connection is considered dead and closed.

        The value passed for timeout is also used to calculate an interval
        at which a heartbeat frame is sent to the broker. The interval is
        equal to the timeout value divided by two.

        :param pika.connection.Connection: Connection object
        :param int timeout: Connection idle timeout. If no activity occurs on the
                            connection nor heartbeat frames received during the
                            timeout window the connection will be closed. The
                            interval used to send heartbeats is calculated from
                            this value by dividing it by two.

        """
        if timeout < 1:
            raise ValueError('timeout must >= 0, but got %r' % (timeout,))

        self._connection = connection

        # Note: see the following documents:
        # https://www.rabbitmq.com/heartbeats.html#heartbeats-timeout
        # https://github.com/pika/pika/pull/1072
        # https://groups.google.com/d/topic/rabbitmq-users/Fmfeqe5ocTY/discussion
        # There is a certain amount of confusion around how client developers
        # interpret the spec. The spec talks about 2 missed heartbeats as a
        # *timeout*, plus that any activity on the connection counts for a
        # heartbeat. This is to avoid edge cases and not to depend on network
        # latency.
        self._timeout = timeout

        self._send_interval = float(timeout) / 2

        # Note: Pika will calculate the heartbeat / connectivity check interval
        # by adding 5 seconds to the negotiated timeout to leave a bit of room
        # for broker heartbeats that may be right at the edge of the timeout
        # window. This is different behavior from the RabbitMQ Java client and
        # the spec that suggests a check interval equivalent to two times the
        # heartbeat timeout value. But, one advantage of adding a small amount
        # is that bad connections will be detected faster.
        # https://github.com/pika/pika/pull/1072#issuecomment-397850795
        # https://github.com/rabbitmq/rabbitmq-java-client/blob/b55bd20a1a236fc2d1ea9369b579770fa0237615/src/main/java/com/rabbitmq/client/impl/AMQConnection.java#L773-L780
        # https://github.com/ruby-amqp/bunny/blob/3259f3af2e659a49c38c2470aa565c8fb825213c/lib/bunny/session.rb#L1187-L1192
        self._check_interval = timeout + 5

        LOGGER.debug('timeout: %f send_interval: %f check_interval: %f',
                     self._timeout, self._send_interval, self._check_interval)

        # Initialize counters
        self._bytes_received = 0
        self._bytes_sent = 0
        self._heartbeat_frames_received = 0
        self._heartbeat_frames_sent = 0
        self._idle_byte_intervals = 0

        self._send_timer = None
        self._check_timer = None
        self._start_send_timer()
        self._start_check_timer()

    @property
    def bytes_received_on_connection(self):
        """Return the number of bytes received by the connection bytes object.

        :rtype int

        """
        return self._connection.bytes_received

    @property
    def connection_is_idle(self):
        """Returns true if the byte count hasn't changed in enough intervals
        to trip the max idle threshold.

        """
        return self._idle_byte_intervals > 0

    def received(self):
        """Called when a heartbeat is received"""
        LOGGER.debug('Received heartbeat frame')
        self._heartbeat_frames_received += 1

    def _send_heartbeat(self):
        """Invoked by a timer to send a heartbeat when we need to.

        """
        LOGGER.debug('Sending heartbeat frame')
        self._send_heartbeat_frame()
        self._start_send_timer()

    def _check_heartbeat(self):
        """Invoked by a timer to check for broker heartbeats. Checks to see
        if we've missed any heartbeats and disconnect our connection if it's
        been idle too long.

        """
        if self._has_received_data:
            self._idle_byte_intervals = 0
        else:
            # Connection has not received any data, increment the counter
            self._idle_byte_intervals += 1

        LOGGER.debug(
            'Received %i heartbeat frames, sent %i, '
            'idle intervals %i', self._heartbeat_frames_received,
            self._heartbeat_frames_sent, self._idle_byte_intervals)

        if self.connection_is_idle:
            self._close_connection()
            return

        self._start_check_timer()

    def stop(self):
        """Stop the heartbeat checker"""
        if self._send_timer:
            LOGGER.debug('Removing timer for next heartbeat send interval')
            self._connection._adapter_remove_timeout(self._send_timer)  # pylint: disable=W0212
            self._send_timer = None
        if self._check_timer:
            LOGGER.debug('Removing timer for next heartbeat check interval')
            self._connection._adapter_remove_timeout(self._check_timer)  # pylint: disable=W0212
            self._check_timer = None

    def _close_connection(self):
        """Close the connection with the AMQP Connection-Forced value."""
        LOGGER.info('Connection is idle, %i stale byte intervals',
                    self._idle_byte_intervals)
        text = HeartbeatChecker._STALE_CONNECTION % self._timeout

        # Abort the stream connection. There is no point trying to gracefully
        # close the AMQP connection since lack of heartbeat suggests that the
        # stream is dead.
        self._connection._terminate_stream(  # pylint: disable=W0212
            pika.exceptions.AMQPHeartbeatTimeout(text))

    @property
    def _has_received_data(self):
        """Returns True if the connection has received data.

        :rtype: bool

        """
        return self._bytes_received != self.bytes_received_on_connection

    @staticmethod
    def _new_heartbeat_frame():
        """Return a new heartbeat frame.

        :rtype pika.frame.Heartbeat

        """
        return frame.Heartbeat()

    def _send_heartbeat_frame(self):
        """Send a heartbeat frame on the connection.

        """
        LOGGER.debug('Sending heartbeat frame')
        self._connection._send_frame(  # pylint: disable=W0212
            self._new_heartbeat_frame())
        self._heartbeat_frames_sent += 1

    def _start_send_timer(self):
        """Start a new heartbeat send timer."""
        self._send_timer = self._connection._adapter_call_later(  # pylint: disable=W0212
            self._send_interval,
            self._send_heartbeat)

    def _start_check_timer(self):
        """Start a new heartbeat check timer."""
        # Note: update counters now to get current values
        # at the start of the timeout window. Values will be
        # checked against the connection's byte count at the
        # end of the window
        self._update_counters()

        self._check_timer = self._connection._adapter_call_later(  # pylint: disable=W0212
            self._check_interval,
            self._check_heartbeat)

    def _update_counters(self):
        """Update the internal counters for bytes sent and received and the
        number of frames received

        """
        self._bytes_sent = self._connection.bytes_sent
        self._bytes_received = self._connection.bytes_received
