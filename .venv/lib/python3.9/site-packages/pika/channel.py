"""The Channel class provides a wrapper for interacting with RabbitMQ
implementing the methods and behaviors for an AMQP Channel.

"""
# disable too-many-lines
# pylint: disable=C0302

import collections
import logging
import uuid
from enum import Enum

import pika.frame as frame
import pika.exceptions as exceptions
import pika.spec as spec
import pika.validators as validators
from pika.compat import unicode_type, dictkeys, is_integer
from pika.exchange_type import ExchangeType

LOGGER = logging.getLogger(__name__)

MAX_CHANNELS = 65535  # per AMQP 0.9.1 spec.


class Channel(object):
    """A Channel is the primary communication method for interacting with
    RabbitMQ. It is recommended that you do not directly invoke the creation of
    a channel object in your application code but rather construct a channel by
    calling the active connection's channel() method.

    """

    # Disable pylint messages concerning "method could be a function"
    # pylint: disable=R0201

    CLOSED = 0
    OPENING = 1
    OPEN = 2
    CLOSING = 3  # client-initiated close in progress

    _STATE_NAMES = {
        CLOSED: 'CLOSED',
        OPENING: 'OPENING',
        OPEN: 'OPEN',
        CLOSING: 'CLOSING'
    }

    _ON_CHANNEL_CLEANUP_CB_KEY = '_on_channel_cleanup'

    def __init__(self, connection, channel_number, on_open_callback):
        """Create a new instance of the Channel

        :param pika.connection.Connection connection: The connection
        :param int channel_number: The channel number for this instance
        :param callable on_open_callback: The callback to call on channel open.
            The callback will be invoked with the `Channel` instance as its only
            argument.

        """
        if not isinstance(channel_number, int):
            raise exceptions.InvalidChannelNumber(channel_number)

        validators.rpc_completion_callback(on_open_callback)

        self.channel_number = channel_number
        self.callbacks = connection.callbacks
        self.connection = connection

        # Initially, flow is assumed to be active
        self.flow_active = True

        self._content_assembler = ContentFrameAssembler()

        self._blocked = collections.deque(list())
        self._blocking = None
        self._has_on_flow_callback = False
        self._cancelled = set()
        self._consumers = dict()
        self._consumers_with_noack = set()
        self._on_flowok_callback = None
        self._on_getok_callback = None
        self._on_openok_callback = on_open_callback
        self._state = self.CLOSED

        # We save the closing reason exception to be passed to on-channel-close
        # callback at closing of the channel. Exception representing the closing
        # reason; ChannelClosedByClient or ChannelClosedByBroker on controlled
        # close; otherwise another exception describing the reason for failure
        # (most likely connection failure).
        self._closing_reason = None  # type: None | Exception

        # opaque cookie value set by wrapper layer (e.g., BlockingConnection)
        # via _set_cookie
        self._cookie = None

    def __int__(self):
        """Return the channel object as its channel number

        :rtype: int

        """
        return self.channel_number

    def __repr__(self):
        return '<%s number=%s %s conn=%r>' % (
            self.__class__.__name__, self.channel_number,
            self._STATE_NAMES[self._state], self.connection)

    def add_callback(self, callback, replies, one_shot=True):
        """Pass in a callback handler and a list replies from the
        RabbitMQ broker which you'd like the callback notified of. Callbacks
        should allow for the frame parameter to be passed in.

        :param callable callback: The callback to call
        :param list replies: The replies to get a callback for
        :param bool one_shot: Only handle the first type callback

        """
        for reply in replies:
            self.callbacks.add(self.channel_number, reply, callback, one_shot)

    def add_on_cancel_callback(self, callback):
        """Pass a callback function that will be called when the basic_cancel
        is sent by the server. The callback function should receive a frame
        parameter.

        :param callable callback: The callback to call on Basic.Cancel from
            broker

        """
        self.callbacks.add(self.channel_number, spec.Basic.Cancel, callback,
                           False)

    def add_on_close_callback(self, callback):
        """Pass a callback function that will be called when the channel is
        closed. The callback function will receive the channel and an exception
        describing why the channel was closed.

        If the channel is closed by broker via Channel.Close, the callback will
        receive `ChannelClosedByBroker` as the reason.

        If graceful user-initiated channel closing completes successfully (
        either directly of indirectly by closing a connection containing the
        channel) and closing concludes gracefully without Channel.Close from the
        broker and without loss of connection, the callback will receive
        `ChannelClosedByClient` exception as reason.

        If channel was closed due to loss of connection, the callback will
        receive another exception type describing the failure.

        :param callable callback: The callback, having the signature:
            callback(Channel, Exception reason)

        """
        self.callbacks.add(self.channel_number, '_on_channel_close', callback,
                           False, self)

    def add_on_flow_callback(self, callback):
        """Pass a callback function that will be called when Channel.Flow is
        called by the remote server. Note that newer versions of RabbitMQ
        will not issue this but instead use TCP backpressure

        :param callable callback: The callback function

        """
        self._has_on_flow_callback = True
        self.callbacks.add(self.channel_number, spec.Channel.Flow, callback,
                           False)

    def add_on_return_callback(self, callback):
        """Pass a callback function that will be called when basic_publish is
        sent a message that has been rejected and returned by the server.

        :param callable callback: The function to call, having the signature
                                callback(channel, method, properties, body)
                                where
                                - channel: pika.channel.Channel
                                - method: pika.spec.Basic.Return
                                - properties: pika.spec.BasicProperties
                                - body: bytes

        """
        self.callbacks.add(self.channel_number, '_on_return', callback, False)

    def basic_ack(self, delivery_tag=0, multiple=False):
        """Acknowledge one or more messages. When sent by the client, this
        method acknowledges one or more messages delivered via the Deliver or
        Get-Ok methods. When sent by server, this method acknowledges one or
        more messages published with the Publish method on a channel in
        confirm mode. The acknowledgement can be for a single message or a
        set of messages up to and including a specific message.

        :param integer delivery_tag: int/long The server-assigned delivery tag
        :param bool multiple: If set to True, the delivery tag is treated as
                              "up to and including", so that multiple messages
                              can be acknowledged with a single method. If set
                              to False, the delivery tag refers to a single
                              message. If the multiple field is 1, and the
                              delivery tag is zero, this indicates
                              acknowledgement of all outstanding messages.

        """
        self._raise_if_not_open()
        return self._send_method(spec.Basic.Ack(delivery_tag, multiple))

    def basic_cancel(self, consumer_tag='', callback=None):
        """This method cancels a consumer. This does not affect already
        delivered messages, but it does mean the server will not send any more
        messages for that consumer. The client may receive an arbitrary number
        of messages in between sending the cancel method and receiving the
        cancel-ok reply. It may also be sent from the server to the client in
        the event of the consumer being unexpectedly cancelled (i.e. cancelled
        for any reason other than the server receiving the corresponding
        basic.cancel from the client). This allows clients to be notified of
        the loss of consumers due to events such as queue deletion.

        :param str consumer_tag: Identifier for the consumer
        :param callable callback: callback(pika.frame.Method) for method
            Basic.CancelOk. If None, do not expect a Basic.CancelOk response,
            otherwise, callback must be callable

        :raises ValueError:

        """
        validators.require_string(consumer_tag, 'consumer_tag')
        self._raise_if_not_open()
        nowait = validators.rpc_completion_callback(callback)

        if consumer_tag in self._cancelled:
            # We check for cancelled first, because basic_cancel removes
            # consumers closed with nowait from self._consumers
            LOGGER.warning('basic_cancel - consumer is already cancelling: %s',
                           consumer_tag)
            return

        if consumer_tag not in self._consumers:
            # Could be cancelled by user or broker earlier
            LOGGER.warning('basic_cancel - consumer not found: %s',
                           consumer_tag)
            return

        LOGGER.debug('Cancelling consumer: %s (nowait=%s)', consumer_tag,
                     nowait)

        if nowait:
            # This is our last opportunity while the channel is open to remove
            # this consumer callback and help gc; unfortunately, this consumer's
            # self._cancelled and self._consumers_with_noack (if any) entries
            # will persist until the channel is closed.
            del self._consumers[consumer_tag]

        if callback is not None:
            self.callbacks.add(self.channel_number, spec.Basic.CancelOk,
                               callback)

        self._cancelled.add(consumer_tag)

        self._rpc(spec.Basic.Cancel(consumer_tag=consumer_tag, nowait=nowait),
                  self._on_cancelok if not nowait else None,
                  [(spec.Basic.CancelOk, {
                      'consumer_tag': consumer_tag
                  })] if not nowait else [])

    def basic_consume(self,
                      queue,
                      on_message_callback,
                      auto_ack=False,
                      exclusive=False,
                      consumer_tag=None,
                      arguments=None,
                      callback=None):
        """Sends the AMQP 0-9-1 command Basic.Consume to the broker and binds messages
        for the consumer_tag to the consumer callback. If you do not pass in
        a consumer_tag, one will be automatically generated for you. Returns
        the consumer tag.

        For more information on basic_consume, see:
        Tutorial 2 at http://www.rabbitmq.com/getstarted.html
        http://www.rabbitmq.com/confirms.html
        http://www.rabbitmq.com/amqp-0-9-1-reference.html#basic.consume

        :param str queue: The queue to consume from. Use the empty string to
            specify the most recent server-named queue for this channel
        :param callable on_message_callback: The function to call when
            consuming with the signature
            on_message_callback(channel, method, properties, body), where
            - channel: pika.channel.Channel
            - method: pika.spec.Basic.Deliver
            - properties: pika.spec.BasicProperties
            - body: bytes
        :param bool auto_ack: if set to True, automatic acknowledgement mode
            will be used (see http://www.rabbitmq.com/confirms.html).
            This corresponds with the 'no_ack' parameter in the basic.consume
            AMQP 0.9.1 method
        :param bool exclusive: Don't allow other consumers on the queue
        :param str consumer_tag: Specify your own consumer tag
        :param dict arguments: Custom key/value pair arguments for the consumer
        :param callable callback: callback(pika.frame.Method) for method
          Basic.ConsumeOk.
        :returns: Consumer tag which may be used to cancel the consumer.
        :rtype: str
        :raises ValueError:

        """
        validators.require_string(queue, 'queue')
        validators.require_callback(on_message_callback)
        self._raise_if_not_open()
        validators.rpc_completion_callback(callback)

        # If a consumer tag was not passed, create one
        if not consumer_tag:
            consumer_tag = self._generate_consumer_tag()

        if consumer_tag in self._consumers or consumer_tag in self._cancelled:
            raise exceptions.DuplicateConsumerTag(consumer_tag)

        if auto_ack:
            self._consumers_with_noack.add(consumer_tag)

        self._consumers[consumer_tag] = on_message_callback

        rpc_callback = self._on_eventok if callback is None else callback

        self._rpc(
            spec.Basic.Consume(queue=queue,
                               consumer_tag=consumer_tag,
                               no_ack=auto_ack,
                               exclusive=exclusive,
                               arguments=arguments or dict()), rpc_callback,
            [(spec.Basic.ConsumeOk, {
                'consumer_tag': consumer_tag
            })])

        return consumer_tag

    def _generate_consumer_tag(self):
        """Generate a consumer tag

        NOTE: this protected method may be called by derived classes

        :returns: consumer tag
        :rtype: str

        """
        return 'ctag%i.%s' % (self.channel_number, uuid.uuid4().hex)

    def basic_get(self, queue, callback, auto_ack=False):
        """Get a single message from the AMQP broker. If you want to
        be notified of Basic.GetEmpty, use the Channel.add_callback method
        adding your Basic.GetEmpty callback which should expect only one
        parameter, frame. Due to implementation details, this cannot be called
        a second time until the callback is executed.  For more information on
        basic_get and its parameters, see:

        http://www.rabbitmq.com/amqp-0-9-1-reference.html#basic.get

        :param str queue: The queue from which to get a message. Use the empty
            string to specify the most recent server-named queue for this
            channel
        :param callable callback: The callback to call with a message that has
            the signature callback(channel, method, properties, body), where:
            - channel: pika.channel.Channel
            - method: pika.spec.Basic.GetOk
            - properties: pika.spec.BasicProperties
            - body: bytes
        :param bool auto_ack: Tell the broker to not expect a reply
        :raises ValueError:

        """
        validators.require_string(queue, 'queue')
        validators.require_callback(callback)
        if self._on_getok_callback is not None:
            raise exceptions.DuplicateGetOkCallback()
        self._on_getok_callback = callback

        # pylint: disable=W0511
        # TODO Strangely, not using _rpc for the synchronous Basic.Get. Would
        # need to extend _rpc to handle Basic.GetOk method, header, and body
        # frames (or similar)
        self._send_method(spec.Basic.Get(queue=queue, no_ack=auto_ack))

    def basic_nack(self, delivery_tag=0, multiple=False, requeue=True):
        """This method allows a client to reject one or more incoming messages.
        It can be used to interrupt and cancel large incoming messages, or
        return untreatable messages to their original queue.

        :param integer delivery_tag: int/long The server-assigned delivery tag
        :param bool multiple: If set to True, the delivery tag is treated as
                              "up to and including", so that multiple messages
                              can be acknowledged with a single method. If set
                              to False, the delivery tag refers to a single
                              message. If the multiple field is 1, and the
                              delivery tag is zero, this indicates
                              acknowledgement of all outstanding messages.
        :param bool requeue: If requeue is true, the server will attempt to
                             requeue the message. If requeue is false or the
                             requeue attempt fails the messages are discarded or
                             dead-lettered.

        """
        self._raise_if_not_open()
        return self._send_method(
            spec.Basic.Nack(delivery_tag, multiple, requeue))

    def basic_publish(self,
                      exchange,
                      routing_key,
                      body,
                      properties=None,
                      mandatory=False):
        """Publish to the channel with the given exchange, routing key and body.
        For more information on basic_publish and what the parameters do, see:

        http://www.rabbitmq.com/amqp-0-9-1-reference.html#basic.publish

        :param str exchange: The exchange to publish to
        :param str routing_key: The routing key to bind on
        :param bytes body: The message body
        :param pika.spec.BasicProperties properties: Basic.properties
        :param bool mandatory: The mandatory flag

        """
        self._raise_if_not_open()
        if isinstance(body, unicode_type):
            body = body.encode('utf-8')
        properties = properties or spec.BasicProperties()
        self._send_method(
            spec.Basic.Publish(exchange=exchange,
                               routing_key=routing_key,
                               mandatory=mandatory), (properties, body))

    def basic_qos(self,
                  prefetch_size=0,
                  prefetch_count=0,
                  global_qos=False,
                  callback=None):
        """Specify quality of service. This method requests a specific quality
        of service. The client can request that messages be sent in advance
        so that when the client finishes processing a message, the following
        message is already held locally, rather than needing to be sent down
        the channel. The QoS can be applied separately to each new consumer on
        channel or shared across all consumers on the channel. Prefetching
        gives a performance improvement.

        :param int prefetch_size:  This field specifies the prefetch window
                                   size. The server will send a message in
                                   advance if it is equal to or smaller in size
                                   than the available prefetch size (and also
                                   falls into other prefetch limits). May be set
                                   to zero, meaning "no specific limit",
                                   although other prefetch limits may still
                                   apply. The prefetch-size is ignored by
                                   consumers who have enabled the no-ack option.
        :param int prefetch_count: Specifies a prefetch window in terms of whole
                                   messages. This field may be used in
                                   combination with the prefetch-size field; a
                                   message will only be sent in advance if both
                                   prefetch windows (and those at the channel
                                   and connection level) allow it. The
                                   prefetch-count is ignored by consumers who
                                   have enabled the no-ack option.
        :param bool global_qos:    Should the QoS be shared across all
                                   consumers on the channel.
        :param callable callback: The callback to call for Basic.QosOk response
        :raises ValueError:

        """
        self._raise_if_not_open()
        validators.rpc_completion_callback(callback)
        validators.zero_or_greater('prefetch_size', prefetch_size)
        validators.zero_or_greater('prefetch_count', prefetch_count)
        return self._rpc(
            spec.Basic.Qos(prefetch_size, prefetch_count, global_qos), callback,
            [spec.Basic.QosOk])

    def basic_reject(self, delivery_tag=0, requeue=True):
        """Reject an incoming message. This method allows a client to reject a
        message. It can be used to interrupt and cancel large incoming messages,
        or return untreatable messages to their original queue.

        :param integer delivery_tag: int/long The server-assigned delivery tag
        :param bool requeue: If requeue is true, the server will attempt to
                             requeue the message. If requeue is false or the
                             requeue attempt fails the messages are discarded or
                             dead-lettered.
        :raises: TypeError

        """
        self._raise_if_not_open()
        if not is_integer(delivery_tag):
            raise TypeError('delivery_tag must be an integer')
        return self._send_method(spec.Basic.Reject(delivery_tag, requeue))

    def basic_recover(self, requeue=False, callback=None):
        """This method asks the server to redeliver all unacknowledged messages
        on a specified channel. Zero or more messages may be redelivered. This
        method replaces the asynchronous Recover.

        :param bool requeue: If False, the message will be redelivered to the
                             original recipient. If True, the server will
                             attempt to requeue the message, potentially then
                             delivering it to an alternative subscriber.
        :param callable callback: Callback to call when receiving
            Basic.RecoverOk
        :param callable callback: callback(pika.frame.Method) for method
            Basic.RecoverOk
        :raises ValueError:

        """
        self._raise_if_not_open()
        validators.rpc_completion_callback(callback)
        return self._rpc(spec.Basic.Recover(requeue), callback,
                         [spec.Basic.RecoverOk])

    def close(self, reply_code=0, reply_text="Normal shutdown"):
        """Invoke a graceful shutdown of the channel with the AMQP Broker.

        If channel is OPENING, transition to CLOSING and suppress the incoming
        Channel.OpenOk, if any.

        :param int reply_code: The reason code to send to broker
        :param str reply_text: The reason text to send to broker

        :raises ChannelWrongStateError: if channel is closed or closing

        """
        if self.is_closed or self.is_closing:
            # Whoever is calling `close` might expect the on-channel-close-cb
            # to be called, which won't happen when it's already closed.
            self._raise_if_not_open()

        # If channel is OPENING, we will transition it to CLOSING state,
        # causing the _on_openok method to suppress the OPEN state transition
        # and the on-channel-open-callback

        LOGGER.info('Closing channel (%s): %r on %s', reply_code, reply_text,
                    self)

        # Save the reason info so that we may use it in the '_on_channel_close'
        # callback processing
        self._closing_reason = exceptions.ChannelClosedByClient(
            reply_code, reply_text)

        for consumer_tag in dictkeys(self._consumers):
            if consumer_tag not in self._cancelled:
                self.basic_cancel(consumer_tag=consumer_tag)

        # Change state after cancelling consumers to avoid
        # ChannelWrongStateError exception from basic_cancel
        self._set_state(self.CLOSING)

        self._rpc(spec.Channel.Close(reply_code, reply_text, 0, 0),
                  self._on_closeok, [spec.Channel.CloseOk])

    def confirm_delivery(self, ack_nack_callback, callback=None):
        """Turn on Confirm mode in the channel. Pass in a callback to be
        notified by the Broker when a message has been confirmed as received or
        rejected (Basic.Ack, Basic.Nack) from the broker to the publisher.

        For more information see:
            https://www.rabbitmq.com/confirms.html

        :param callable ack_nack_callback: Required callback for delivery
            confirmations that has the following signature:
            callback(pika.frame.Method), where method_frame contains
            either method `spec.Basic.Ack` or `spec.Basic.Nack`.
        :param callable callback: callback(pika.frame.Method) for method
            Confirm.SelectOk
        :raises ValueError:

        """
        if not callable(ack_nack_callback):
            # confirm_deliver requires a callback; it's meaningless
            # without a user callback to receieve Basic.Ack/Basic.Nack notifications
            raise ValueError('confirm_delivery requires a callback '
                             'to receieve Basic.Ack/Basic.Nack notifications')

        self._raise_if_not_open()
        nowait = validators.rpc_completion_callback(callback)

        if not (self.connection.publisher_confirms and
                self.connection.basic_nack):
            raise exceptions.MethodNotImplemented(
                'Confirm.Select not Supported by Server')

        # Add the ack and nack callback
        self.callbacks.add(self.channel_number, spec.Basic.Ack,
                           ack_nack_callback, False)
        self.callbacks.add(self.channel_number, spec.Basic.Nack,
                           ack_nack_callback, False)

        self._rpc(spec.Confirm.Select(nowait), callback,
                  [spec.Confirm.SelectOk] if not nowait else [])

    @property
    def consumer_tags(self):
        """Property method that returns a list of currently active consumers

        :rtype: list

        """
        return dictkeys(self._consumers)

    def exchange_bind(self,
                      destination,
                      source,
                      routing_key='',
                      arguments=None,
                      callback=None):
        """Bind an exchange to another exchange.

        :param str destination: The destination exchange to bind
        :param str source: The source exchange to bind to
        :param str routing_key: The routing key to bind on
        :param dict arguments: Custom key/value pair arguments for the binding
        :param callable callback: callback(pika.frame.Method) for method Exchange.BindOk
        :raises ValueError:

        """
        self._raise_if_not_open()
        validators.require_string(destination, 'destination')
        validators.require_string(source, 'source')
        nowait = validators.rpc_completion_callback(callback)
        return self._rpc(
            spec.Exchange.Bind(0, destination, source, routing_key, nowait,
                               arguments or dict()), callback,
            [spec.Exchange.BindOk] if not nowait else [])

    def exchange_declare(self,
                         exchange,
                         exchange_type=ExchangeType.direct,
                         passive=False,
                         durable=False,
                         auto_delete=False,
                         internal=False,
                         arguments=None,
                         callback=None):
        """This method creates an exchange if it does not already exist, and if
        the exchange exists, verifies that it is of the correct and expected
        class.

        If passive set, the server will reply with Declare-Ok if the exchange
        already exists with the same name, and raise an error if not and if the
        exchange does not already exist, the server MUST raise a channel
        exception with reply code 404 (not found).

        :param str exchange: The exchange name consists of a non-empty sequence
            of these characters: letters, digits, hyphen, underscore, period,
            or colon
        :param str exchange_type: The exchange type to use
        :param bool passive: Perform a declare or just check to see if it exists
        :param bool durable: Survive a reboot of RabbitMQ
        :param bool auto_delete: Remove when no more queues are bound to it
        :param bool internal: Can only be published to by other exchanges
        :param dict arguments: Custom key/value pair arguments for the exchange
        :param callable callback: callback(pika.frame.Method) for method Exchange.DeclareOk
        :raises ValueError:

        """
        validators.require_string(exchange, 'exchange')
        self._raise_if_not_open()
        nowait = validators.rpc_completion_callback(callback)
        if isinstance(exchange_type, Enum):
            exchange_type = exchange_type.value
        return self._rpc(
            spec.Exchange.Declare(0, exchange, exchange_type, passive, durable,
                                  auto_delete, internal, nowait, arguments or
                                  dict()), callback,
            [spec.Exchange.DeclareOk] if not nowait else [])

    def exchange_delete(self, exchange=None, if_unused=False, callback=None):
        """Delete the exchange.

        :param str exchange: The exchange name
        :param bool if_unused: only delete if the exchange is unused
        :param callable callback: callback(pika.frame.Method) for method Exchange.DeleteOk
        :raises ValueError:

        """
        self._raise_if_not_open()
        nowait = validators.rpc_completion_callback(callback)
        return self._rpc(spec.Exchange.Delete(0, exchange, if_unused,
                                              nowait), callback,
                         [spec.Exchange.DeleteOk] if not nowait else [])

    def exchange_unbind(self,
                        destination=None,
                        source=None,
                        routing_key='',
                        arguments=None,
                        callback=None):
        """Unbind an exchange from another exchange.

        :param str destination: The destination exchange to unbind
        :param str source: The source exchange to unbind from
        :param str routing_key: The routing key to unbind
        :param dict arguments: Custom key/value pair arguments for the binding
        :param callable callback: callback(pika.frame.Method) for method Exchange.UnbindOk
        :raises ValueError:

        """
        self._raise_if_not_open()
        nowait = validators.rpc_completion_callback(callback)
        return self._rpc(
            spec.Exchange.Unbind(0, destination, source, routing_key, nowait,
                                 arguments), callback,
            [spec.Exchange.UnbindOk] if not nowait else [])

    def flow(self, active, callback=None):
        """Turn Channel flow control off and on. Pass a callback to be notified
        of the response from the server. active is a bool. Callback should
        expect a bool in response indicating channel flow state. For more
        information, please reference:

        http://www.rabbitmq.com/amqp-0-9-1-reference.html#channel.flow

        :param bool active: Turn flow on or off
        :param callable callback: callback(bool) upon completion
        :raises ValueError:

        """
        self._raise_if_not_open()
        validators.rpc_completion_callback(callback)
        self._on_flowok_callback = callback
        self._rpc(spec.Channel.Flow(active), self._on_flowok,
                  [spec.Channel.FlowOk])

    @property
    def is_closed(self):
        """Returns True if the channel is closed.

        :rtype: bool

        """
        return self._state == self.CLOSED

    @property
    def is_closing(self):
        """Returns True if client-initiated closing of the channel is in
        progress.

        :rtype: bool

        """
        return self._state == self.CLOSING

    @property
    def is_open(self):
        """Returns True if the channel is open.

        :rtype: bool

        """
        return self._state == self.OPEN

    @property
    def is_opening(self):
        """Returns True if the channel is opening.

        :rtype: bool

        """
        return self._state == self.OPENING

    def open(self):
        """Open the channel"""
        self._set_state(self.OPENING)
        self._add_callbacks()
        self._rpc(spec.Channel.Open(), self._on_openok, [spec.Channel.OpenOk])

    def queue_bind(self,
                   queue,
                   exchange,
                   routing_key=None,
                   arguments=None,
                   callback=None):
        """Bind the queue to the specified exchange

        :param str queue: The queue to bind to the exchange
        :param str exchange: The source exchange to bind to
        :param str routing_key: The routing key to bind on
        :param dict arguments: Custom key/value pair arguments for the binding
        :param callable callback: callback(pika.frame.Method) for method Queue.BindOk
        :raises ValueError:

        """
        validators.require_string(queue, 'queue')
        validators.require_string(exchange, 'exchange')
        self._raise_if_not_open()
        nowait = validators.rpc_completion_callback(callback)
        if routing_key is None:
            routing_key = queue
        return self._rpc(
            spec.Queue.Bind(0, queue, exchange, routing_key, nowait,
                            arguments or dict()), callback,
            [spec.Queue.BindOk] if not nowait else [])

    def queue_declare(self,
                      queue,
                      passive=False,
                      durable=False,
                      exclusive=False,
                      auto_delete=False,
                      arguments=None,
                      callback=None):
        """Declare queue, create if needed. This method creates or checks a
        queue. When creating a new queue the client can specify various
        properties that control the durability of the queue and its contents,
        and the level of sharing for the queue.

        Use an empty string as the queue name for the broker to auto-generate
        one

        :param str queue: The queue name; if empty string, the broker will
            create a unique queue name
        :param bool passive: Only check to see if the queue exists
        :param bool durable: Survive reboots of the broker
        :param bool exclusive: Only allow access by the current connection
        :param bool auto_delete: Delete after consumer cancels or disconnects
        :param dict arguments: Custom key/value arguments for the queue
        :param callable callback: callback(pika.frame.Method) for method Queue.DeclareOk
        :raises ValueError:

        """
        validators.require_string(queue, 'queue')
        self._raise_if_not_open()
        nowait = validators.rpc_completion_callback(callback)

        if queue:
            condition = (spec.Queue.DeclareOk, {'queue': queue})
        else:
            condition = spec.Queue.DeclareOk
        replies = [condition] if not nowait else []

        return self._rpc(
            spec.Queue.Declare(0, queue, passive, durable, exclusive,
                               auto_delete, nowait, arguments or dict()),
            callback, replies)

    def queue_delete(self,
                     queue,
                     if_unused=False,
                     if_empty=False,
                     callback=None):
        """Delete a queue from the broker.

        :param str queue: The queue to delete
        :param bool if_unused: only delete if it's unused
        :param bool if_empty: only delete if the queue is empty
        :param callable callback: callback(pika.frame.Method) for method Queue.DeleteOk
        :raises ValueError:

        """
        self._raise_if_not_open()
        validators.require_string(queue, 'queue')
        nowait = validators.rpc_completion_callback(callback)
        replies = [spec.Queue.DeleteOk] if not nowait else []
        return self._rpc(
            spec.Queue.Delete(0, queue, if_unused, if_empty, nowait), callback,
            replies)

    def queue_purge(self, queue, callback=None):
        """Purge all of the messages from the specified queue

        :param str queue: The queue to purge
        :param callable callback: callback(pika.frame.Method) for method Queue.PurgeOk
        :raises ValueError:

        """
        self._raise_if_not_open()
        validators.require_string(queue, 'queue')
        nowait = validators.rpc_completion_callback(callback)
        replies = [spec.Queue.PurgeOk] if not nowait else []
        return self._rpc(spec.Queue.Purge(0, queue, nowait), callback, replies)

    def queue_unbind(self,
                     queue,
                     exchange=None,
                     routing_key=None,
                     arguments=None,
                     callback=None):
        """Unbind a queue from an exchange.

        :param str queue: The queue to unbind from the exchange
        :param str exchange: The source exchange to bind from
        :param str routing_key: The routing key to unbind
        :param dict arguments: Custom key/value pair arguments for the binding
        :param callable callback: callback(pika.frame.Method) for method Queue.UnbindOk
        :raises ValueError:

        """
        self._raise_if_not_open()
        validators.require_string(queue, 'queue')
        validators.rpc_completion_callback(callback)
        if routing_key is None:
            routing_key = queue
        return self._rpc(
            spec.Queue.Unbind(0, queue, exchange, routing_key, arguments or
                              dict()), callback, [spec.Queue.UnbindOk])

    def tx_commit(self, callback=None):
        """Commit a transaction

        :param callable callback: The callback for delivery confirmations
        :raises ValueError:

        """
        self._raise_if_not_open()
        validators.rpc_completion_callback(callback)
        return self._rpc(spec.Tx.Commit(), callback, [spec.Tx.CommitOk])

    def tx_rollback(self, callback=None):
        """Rollback a transaction.

        :param callable callback: The callback for delivery confirmations
        :raises ValueError:

        """
        self._raise_if_not_open()
        validators.rpc_completion_callback(callback)
        return self._rpc(spec.Tx.Rollback(), callback, [spec.Tx.RollbackOk])

    def tx_select(self, callback=None):
        """Select standard transaction mode. This method sets the channel to use
        standard transactions. The client must use this method at least once on
        a channel before using the Commit or Rollback methods.

        :param callable callback: The callback for delivery confirmations
        :raises ValueError:

        """
        self._raise_if_not_open()
        validators.rpc_completion_callback(callback)
        return self._rpc(spec.Tx.Select(), callback, [spec.Tx.SelectOk])

    # Internal methods

    def _add_callbacks(self):
        """Callbacks that add the required behavior for a channel when
        connecting and connected to a server.

        """
        # Add a callback for Basic.GetEmpty
        self.callbacks.add(self.channel_number, spec.Basic.GetEmpty,
                           self._on_getempty, False)

        # Add a callback for Basic.Cancel
        self.callbacks.add(self.channel_number, spec.Basic.Cancel,
                           self._on_cancel, False)

        # Deprecated in newer versions of RabbitMQ but still register for it
        self.callbacks.add(self.channel_number, spec.Channel.Flow,
                           self._on_flow, False)

        # Add a callback for when the server closes our channel
        self.callbacks.add(self.channel_number, spec.Channel.Close,
                           self._on_close_from_broker, True)

    def _add_on_cleanup_callback(self, callback):
        """For internal use only (e.g., Connection needs to remove closed
        channels from its channel container). Pass a callback function that will
        be called when the channel is being cleaned up after all channel-close
        callbacks callbacks.

        :param callable callback: The callback to call, having the
            signature: callback(channel)

        """
        self.callbacks.add(self.channel_number,
                           self._ON_CHANNEL_CLEANUP_CB_KEY,
                           callback,
                           one_shot=True,
                           only_caller=self)

    def _cleanup(self):
        """Remove all consumers and any callbacks for the channel."""
        self.callbacks.process(self.channel_number,
                               self._ON_CHANNEL_CLEANUP_CB_KEY, self, self)
        self._consumers = dict()
        self.callbacks.cleanup(str(self.channel_number))
        self._cookie = None

    def _cleanup_consumer_ref(self, consumer_tag):
        """Remove any references to the consumer tag in internal structures
        for consumer state.

        :param str consumer_tag: The consumer tag to cleanup

        """
        self._consumers_with_noack.discard(consumer_tag)
        self._consumers.pop(consumer_tag, None)
        self._cancelled.discard(consumer_tag)

    def _get_cookie(self):
        """Used by the wrapper implementation (e.g., `BlockingChannel`) to
        retrieve the cookie that it set via `_set_cookie`

        :returns: opaque cookie value that was set via `_set_cookie`
        :rtype: object

        """
        return self._cookie

    def _handle_content_frame(self, frame_value):
        """This is invoked by the connection when frames that are not registered
        with the CallbackManager have been found. This should only be the case
        when the frames are related to content delivery.

        The _content_assembler will be invoked which will return the fully
        formed message in three parts when all of the body frames have been
        received.

        :param pika.amqp_object.Frame frame_value: The frame to deliver

        """
        try:
            response = self._content_assembler.process(frame_value)
        except exceptions.UnexpectedFrameError:
            self._on_unexpected_frame(frame_value)
            return

        if response:
            if isinstance(response[0].method, spec.Basic.Deliver):
                self._on_deliver(*response)
            elif isinstance(response[0].method, spec.Basic.GetOk):
                self._on_getok(*response)
            elif isinstance(response[0].method, spec.Basic.Return):
                self._on_return(*response)

    def _on_cancel(self, method_frame):
        """When the broker cancels a consumer, delete it from our internal
        dictionary.

        :param pika.frame.Method method_frame: The method frame received

        """
        if method_frame.method.consumer_tag in self._cancelled:
            # User-initiated cancel is waiting for Cancel-ok
            return

        self._cleanup_consumer_ref(method_frame.method.consumer_tag)

    def _on_cancelok(self, method_frame):
        """Called in response to a frame from the Broker when the
         client sends Basic.Cancel

        :param pika.frame.Method method_frame: The method frame received

        """
        self._cleanup_consumer_ref(method_frame.method.consumer_tag)

    def _transition_to_closed(self):
        """Common logic for transitioning the channel to the CLOSED state:

        Set state to CLOSED, dispatch callbacks registered via
        `Channel.add_on_close_callback()`, and mop up.

        Assumes that the channel is not in CLOSED state and that
        `self._closing_reason` has been set up

        """
        assert not self.is_closed
        assert self._closing_reason is not None

        self._set_state(self.CLOSED)

        try:
            self.callbacks.process(self.channel_number, '_on_channel_close',
                                   self, self, self._closing_reason)
        finally:
            self._cleanup()

    def _on_close_from_broker(self, method_frame):
        """Handle `Channel.Close` from broker.

        :param pika.frame.Method method_frame: Method frame with Channel.Close
            method

        """
        LOGGER.warning('Received remote Channel.Close (%s): %r on %s',
                       method_frame.method.reply_code,
                       method_frame.method.reply_text, self)
        # Note, we should not be called when channel is already closed
        assert not self.is_closed

        # AMQP 0.9.1 requires CloseOk response to Channel.Close;
        self._send_method(spec.Channel.CloseOk())

        # Save the details, possibly overriding user-provided values if
        # user-initiated close is pending (in which case they will be provided
        # to user callback when CloseOk arrives).
        self._closing_reason = exceptions.ChannelClosedByBroker(
            method_frame.method.reply_code, method_frame.method.reply_text)

        if self.is_closing:
            # Since we may have already put Channel.Close on the wire, we need
            # to wait for CloseOk before cleaning up to avoid a race condition
            # whereby our channel number might get reused before our CloseOk
            # arrives
            #
            # NOTE: if our Channel.Close destined for the broker was blocked by
            # an earlier synchronous method, this call will drop it and perform
            # a meta-close (see `_on_close_meta()` which fakes receipt of
            # `Channel.CloseOk` and dispatches the `'_on_channel_close'`
            # callbacks.
            self._drain_blocked_methods_on_remote_close()
        else:
            self._transition_to_closed()

    def _on_close_meta(self, reason):
        """Handle meta-close request from either a remote Channel.Close from
        the broker (when a pending Channel.Close method is queued for
        execution) or a Connection's cleanup logic after sudden connection
        loss. We use this opportunity to transition to CLOSED state, clean up
        the channel, and dispatch the on-channel-closed callbacks.

        :param Exception reason: Exception describing the reason for closing.

        """
        LOGGER.debug('Handling meta-close on %s: %r', self, reason)

        if not self.is_closed:
            self._closing_reason = reason
            self._transition_to_closed()

    def _on_closeok(self, method_frame):
        """Invoked when RabbitMQ replies to a Channel.Close method

        :param pika.frame.Method method_frame: Method frame with Channel.CloseOk
            method

        """
        LOGGER.info('Received %s on %s', method_frame.method, self)

        self._transition_to_closed()

    def _on_deliver(self, method_frame, header_frame, body):
        """Cope with reentrancy. If a particular consumer is still active when
        another delivery appears for it, queue the deliveries up until it
        finally exits.

        :param pika.frame.Method method_frame: The method frame received
        :param pika.frame.Header header_frame: The header frame received
        :param bytes body: The body received

        """
        consumer_tag = method_frame.method.consumer_tag

        if consumer_tag in self._cancelled:
            if self.is_open and consumer_tag not in self._consumers_with_noack:
                self.basic_reject(method_frame.method.delivery_tag)
            return

        if consumer_tag not in self._consumers:
            LOGGER.error('Unexpected delivery: %r', method_frame)
            return

        self._consumers[consumer_tag](self, method_frame.method,
                                      header_frame.properties, body)

    def _on_eventok(self, method_frame):
        """Generic events that returned ok that may have internal callbacks.
        We keep a list of what we've yet to implement so that we don't silently
        drain events that we don't support.

        :param pika.frame.Method method_frame: The method frame received

        """
        LOGGER.debug('Discarding frame %r', method_frame)

    def _on_flow(self, _method_frame_unused):
        """Called if the server sends a Channel.Flow frame.

        :param pika.frame.Method method_frame_unused: The Channel.Flow frame

        """
        if self._has_on_flow_callback is False:
            LOGGER.warning('Channel.Flow received from server')

    def _on_flowok(self, method_frame):
        """Called in response to us asking the server to toggle on Channel.Flow

        :param pika.frame.Method method_frame: The method frame received

        """
        self.flow_active = method_frame.method.active
        if self._on_flowok_callback:
            self._on_flowok_callback(method_frame.method.active)
            self._on_flowok_callback = None
        else:
            LOGGER.warning('Channel.FlowOk received with no active callbacks')

    def _on_getempty(self, method_frame):
        """When we receive an empty reply do nothing but log it

        :param pika.frame.Method method_frame: The method frame received

        """
        LOGGER.debug('Received Basic.GetEmpty: %r', method_frame)
        if self._on_getok_callback is not None:
            self._on_getok_callback = None

    def _on_getok(self, method_frame, header_frame, body):
        """Called in reply to a Basic.Get when there is a message.

        :param pika.frame.Method method_frame: The method frame received
        :param pika.frame.Header header_frame: The header frame received
        :param bytes body: The body received

        """
        if self._on_getok_callback is not None:
            callback = self._on_getok_callback
            self._on_getok_callback = None
            callback(self, method_frame.method, header_frame.properties, body)
        else:
            LOGGER.error('Basic.GetOk received with no active callback')

    def _on_openok(self, method_frame):
        """Called by our callback handler when we receive a Channel.OpenOk and
        subsequently calls our _on_openok_callback which was passed into the
        Channel constructor. The reason we do this is because we want to make
        sure that the on_open_callback parameter passed into the Channel
        constructor is not the first callback we make.

        Suppress the state transition and callback if channel is already in
        CLOSING state.

        :param pika.frame.Method method_frame: Channel.OpenOk frame

        """
        # Suppress OpenOk if the user or Connection.Close started closing it
        # before open completed.
        if self.is_closing:
            LOGGER.debug('Suppressing while in closing state: %s', method_frame)
        else:
            self._set_state(self.OPEN)
            if self._on_openok_callback is not None:
                self._on_openok_callback(self)

    def _on_return(self, method_frame, header_frame, body):
        """Called if the server sends a Basic.Return frame.

        :param pika.frame.Method method_frame: The Basic.Return frame
        :param pika.frame.Header header_frame: The content header frame
        :param bytes body: The message body

        """
        if not self.callbacks.process(self.channel_number, '_on_return', self,
                                      self, method_frame.method,
                                      header_frame.properties, body):
            LOGGER.debug('Basic.Return received from server (%r, %r)',
                          method_frame.method, header_frame.properties)

    def _on_selectok(self, method_frame):
        """Called when the broker sends a Confirm.SelectOk frame

        :param pika.frame.Method method_frame: The method frame received

        """
        LOGGER.debug("Confirm.SelectOk Received: %r", method_frame)

    def _on_synchronous_complete(self, _method_frame_unused):
        """This is called when a synchronous command is completed. It will undo
        the blocking state and send all the frames that stacked up while we
        were in the blocking state.

        :param pika.frame.Method method_frame_unused: The method frame received

        """
        LOGGER.debug('%i blocked frames', len(self._blocked))
        self._blocking = None
        # self._blocking must be checked here as a callback could
        # potentially change the state of that variable during an
        # iteration of the while loop
        while self._blocked and self._blocking is None:
            self._rpc(*self._blocked.popleft())

    def _drain_blocked_methods_on_remote_close(self):
        """This is called when the broker sends a Channel.Close while the
        client is in CLOSING state. This method checks the blocked method
        queue for a pending client-initiated Channel.Close method and
        ensures its callbacks are processed, but does not send the method
        to the broker.

        The broker may close the channel before responding to outstanding
        in-transit synchronous methods, or even before these methods have been
        sent to the broker. AMQP 0.9.1 obliges the server to drop all methods
        arriving on a closed channel other than Channel.CloseOk and
        Channel.Close. Since the response to a synchronous method that blocked
        the channel never arrives, the channel never becomes unblocked, and the
        Channel.Close, if any, in the blocked queue has no opportunity to be
        sent, and thus its completion callback would never be called.

        """
        LOGGER.debug(
            'Draining %i blocked frames due to broker-requested Channel.Close',
            len(self._blocked))
        while self._blocked:
            method = self._blocked.popleft()[0]
            if isinstance(method, spec.Channel.Close):
                # The desired reason is already in self._closing_reason
                self._on_close_meta(self._closing_reason)
            else:
                LOGGER.debug('Ignoring drained blocked method: %s', method)

    def _rpc(self, method, callback=None, acceptable_replies=None):
        """Make a synchronous channel RPC call for a synchronous method frame. If
        the channel is already in the blocking state, then enqueue the request,
        but don't send it at this time; it will be eventually sent by
        `_on_synchronous_complete` after the prior blocking request receives a
        response. If the channel is not in the blocking state and
        `acceptable_replies` is not empty, transition the channel to the
        blocking state and register for `_on_synchronous_complete` before
        sending the request.

        NOTE: A callback must be accompanied by non-empty acceptable_replies.

        :param pika.amqp_object.Method method: The AMQP method to invoke
        :param callable callback: The callback for the RPC response
        :param list|None acceptable_replies: A (possibly empty) sequence of
            replies this RPC call expects or None

        """
        assert method.synchronous, (
            'Only synchronous-capable methods may be used with _rpc: %r' %
            (method,))

        # Validate we got None or a list of acceptable_replies
        if not isinstance(acceptable_replies, (type(None), list)):
            raise TypeError('acceptable_replies should be list or None')

        if callback is not None:
            # Validate the callback is callable
            if not callable(callback):
                raise TypeError('callback should be None or a callable')

            # Make sure that callback is accompanied by acceptable replies
            if not acceptable_replies:
                raise ValueError(
                    'Unexpected callback for asynchronous (nowait) operation.')

        # Make sure the channel is not closed yet
        if self.is_closed:
            self._raise_if_not_open()

        # If the channel is blocking, add subsequent commands to our stack
        if self._blocking:
            LOGGER.debug(
                'Already in blocking state, so enqueueing method %s; '
                'acceptable_replies=%r', method, acceptable_replies)
            self._blocked.append([method, callback, acceptable_replies])
            return

        # Note: _send_method can throw exceptions if there are framing errors
        # or invalid data passed in. Call it here to prevent self._blocking
        # from being set if an exception is thrown. This also prevents
        # acceptable_replies registering callbacks when exceptions are thrown
        self._send_method(method)

        # If acceptable replies are set, add callbacks
        if acceptable_replies:
            # Block until a response frame is received for synchronous frames
            self._blocking = method.NAME
            LOGGER.debug(
                'Entering blocking state on frame %s; acceptable_replies=%r',
                method, acceptable_replies)

            for reply in acceptable_replies:
                if isinstance(reply, tuple):
                    reply, arguments = reply
                else:
                    arguments = None
                LOGGER.debug('Adding on_synchronous_complete callback')
                self.callbacks.add(self.channel_number,
                                   reply,
                                   self._on_synchronous_complete,
                                   arguments=arguments)
                if callback is not None:
                    LOGGER.debug('Adding passed-in RPC response callback')
                    self.callbacks.add(self.channel_number,
                                       reply,
                                       callback,
                                       arguments=arguments)

    def _raise_if_not_open(self):
        """If channel is not in the OPEN state, raises ChannelWrongStateError
        with `reply_code` and `reply_text` corresponding to current state.

        :raises exceptions.ChannelWrongStateError: if channel is not in OPEN
            state.
        """
        if self._state == self.OPEN:
            return

        if self._state == self.OPENING:
            raise exceptions.ChannelWrongStateError('Channel is opening, but is not usable yet.')

        if self._state == self.CLOSING:
            raise exceptions.ChannelWrongStateError('Channel is closing.')

        # Assumed self.CLOSED
        assert self._state == self.CLOSED
        raise exceptions.ChannelWrongStateError('Channel is closed.')

    def _send_method(self, method, content=None):
        """Shortcut wrapper to send a method through our connection, passing in
        the channel number

        :param pika.amqp_object.Method method: The method to send
        :param tuple content: If set, is a content frame, is tuple of
                              properties and body.

        """
        # pylint: disable=W0212
        self.connection._send_method(self.channel_number, method, content)

    def _set_cookie(self, cookie):
        """Used by wrapper layer (e.g., `BlockingConnection`) to link the
        channel implementation back to the proxy. See `_get_cookie`.

        :param cookie: an opaque value; typically a proxy channel implementation
            instance (e.g., `BlockingChannel` instance)
        """
        self._cookie = cookie

    def _set_state(self, connection_state):
        """Set the channel connection state to the specified state value.

        :param int connection_state: The connection_state value

        """
        self._state = connection_state

    def _on_unexpected_frame(self, frame_value):
        """Invoked when a frame is received that is not setup to be processed.

        :param pika.frame.Frame frame_value: The frame received

        """
        LOGGER.error('Unexpected frame: %r', frame_value)


class ContentFrameAssembler(object):
    """Handle content related frames, building a message and return the message
    back in three parts upon receipt.

    """

    def __init__(self):
        """Create a new instance of the conent frame assembler.

        """
        self._method_frame = None
        self._header_frame = None
        self._seen_so_far = 0
        self._body_fragments = list()

    def process(self, frame_value):
        """Invoked by the Channel object when passed frames that are not
        setup in the rpc process and that don't have explicit reply types
        defined. This includes Basic.Publish, Basic.GetOk and Basic.Return

        :param Method|Header|Body frame_value: The frame to process

        """
        if (isinstance(frame_value, frame.Method) and
                spec.has_content(frame_value.method.INDEX)):
            self._method_frame = frame_value
            return None
        elif isinstance(frame_value, frame.Header):
            self._header_frame = frame_value
            if frame_value.body_size == 0:
                return self._finish()
            else:
                return None
        elif isinstance(frame_value, frame.Body):
            return self._handle_body_frame(frame_value)
        else:
            raise exceptions.UnexpectedFrameError(frame_value)

    def _finish(self):
        """Invoked when all of the message has been received

        :rtype: tuple(pika.frame.Method, pika.frame.Header, str)

        """
        content = (self._method_frame, self._header_frame,
                   b''.join(self._body_fragments))
        self._reset()
        return content

    def _handle_body_frame(self, body_frame):
        """Receive body frames and append them to the stack. When the body size
        matches, call the finish method.

        :param Body body_frame: The body frame
        :raises: pika.exceptions.BodyTooLongError
        :rtype: tuple(pika.frame.Method, pika.frame.Header, str)|None

        """
        self._seen_so_far += len(body_frame.fragment)
        self._body_fragments.append(body_frame.fragment)
        if self._seen_so_far == self._header_frame.body_size:
            return self._finish()
        elif self._seen_so_far > self._header_frame.body_size:
            raise exceptions.BodyTooLongError(self._seen_so_far,
                                              self._header_frame.body_size)
        return None

    def _reset(self):
        """Reset the values for processing frames"""
        self._method_frame = None
        self._header_frame = None
        self._seen_so_far = 0
        self._body_fragments = list()
