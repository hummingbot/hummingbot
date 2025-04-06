"""Pika specific exceptions"""
# pylint: disable=C0111,E1136


class AMQPError(Exception):

    def __repr__(self):
        return '%s: An unspecified AMQP error has occurred; %s' % (
            self.__class__.__name__, self.args)


class AMQPConnectionError(AMQPError):

    def __repr__(self):
        if len(self.args) == 2:
            return '{}: ({}) {}'.format(self.__class__.__name__, self.args[0],
                                        self.args[1])
        else:
            return '{}: {}'.format(self.__class__.__name__, self.args)


class ConnectionOpenAborted(AMQPConnectionError):
    """Client closed connection while opening."""


class StreamLostError(AMQPConnectionError):
    """Stream (TCP) connection lost."""


class IncompatibleProtocolError(AMQPConnectionError):

    def __repr__(self):
        return (
            '%s: The protocol returned by the server is not supported: %s' % (
                self.__class__.__name__,
                self.args,
            ))


class AuthenticationError(AMQPConnectionError):

    def __repr__(self):
        return ('%s: Server and client could not negotiate use of the %s '
                'authentication mechanism' % (self.__class__.__name__,
                                              self.args[0]))


class ProbableAuthenticationError(AMQPConnectionError):

    def __repr__(self):
        return (
            '%s: Client was disconnected at a connection stage indicating a '
            'probable authentication error: %s' % (
                self.__class__.__name__,
                self.args,
            ))


class ProbableAccessDeniedError(AMQPConnectionError):

    def __repr__(self):
        return (
            '%s: Client was disconnected at a connection stage indicating a '
            'probable denial of access to the specified virtual host: %s' % (
                self.__class__.__name__,
                self.args,
            ))


class NoFreeChannels(AMQPConnectionError):

    def __repr__(self):
        return '%s: The connection has run out of free channels' % (
            self.__class__.__name__)


class ConnectionWrongStateError(AMQPConnectionError):
    """Connection is in wrong state for the requested operation."""

    def __repr__(self):
        if self.args:
            return super(ConnectionWrongStateError, self).__repr__()
        else:
            return ('%s: The connection is in wrong state for the requested '
                    'operation.' % self.__class__.__name__)


class ConnectionClosed(AMQPConnectionError):

    def __init__(self, reply_code, reply_text):
        """

        :param int reply_code: reply-code that was used in user's or broker's
            `Connection.Close` method. NEW in v1.0.0
        :param str reply_text: reply-text that was used in user's or broker's
            `Connection.Close` method. Human-readable string corresponding to
            `reply_code`. NEW in v1.0.0
        """
        super(ConnectionClosed, self).__init__(int(reply_code), str(reply_text))

    def __repr__(self):
        return '{}: ({}) {!r}'.format(self.__class__.__name__, self.reply_code,
                                      self.reply_text)

    @property
    def reply_code(self):
        """ NEW in v1.0.0
        :rtype: int

        """
        return self.args[0]

    @property
    def reply_text(self):
        """ NEW in v1.0.0
        :rtype: str

        """
        return self.args[1]


class ConnectionClosedByBroker(ConnectionClosed):
    """Connection.Close from broker."""


class ConnectionClosedByClient(ConnectionClosed):
    """Connection was closed at request of Pika client."""


class ConnectionBlockedTimeout(AMQPConnectionError):
    """RabbitMQ-specific: timed out waiting for connection.unblocked."""


class AMQPHeartbeatTimeout(AMQPConnectionError):
    """Connection was dropped as result of heartbeat timeout."""


class AMQPChannelError(AMQPError):

    def __repr__(self):
        return '{}: {!r}'.format(self.__class__.__name__, self.args)


class ChannelWrongStateError(AMQPChannelError):
    """Channel is in wrong state for the requested operation."""


class ChannelClosed(AMQPChannelError):
    """The channel closed by client or by broker

    """

    def __init__(self, reply_code, reply_text):
        """

        :param int reply_code: reply-code that was used in user's or broker's
            `Channel.Close` method. One of the AMQP-defined Channel Errors.
            NEW in v1.0.0
        :param str reply_text: reply-text that was used in user's or broker's
            `Channel.Close` method. Human-readable string corresponding to
            `reply_code`;
            NEW in v1.0.0

        """
        super(ChannelClosed, self).__init__(int(reply_code), str(reply_text))

    def __repr__(self):
        return '{}: ({}) {!r}'.format(self.__class__.__name__, self.reply_code,
                                      self.reply_text)

    @property
    def reply_code(self):
        """ NEW in v1.0.0
        :rtype: int

        """
        return self.args[0]

    @property
    def reply_text(self):
        """ NEW in v1.0.0
        :rtype: str

        """
        return self.args[1]


class ChannelClosedByBroker(ChannelClosed):
    """`Channel.Close` from broker; may be passed as reason to channel's
    on-closed callback of non-blocking connection adapters or raised by
    `BlockingConnection`.

    NEW in v1.0.0
    """


class ChannelClosedByClient(ChannelClosed):
    """Channel closed by client upon receipt of `Channel.CloseOk`; may be passed
    as reason to channel's on-closed callback of non-blocking connection
    adapters, but not raised by `BlockingConnection`.

    NEW in v1.0.0
    """


class DuplicateConsumerTag(AMQPChannelError):

    def __repr__(self):
        return ('%s: The consumer tag specified already exists for this '
                'channel: %s' % (self.__class__.__name__, self.args[0]))


class ConsumerCancelled(AMQPChannelError):

    def __repr__(self):
        return '%s: Server cancelled consumer' % self.__class__.__name__


class UnroutableError(AMQPChannelError):
    """Exception containing one or more unroutable messages returned by broker
    via Basic.Return.

    Used by BlockingChannel.

    In publisher-acknowledgements mode, this is raised upon receipt of Basic.Ack
    from broker; in the event of Basic.Nack from broker, `NackError` is raised
    instead
    """

    def __init__(self, messages):
        """
        :param sequence(blocking_connection.ReturnedMessage) messages: Sequence
            of returned unroutable messages
        """
        super(UnroutableError, self).__init__(
            "%s unroutable message(s) returned" % (len(messages)))

        self.messages = messages

    def __repr__(self):
        return '%s: %i unroutable messages returned by broker' % (
            self.__class__.__name__, len(self.messages))


class NackError(AMQPChannelError):
    """This exception is raised when a message published in
    publisher-acknowledgements mode is Nack'ed by the broker.

    Used by BlockingChannel.
    """

    def __init__(self, messages):
        """
        :param sequence(blocking_connection.ReturnedMessage) messages: Sequence
            of returned unroutable messages
        """
        super(NackError,
              self).__init__("%s message(s) NACKed" % (len(messages)))

        self.messages = messages

    def __repr__(self):
        return '%s: %i unroutable messages returned by broker' % (
            self.__class__.__name__, len(self.messages))


class InvalidChannelNumber(AMQPError):

    def __repr__(self):
        return '%s: An invalid channel number has been specified: %s' % (
            self.__class__.__name__, self.args[0])


class ProtocolSyntaxError(AMQPError):

    def __repr__(self):
        return '%s: An unspecified protocol syntax error occurred' % (
            self.__class__.__name__)


class UnexpectedFrameError(ProtocolSyntaxError):

    def __repr__(self):
        return '%s: Received a frame out of sequence: %r' % (
            self.__class__.__name__, self.args[0])


class ProtocolVersionMismatch(ProtocolSyntaxError):

    def __repr__(self):
        return '%s: Protocol versions did not match: %r vs %r' % (
            self.__class__.__name__, self.args[0], self.args[1])


class BodyTooLongError(ProtocolSyntaxError):

    def __repr__(self):
        return ('%s: Received too many bytes for a message delivery: '
                'Received %i, expected %i' % (self.__class__.__name__,
                                              self.args[0], self.args[1]))


class InvalidFrameError(ProtocolSyntaxError):

    def __repr__(self):
        return '%s: Invalid frame received: %r' % (self.__class__.__name__,
                                                   self.args[0])


class InvalidFieldTypeException(ProtocolSyntaxError):

    def __repr__(self):
        return '%s: Unsupported field kind %s' % (self.__class__.__name__,
                                                  self.args[0])


class UnsupportedAMQPFieldException(ProtocolSyntaxError):

    def __repr__(self):
        return '%s: Unsupported field kind %s' % (self.__class__.__name__,
                                                  type(self.args[1]))


class MethodNotImplemented(AMQPError):
    pass


class ChannelError(Exception):

    def __repr__(self):
        return '%s: An unspecified error occurred with the Channel' % (
            self.__class__.__name__)


class ReentrancyError(Exception):
    """The requested operation would result in unsupported recursion or
    reentrancy.

    Used by BlockingConnection/BlockingChannel

    """


class ShortStringTooLong(AMQPError):

    def __repr__(self):
        return ('%s: AMQP Short String can contain up to 255 bytes: '
                '%.300s' % (self.__class__.__name__, self.args[0]))


class DuplicateGetOkCallback(ChannelError):

    def __repr__(self):
        return ('%s: basic_get can only be called again after the callback for '
                'the previous basic_get is executed' % self.__class__.__name__)
