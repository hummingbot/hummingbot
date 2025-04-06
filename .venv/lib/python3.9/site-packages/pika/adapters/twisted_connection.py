"""Using Pika with a Twisted reactor.

The interfaces in this module are Deferred-based when possible. This means that
the connection.channel() method and most of the channel methods return
Deferreds instead of taking a callback argument and that basic_consume()
returns a Twisted DeferredQueue where messages from the server will be
stored. Refer to the docstrings for TwistedProtocolConnection.channel() and the
TwistedChannel class for details.

"""

import functools
import logging
from collections import namedtuple

from twisted.internet import (defer, error as twisted_error, reactor, protocol)
from twisted.python.failure import Failure

import pika.connection
from pika import exceptions, spec
from pika.adapters.utils import nbio_interface
from pika.adapters.utils.io_services_utils import check_callback_arg
from pika.exchange_type import ExchangeType

# Twistisms
# pylint: disable=C0111,C0103
# Other
# pylint: disable=too-many-lines

LOGGER = logging.getLogger(__name__)


class ClosableDeferredQueue(defer.DeferredQueue):
    """
    Like the normal Twisted DeferredQueue, but after close() is called with an
    exception instance all pending Deferreds are errbacked and further attempts
    to call get() or put() return a Failure wrapping that exception.
    """

    def __init__(self, size=None, backlog=None):
        self.closed = None
        super(ClosableDeferredQueue, self).__init__(size, backlog)

    def put(self, obj):
        """
        Like the original :meth:`DeferredQueue.put` method, but returns an
        errback if the queue is closed.

        """
        if self.closed:
            LOGGER.error('Impossible to put to the queue, it is closed.')
            return defer.fail(self.closed)
        return defer.DeferredQueue.put(self, obj)

    def get(self):
        """
        Returns a Deferred that will fire with the next item in the queue, when
        it's available.

        The Deferred will errback if the queue is closed.

        :returns: Deferred that fires with the next item.
        :rtype: Deferred

        """
        if self.closed:
            LOGGER.error('Impossible to get from the queue, it is closed.')
            return defer.fail(self.closed)
        return defer.DeferredQueue.get(self)

    def close(self, reason):
        """Closes the queue.

        Errback the pending calls to :meth:`get()`.

        """
        if self.closed:
            LOGGER.warning('Queue was already closed with reason: %s.',
                           self.closed)
        self.closed = reason
        while self.waiting:
            self.waiting.pop().errback(reason)
        self.pending = []


ReceivedMessage = namedtuple("ReceivedMessage",
                             ["channel", "method", "properties", "body"])


class TwistedChannel(object):
    """A wrapper around Pika's Channel.

    Channel methods that normally take a callback argument are wrapped to
    return a Deferred that fires with whatever would be passed to the callback.
    If the channel gets closed, all pending Deferreds are errbacked with a
    ChannelClosed exception. The returned Deferreds fire with whatever
    arguments the callback to the original method would receive.

    Some methods like basic_consume and basic_get are wrapped in a special way,
    see their docstrings for details.
    """

    def __init__(self, channel):
        self._channel = channel
        self._closed = None
        self._calls = set()
        self._consumers = {}
        # Store Basic.Get calls so we can handle GetEmpty replies
        self._basic_get_deferred = None
        self._channel.add_callback(self._on_getempty, [spec.Basic.GetEmpty],
                                   False)
        # We need this mapping to close the ClosableDeferredQueue when a queue
        # is deleted.
        self._queue_name_to_consumer_tags = {}
        # Whether RabbitMQ delivery confirmation has been enabled
        self._delivery_confirmation = False
        self._delivery_message_id = None
        self._deliveries = {}
        # Holds a ReceivedMessage object representing a message received via
        # Basic.Return in publisher-acknowledgments mode.
        self._puback_return = None

        self.on_closed = defer.Deferred()
        self._channel.add_on_close_callback(self._on_channel_closed)
        self._channel.add_on_cancel_callback(
            self._on_consumer_cancelled_by_broker)

    def __repr__(self):
        return '<{cls} channel={chan!r}>'.format(
            cls=self.__class__.__name__, chan=self._channel)

    def _on_channel_closed(self, _channel, reason):
        # enter the closed state
        self._closed = reason
        # errback all pending calls
        for d in self._calls:
            d.errback(self._closed)
        # errback all pending deliveries
        for d in self._deliveries.values():
            d.errback(self._closed)
        # close all open queues
        for consumer in self._consumers.values():
            consumer.close(self._closed)
        # release references to stored objects
        self._calls = set()
        self._deliveries = {}
        self._consumers = {}
        self.on_closed.callback(self._closed)

    def _on_consumer_cancelled_by_broker(self, method_frame):
        """Called by impl when broker cancels consumer via Basic.Cancel.

        This is a RabbitMQ-specific feature. The circumstances include deletion
        of queue being consumed as well as failure of a HA node responsible for
        the queue being consumed.

        :param pika.frame.Method method_frame: method frame with the
            `spec.Basic.Cancel` method

        """
        return self._on_consumer_cancelled(method_frame)

    def _on_consumer_cancelled(self, frame):
        """Called when the broker cancels a consumer via Basic.Cancel or when
        the broker responds to a Basic.Cancel request by Basic.CancelOk.

        :param pika.frame.Method frame: method frame with the
            `spec.Basic.Cancel` or `spec.Basic.CancelOk` method

        """
        consumer_tag = frame.method.consumer_tag
        if consumer_tag not in self._consumers:
            # Could be cancelled by user or broker earlier
            LOGGER.warning('basic_cancel - consumer not found: %s',
                           consumer_tag)
            return frame
        self._consumers[consumer_tag].close(exceptions.ConsumerCancelled())
        del self._consumers[consumer_tag]
        # Remove from the queue-to-ctags index:
        for ctags in self._queue_name_to_consumer_tags.values():
            try:
                ctags.remove(consumer_tag)
            except KeyError:
                continue
        return frame

    def _on_getempty(self, _method_frame):
        """Callback the Basic.Get deferred with None.
        """
        if self._basic_get_deferred is None:
            LOGGER.warning("Got Basic.GetEmpty but no Basic.Get calls "
                           "were pending.")
            return
        self._basic_get_deferred.callback(None)

    def _wrap_channel_method(self, name):
        """Wrap Pika's Channel method to make it return a Deferred that fires
        when the method completes and errbacks if the channel gets closed. If
        the original method's callback would receive more than one argument,
        the Deferred fires with a tuple of argument values.

        """
        method = getattr(self._channel, name)

        @functools.wraps(method)
        def wrapped(*args, **kwargs):
            if self._closed:
                return defer.fail(self._closed)

            d = defer.Deferred()
            self._calls.add(d)
            d.addCallback(self._clear_call, d)

            def single_argument(*args):
                """
                Make sure that the deferred is called with a single argument.
                In case the original callback fires with more than one, convert
                to a tuple.
                """
                if len(args) > 1:
                    d.callback(tuple(args))
                else:
                    d.callback(*args)

            kwargs['callback'] = single_argument

            try:
                method(*args, **kwargs)
            except Exception:  # pylint: disable=W0703
                return defer.fail()
            return d

        return wrapped

    def _clear_call(self, ret, d):
        self._calls.discard(d)
        return ret

    # Public Channel attributes

    @property
    def channel_number(self):
        return self._channel.channel_number

    @property
    def connection(self):
        return self._channel.connection

    @property
    def is_closed(self):
        """Returns True if the channel is closed.

        :rtype: bool

        """
        return self._channel.is_closed

    @property
    def is_closing(self):
        """Returns True if client-initiated closing of the channel is in
        progress.

        :rtype: bool

        """
        return self._channel.is_closing

    @property
    def is_open(self):
        """Returns True if the channel is open.

        :rtype: bool

        """
        return self._channel.is_open

    @property
    def flow_active(self):
        return self._channel.flow_active

    @property
    def consumer_tags(self):
        return self._channel.consumer_tags

    # Deferred-equivalents of public Channel methods

    def callback_deferred(self, deferred, replies):
        """Pass in a Deferred and a list replies from the RabbitMQ broker which
        you'd like the Deferred to be callbacked on with the frame as callback
        value.

        :param Deferred deferred: The Deferred to callback
        :param list replies: The replies to callback on

        """
        self._channel.add_callback(deferred.callback, replies)

    # Public Channel methods

    def add_on_return_callback(self, callback):
        """Pass a callback function that will be called when a published
        message is rejected and returned by the server via `Basic.Return`.

        :param callable callback: The method to call on callback with the
            message as only argument. The message is a named tuple with
            the following attributes
            - channel: this TwistedChannel
            - method: pika.spec.Basic.Return
            - properties: pika.spec.BasicProperties
            - body: bytes
        """
        self._channel.add_on_return_callback(
            lambda _channel, method, properties, body: callback(
                ReceivedMessage(
                    channel=self,
                    method=method,
                    properties=properties,
                    body=body,
                )
            )
        )

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
        return self._channel.basic_ack(
            delivery_tag=delivery_tag, multiple=multiple)

    def basic_cancel(self, consumer_tag=''):
        """This method cancels a consumer. This does not affect already
        delivered messages, but it does mean the server will not send any more
        messages for that consumer. The client may receive an arbitrary number
        of messages in between sending the cancel method and receiving the
        cancel-ok reply. It may also be sent from the server to the client in
        the event of the consumer being unexpectedly cancelled (i.e. cancelled
        for any reason other than the server receiving the corresponding
        basic.cancel from the client). This allows clients to be notified of
        the loss of consumers due to events such as queue deletion.

        This method wraps :meth:`Channel.basic_cancel
        <pika.channel.Channel.basic_cancel>` and closes any deferred queue
        associated with that consumer.

        :param str consumer_tag: Identifier for the consumer
        :returns: Deferred that fires on the Basic.CancelOk response
        :rtype: Deferred
        :raises ValueError:

        """
        wrapped = self._wrap_channel_method('basic_cancel')
        d = wrapped(consumer_tag=consumer_tag)
        return d.addCallback(self._on_consumer_cancelled)

    def basic_consume(self,
                      queue,
                      auto_ack=False,
                      exclusive=False,
                      consumer_tag=None,
                      arguments=None):
        """Consume from a server queue.

        Sends the AMQP 0-9-1 command Basic.Consume to the broker and binds
        messages for the consumer_tag to a
        :class:`ClosableDeferredQueue`. If you do not pass in a
        consumer_tag, one will be automatically generated for you.

        For more information on basic_consume, see:
        Tutorial 2 at http://www.rabbitmq.com/getstarted.html
        http://www.rabbitmq.com/confirms.html
        http://www.rabbitmq.com/amqp-0-9-1-reference.html#basic.consume

        :param str queue: The queue to consume from. Use the empty string to
            specify the most recent server-named queue for this channel.
        :param bool auto_ack: if set to True, automatic acknowledgement mode
            will be used (see http://www.rabbitmq.com/confirms.html). This
            corresponds with the 'no_ack' parameter in the basic.consume AMQP
            0.9.1 method
        :param bool exclusive: Don't allow other consumers on the queue
        :param str consumer_tag: Specify your own consumer tag
        :param dict arguments: Custom key/value pair arguments for the consumer
        :returns: Deferred that fires with a tuple
            ``(queue_object, consumer_tag)``. The Deferred will errback with an
            instance of :class:`exceptions.ChannelClosed` if the call fails.
            The queue object is an instance of :class:`ClosableDeferredQueue`,
            where data received from the queue will be stored. Clients should
            use its :meth:`get() <ClosableDeferredQueue.get>` method to fetch
            an individual message, which will return a Deferred firing with a
            namedtuple whose attributes are:
            - channel: this TwistedChannel
            - method: pika.spec.Basic.Deliver
            - properties: pika.spec.BasicProperties
            - body: bytes
        :rtype: Deferred

        """
        if self._closed:
            return defer.fail(self._closed)

        queue_obj = ClosableDeferredQueue()
        d = defer.Deferred()
        self._calls.add(d)

        def on_consume_ok(frame):
            consumer_tag = frame.method.consumer_tag
            self._queue_name_to_consumer_tags.setdefault(
                queue, set()).add(consumer_tag)
            self._consumers[consumer_tag] = queue_obj
            self._calls.discard(d)
            d.callback((queue_obj, consumer_tag))

        def on_message_callback(_channel, method, properties, body):
            """Add the ReceivedMessage to the queue, while replacing the
            channel implementation.
            """
            queue_obj.put(
                ReceivedMessage(
                    channel=self,
                    method=method,
                    properties=properties,
                    body=body,
                ))

        try:
            self._channel.basic_consume(
                queue=queue,
                on_message_callback=on_message_callback,
                auto_ack=auto_ack,
                exclusive=exclusive,
                consumer_tag=consumer_tag,
                arguments=arguments,
                callback=on_consume_ok,
            )
        except Exception:  # pylint: disable=W0703
            return defer.fail()

        return d

    def basic_get(self, queue, auto_ack=False):
        """Get a single message from the AMQP broker.

        Will return If the queue is empty, it will return None.
        If you want to
        be notified of Basic.GetEmpty, use the Channel.add_callback method
        adding your Basic.GetEmpty callback which should expect only one
        parameter, frame. Due to implementation details, this cannot be called
        a second time until the callback is executed.  For more information on
        basic_get and its parameters, see:

        http://www.rabbitmq.com/amqp-0-9-1-reference.html#basic.get

        This method wraps :meth:`Channel.basic_get
        <pika.channel.Channel.basic_get>`.

        :param str queue: The queue from which to get a message. Use the empty
                      string to specify the most recent server-named queue
                      for this channel.
        :param bool auto_ack: Tell the broker to not expect a reply
        :returns: Deferred that fires with a namedtuple whose attributes are:
             - channel: this TwistedChannel
             - method: pika.spec.Basic.GetOk
             - properties: pika.spec.BasicProperties
             - body: bytes
            If the queue is empty, None will be returned.
        :rtype: Deferred
        :raises pika.exceptions.DuplicateGetOkCallback:

        """
        if self._basic_get_deferred is not None:
            raise exceptions.DuplicateGetOkCallback()

        def create_namedtuple(result):
            if result is None:
                return None
            _channel, method, properties, body = result
            return ReceivedMessage(
                channel=self,
                method=method,
                properties=properties,
                body=body,
            )

        def cleanup_attribute(result):
            self._basic_get_deferred = None
            return result

        d = self._wrap_channel_method("basic_get")(
            queue=queue, auto_ack=auto_ack)
        d.addCallback(create_namedtuple)
        d.addBoth(cleanup_attribute)
        self._basic_get_deferred = d
        return d

    def basic_nack(self, delivery_tag=None, multiple=False, requeue=True):
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
                             requeue attempt fails the messages are discarded
                             or dead-lettered.

        """
        return self._channel.basic_nack(
            delivery_tag=delivery_tag,
            multiple=multiple,
            requeue=requeue,
        )

    def basic_publish(self,
                      exchange,
                      routing_key,
                      body,
                      properties=None,
                      mandatory=False):
        """Publish to the channel with the given exchange, routing key and body.

        This method wraps :meth:`Channel.basic_publish
        <pika.channel.Channel.basic_publish>`, but makes sure the channel is
        not closed before publishing.

        For more information on basic_publish and what the parameters do, see:

        http://www.rabbitmq.com/amqp-0-9-1-reference.html#basic.publish

        :param str exchange: The exchange to publish to
        :param str routing_key: The routing key to bind on
        :param bytes body: The message body
        :param pika.spec.BasicProperties properties: Basic.properties
        :param bool mandatory: The mandatory flag
        :returns: A Deferred that fires with the result of the channel's
            basic_publish.
        :rtype: Deferred
        :raises UnroutableError: raised when a message published in
            publisher-acknowledgments mode (see
            `BlockingChannel.confirm_delivery`) is returned via `Basic.Return`
            followed by `Basic.Ack`.
        :raises NackError: raised when a message published in
            publisher-acknowledgements mode is Nack'ed by the broker. See
            `BlockingChannel.confirm_delivery`.

        """
        if self._closed:
            return defer.fail(self._closed)
        result = self._channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            properties=properties,
            mandatory=mandatory)
        if not self._delivery_confirmation:
            return defer.succeed(result)
        else:
            # See http://www.rabbitmq.com/confirms.html#publisher-confirms
            self._delivery_message_id += 1
            self._deliveries[self._delivery_message_id] = defer.Deferred()
            return self._deliveries[self._delivery_message_id]

    def basic_qos(self, prefetch_size=0, prefetch_count=0, global_qos=False):
        """Specify quality of service. This method requests a specific quality
        of service. The QoS can be specified for the current channel or for all
        channels on the connection. The client can request that messages be
        sent in advance so that when the client finishes processing a message,
        the following message is already held locally, rather than needing to
        be sent down the channel. Prefetching gives a performance improvement.

        :param int prefetch_size:  This field specifies the prefetch window
                                   size. The server will send a message in
                                   advance if it is equal to or smaller in size
                                   than the available prefetch size (and also
                                   falls into other prefetch limits). May be
                                   set to zero, meaning "no specific limit",
                                   although other prefetch limits may still
                                   apply. The prefetch-size is ignored by
                                   consumers who have enabled the no-ack
                                   option.
        :param int prefetch_count: Specifies a prefetch window in terms of
                                   whole messages. This field may be used in
                                   combination with the prefetch-size field; a
                                   message will only be sent in advance if both
                                   prefetch windows (and those at the channel
                                   and connection level) allow it. The
                                   prefetch-count is ignored by consumers who
                                   have enabled the no-ack option.
        :param bool global_qos:    Should the QoS apply to all channels on the
                                   connection.
        :returns: Deferred that fires on the Basic.QosOk response
        :rtype: Deferred

        """
        return self._wrap_channel_method("basic_qos")(
            prefetch_size=prefetch_size,
            prefetch_count=prefetch_count,
            global_qos=global_qos,
        )

    def basic_reject(self, delivery_tag, requeue=True):
        """Reject an incoming message. This method allows a client to reject a
        message. It can be used to interrupt and cancel large incoming
        messages, or return untreatable messages to their original queue.

        :param integer delivery_tag: int/long The server-assigned delivery tag
        :param bool requeue: If requeue is true, the server will attempt to
                             requeue the message. If requeue is false or the
                             requeue attempt fails the messages are discarded
                             or dead-lettered.
        :raises: TypeError

        """
        return self._channel.basic_reject(
            delivery_tag=delivery_tag, requeue=requeue)

    def basic_recover(self, requeue=False):
        """This method asks the server to redeliver all unacknowledged messages
        on a specified channel. Zero or more messages may be redelivered. This
        method replaces the asynchronous Recover.

        :param bool requeue: If False, the message will be redelivered to the
                             original recipient. If True, the server will
                             attempt to requeue the message, potentially then
                             delivering it to an alternative subscriber.
        :returns: Deferred that fires on the Basic.RecoverOk response
        :rtype: Deferred

        """
        return self._wrap_channel_method("basic_recover")(requeue=requeue)

    def close(self, reply_code=0, reply_text="Normal shutdown"):
        """Invoke a graceful shutdown of the channel with the AMQP Broker.

        If channel is OPENING, transition to CLOSING and suppress the incoming
        Channel.OpenOk, if any.

        :param int reply_code: The reason code to send to broker
        :param str reply_text: The reason text to send to broker

        :raises ChannelWrongStateError: if channel is closed or closing

        """
        return self._channel.close(reply_code=reply_code, reply_text=reply_text)

    def confirm_delivery(self):
        """Turn on Confirm mode in the channel. Pass in a callback to be
        notified by the Broker when a message has been confirmed as received or
        rejected (Basic.Ack, Basic.Nack) from the broker to the publisher.

        For more information see:
            http://www.rabbitmq.com/confirms.html#publisher-confirms

        :returns: Deferred that fires on the Confirm.SelectOk response
        :rtype: Deferred

        """
        if self._delivery_confirmation:
            LOGGER.error('confirm_delivery: confirmation was already enabled.')
            return defer.succeed(None)
        wrapped = self._wrap_channel_method('confirm_delivery')
        d = wrapped(ack_nack_callback=self._on_delivery_confirmation)

        def set_delivery_confirmation(result):
            self._delivery_confirmation = True
            self._delivery_message_id = 0
            LOGGER.debug("Delivery confirmation enabled.")
            return result

        d.addCallback(set_delivery_confirmation)
        # Unroutable messages returned after this point will be in the context
        # of publisher acknowledgments
        self._channel.add_on_return_callback(self._on_puback_message_returned)
        return d

    def _on_delivery_confirmation(self, method_frame):
        """Invoked by pika when RabbitMQ responds to a Basic.Publish RPC
        command, passing in either a Basic.Ack or Basic.Nack frame with
        the delivery tag of the message that was published. The delivery tag
        is an integer counter indicating the message number that was sent
        on the channel via Basic.Publish. Here we're just doing house keeping
        to keep track of stats and remove message numbers that we expect
        a delivery confirmation of from the list used to keep track of messages
        that are pending confirmation.

        :param pika.frame.Method method_frame: Basic.Ack or Basic.Nack frame

        """
        delivery_tag = method_frame.method.delivery_tag
        if delivery_tag not in self._deliveries:
            LOGGER.error("Delivery tag %s not found in the pending deliveries",
                         delivery_tag)
            return
        if method_frame.method.multiple:
            tags = [tag for tag in self._deliveries if tag <= delivery_tag]
            tags.sort()
        else:
            tags = [delivery_tag]
        for tag in tags:
            d = self._deliveries[tag]
            del self._deliveries[tag]
            if isinstance(method_frame.method, pika.spec.Basic.Nack):
                # Broker was unable to process the message due to internal
                # error
                LOGGER.warning(
                    "Message was Nack'ed by broker: nack=%r; channel=%s;",
                    method_frame.method, self.channel_number)
                if self._puback_return is not None:
                    returned_messages = [self._puback_return]
                    self._puback_return = None
                else:
                    returned_messages = []
                d.errback(exceptions.NackError(returned_messages))
            else:
                assert isinstance(method_frame.method, pika.spec.Basic.Ack)
                if self._puback_return is not None:
                    # Unroutable message was returned
                    returned_messages = [self._puback_return]
                    self._puback_return = None
                    d.errback(exceptions.UnroutableError(returned_messages))
                else:
                    d.callback(method_frame.method)

    def _on_puback_message_returned(self, channel, method, properties, body):
        """Called as the result of Basic.Return from broker in
        publisher-acknowledgements mode. Saves the info as a ReturnedMessage
        instance in self._puback_return.

        :param pika.Channel channel: our self._impl channel
        :param pika.spec.Basic.Return method:
        :param pika.spec.BasicProperties properties: message properties
        :param bytes body: returned message body; empty string if no body

        """
        assert isinstance(method, spec.Basic.Return), method
        assert isinstance(properties, spec.BasicProperties), properties

        LOGGER.warning(
            "Published message was returned: _delivery_confirmation=%s; "
            "channel=%s; method=%r; properties=%r; body_size=%d; "
            "body_prefix=%.255r", self._delivery_confirmation,
            channel.channel_number, method, properties,
            len(body) if body is not None else None, body)

        self._puback_return = ReceivedMessage(channel=self,
                method=method, properties=properties, body=body)

    def exchange_bind(self, destination, source, routing_key='',
                      arguments=None):
        """Bind an exchange to another exchange.

        :param str destination: The destination exchange to bind
        :param str source: The source exchange to bind to
        :param str routing_key: The routing key to bind on
        :param dict arguments: Custom key/value pair arguments for the binding
        :raises ValueError:
        :returns: Deferred that fires on the Exchange.BindOk response
        :rtype: Deferred

        """
        return self._wrap_channel_method("exchange_bind")(
            destination=destination,
            source=source,
            routing_key=routing_key,
            arguments=arguments,
        )

    def exchange_declare(self,
                         exchange,
                         exchange_type=ExchangeType.direct,
                         passive=False,
                         durable=False,
                         auto_delete=False,
                         internal=False,
                         arguments=None):
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
        :param bool passive: Perform a declare or just check to see if it
            exists
        :param bool durable: Survive a reboot of RabbitMQ
        :param bool auto_delete: Remove when no more queues are bound to it
        :param bool internal: Can only be published to by other exchanges
        :param dict arguments: Custom key/value pair arguments for the exchange
        :returns: Deferred that fires on the Exchange.DeclareOk response
        :rtype: Deferred
        :raises ValueError:

        """
        return self._wrap_channel_method("exchange_declare")(
            exchange=exchange,
            exchange_type=exchange_type,
            passive=passive,
            durable=durable,
            auto_delete=auto_delete,
            internal=internal,
            arguments=arguments,
        )

    def exchange_delete(self, exchange=None, if_unused=False):
        """Delete the exchange.

        :param str exchange: The exchange name
        :param bool if_unused: only delete if the exchange is unused
        :returns: Deferred that fires on the Exchange.DeleteOk response
        :rtype: Deferred
        :raises ValueError:

        """
        return self._wrap_channel_method("exchange_delete")(
            exchange=exchange,
            if_unused=if_unused,
        )

    def exchange_unbind(self,
                        destination=None,
                        source=None,
                        routing_key='',
                        arguments=None):
        """Unbind an exchange from another exchange.

        :param str destination: The destination exchange to unbind
        :param str source: The source exchange to unbind from
        :param str routing_key: The routing key to unbind
        :param dict arguments: Custom key/value pair arguments for the binding
        :returns: Deferred that fires on the Exchange.UnbindOk response
        :rtype: Deferred
        :raises ValueError:

        """
        return self._wrap_channel_method("exchange_unbind")(
            destination=destination,
            source=source,
            routing_key=routing_key,
            arguments=arguments,
        )

    def flow(self, active):
        """Turn Channel flow control off and on.

        Returns a Deferred that will fire with a bool indicating the channel
        flow state. For more information, please reference:

        http://www.rabbitmq.com/amqp-0-9-1-reference.html#channel.flow

        :param bool active: Turn flow on or off
        :returns: Deferred that fires with the channel flow state
        :rtype: Deferred
        :raises ValueError:

        """
        return self._wrap_channel_method("flow")(active=active)

    def open(self):
        """Open the channel"""
        return self._channel.open()

    def queue_bind(self, queue, exchange, routing_key=None, arguments=None):
        """Bind the queue to the specified exchange

        :param str queue: The queue to bind to the exchange
        :param str exchange: The source exchange to bind to
        :param str routing_key: The routing key to bind on
        :param dict arguments: Custom key/value pair arguments for the binding
        :returns: Deferred that fires on the Queue.BindOk response
        :rtype: Deferred
        :raises ValueError:

        """
        return self._wrap_channel_method("queue_bind")(
            queue=queue,
            exchange=exchange,
            routing_key=routing_key,
            arguments=arguments,
        )

    def queue_declare(self,
                      queue,
                      passive=False,
                      durable=False,
                      exclusive=False,
                      auto_delete=False,
                      arguments=None):
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
        :returns: Deferred that fires on the Queue.DeclareOk response
        :rtype: Deferred
        :raises ValueError:

        """
        return self._wrap_channel_method("queue_declare")(
            queue=queue,
            passive=passive,
            durable=durable,
            exclusive=exclusive,
            auto_delete=auto_delete,
            arguments=arguments,
        )

    def queue_delete(self, queue, if_unused=False, if_empty=False):
        """Delete a queue from the broker.


        This method wraps :meth:`Channel.queue_delete
        <pika.channel.Channel.queue_delete>`, and removes the reference to the
        queue object after it gets deleted on the server.

        :param str queue: The queue to delete
        :param bool if_unused: only delete if it's unused
        :param bool if_empty: only delete if the queue is empty
        :returns: Deferred that fires on the Queue.DeleteOk response
        :rtype: Deferred
        :raises ValueError:

        """
        wrapped = self._wrap_channel_method('queue_delete')
        d = wrapped(queue=queue, if_unused=if_unused, if_empty=if_empty)

        def _clear_consumer(ret, queue_name):
            for consumer_tag in list(
                    self._queue_name_to_consumer_tags.get(queue_name, set())):
                self._consumers[consumer_tag].close(
                    exceptions.ConsumerCancelled(
                        "Queue %s was deleted." % queue_name))
                del self._consumers[consumer_tag]
                self._queue_name_to_consumer_tags[queue_name].remove(
                    consumer_tag)
            return ret

        return d.addCallback(_clear_consumer, queue)

    def queue_purge(self, queue):
        """Purge all of the messages from the specified queue

        :param str queue: The queue to purge
        :returns: Deferred that fires on the Queue.PurgeOk response
        :rtype: Deferred
        :raises ValueError:

        """
        return self._wrap_channel_method("queue_purge")(queue=queue)

    def queue_unbind(self,
                     queue,
                     exchange=None,
                     routing_key=None,
                     arguments=None):
        """Unbind a queue from an exchange.

        :param str queue: The queue to unbind from the exchange
        :param str exchange: The source exchange to bind from
        :param str routing_key: The routing key to unbind
        :param dict arguments: Custom key/value pair arguments for the binding
        :returns: Deferred that fires on the Queue.UnbindOk response
        :rtype: Deferred
        :raises ValueError:

        """
        return self._wrap_channel_method("queue_unbind")(
            queue=queue,
            exchange=exchange,
            routing_key=routing_key,
            arguments=arguments,
        )

    def tx_commit(self):
        """Commit a transaction.

        :returns: Deferred that fires on the Tx.CommitOk response
        :rtype: Deferred
        :raises ValueError:

        """
        return self._wrap_channel_method("tx_commit")()

    def tx_rollback(self):
        """Rollback a transaction.

        :returns: Deferred that fires on the Tx.RollbackOk response
        :rtype: Deferred
        :raises ValueError:

        """
        return self._wrap_channel_method("tx_rollback")()

    def tx_select(self):
        """Select standard transaction mode. This method sets the channel to use
        standard transactions. The client must use this method at least once on
        a channel before using the Commit or Rollback methods.

        :returns: Deferred that fires on the Tx.SelectOk response
        :rtype: Deferred
        :raises ValueError:

        """
        return self._wrap_channel_method("tx_select")()


class _TwistedConnectionAdapter(pika.connection.Connection):
    """A Twisted-specific implementation of a Pika Connection.

    NOTE: since `base_connection.BaseConnection`'s primary responsibility is
    management of the transport, we use `pika.connection.Connection` directly
    as our base class because this adapter uses a different transport
    management strategy.

    """

    def __init__(self, parameters, on_open_callback, on_open_error_callback,
                 on_close_callback, custom_reactor):
        super(_TwistedConnectionAdapter, self).__init__(
            parameters=parameters,
            on_open_callback=on_open_callback,
            on_open_error_callback=on_open_error_callback,
            on_close_callback=on_close_callback,
            internal_connection_workflow=False)

        self._reactor = custom_reactor or reactor
        self._transport = None  # to be provided by `connection_made()`

    def _adapter_call_later(self, delay, callback):
        """Implement
        :py:meth:`pika.connection.Connection._adapter_call_later()`.

        """
        check_callback_arg(callback, 'callback')
        return _TimerHandle(self._reactor.callLater(delay, callback))

    def _adapter_remove_timeout(self, timeout_id):
        """Implement
        :py:meth:`pika.connection.Connection._adapter_remove_timeout()`.

        """
        timeout_id.cancel()

    def _adapter_add_callback_threadsafe(self, callback):
        """Implement
        :py:meth:`pika.connection.Connection._adapter_add_callback_threadsafe()`.

        """
        check_callback_arg(callback, 'callback')
        self._reactor.callFromThread(callback)

    def _adapter_connect_stream(self):
        """Implement pure virtual
        :py:ref:meth:`pika.connection.Connection._adapter_connect_stream()`
         method.

        NOTE: This should not be called due to our initialization of Connection
        via `internal_connection_workflow=False`
        """
        raise NotImplementedError

    def _adapter_disconnect_stream(self):
        """Implement pure virtual
        :py:ref:meth:`pika.connection.Connection._adapter_disconnect_stream()`
         method.

        """
        self._transport.loseConnection()

    def _adapter_emit_data(self, data):
        """Implement pure virtual
        :py:ref:meth:`pika.connection.Connection._adapter_emit_data()` method.

        """
        self._transport.write(data)

    def connection_made(self, transport):
        """Introduces transport to protocol after transport is connected.

        :param twisted.internet.interfaces.ITransport transport:
        :raises Exception: Exception-based exception on error

        """
        self._transport = transport
        # Let connection know that stream is available
        self._on_stream_connected()

    def connection_lost(self, error):
        """Called upon loss or closing of TCP connection.

        NOTE: `connection_made()` and `connection_lost()` are each called just
        once and in that order. All other callbacks are called between them.

        :param Failure: A Twisted Failure instance wrapping an exception.

        """
        self._transport = None
        error = error.value  # drop the Failure wrapper
        if isinstance(error, twisted_error.ConnectionDone):
            self._error = error
            error = None
        LOGGER.log(logging.DEBUG if error is None else logging.ERROR,
                   'connection_lost: %r', error)
        self._on_stream_terminated(error)

    def data_received(self, data):
        """Called to deliver incoming data from the server to the protocol.

        :param data: Non-empty data bytes.
        :raises Exception: Exception-based exception on error

        """
        self._on_data_available(data)


class TwistedProtocolConnection(protocol.Protocol):
    """A Pika-specific implementation of a Twisted Protocol. Allows using
    Twisted's non-blocking connectTCP/connectSSL methods for connecting to the
    server.

    TwistedProtocolConnection objects have a `ready` instance variable that's a
    Deferred which fires when the connection is ready to be used (the initial
    AMQP handshaking has been done). You *have* to wait for this Deferred to
    fire before requesting a channel.

    Once the connection is ready, you will be able to use the `closed` instance
    variable: a Deferred which fires when the connection is closed.

    Since it's Twisted handling connection establishing it does not accept
    connect callbacks, you have to implement that within Twisted. Also remember
    that the host, port and ssl values of the connection parameters are ignored
    because, yet again, it's Twisted who manages the connection.

    """

    def __init__(self, parameters=None, custom_reactor=None):
        self.ready = defer.Deferred()
        self.ready.addCallback(lambda _: self.connectionReady())
        self.closed = None
        self._impl = _TwistedConnectionAdapter(
            parameters=parameters,
            on_open_callback=self._on_connection_ready,
            on_open_error_callback=self._on_connection_failed,
            on_close_callback=self._on_connection_closed,
            custom_reactor=custom_reactor,
        )
        self._calls = set()

    def channel(self, channel_number=None):  # pylint: disable=W0221
        """Create a new channel with the next available channel number or pass
        in a channel number to use. Must be non-zero if you would like to
        specify but it is recommended that you let Pika manage the channel
        numbers.

        :param int channel_number: The channel number to use, defaults to the
                                   next available.
        :returns: a Deferred that fires with an instance of a wrapper around
            the Pika Channel class.
        :rtype: Deferred

        """
        d = defer.Deferred()
        self._impl.channel(channel_number, d.callback)
        self._calls.add(d)
        d.addCallback(self._clear_call, d)
        return d.addCallback(TwistedChannel)

    @property
    def is_open(self):
        # For compatibility with previous releases.
        return self._impl.is_open

    @property
    def is_closed(self):
        # For compatibility with previous releases.
        return self._impl.is_closed

    def close(self, reply_code=200, reply_text='Normal shutdown'):
        if not self._impl.is_closed:
            self._impl.close(reply_code, reply_text)
        return self.closed

    # IProtocol methods

    def dataReceived(self, data):
        # Pass the bytes to Pika for parsing
        self._impl.data_received(data)

    def connectionLost(self, reason=protocol.connectionDone):
        self._impl.connection_lost(reason)
        # Let the caller know there's been an error
        d, self.ready = self.ready, None
        if d:
            d.errback(reason)

    def makeConnection(self, transport):
        self._impl.connection_made(transport)
        protocol.Protocol.makeConnection(self, transport)

    # Our own methods

    def connectionReady(self):
        """This method will be called when the underlying connection is ready.
        """
        return self

    def _on_connection_ready(self, _connection):
        d, self.ready = self.ready, None
        if d:
            self.closed = defer.Deferred()
            d.callback(None)

    def _on_connection_failed(self, _connection, _error_message=None):
        d, self.ready = self.ready, None
        if d:
            attempts = self._impl.params.connection_attempts
            exc = exceptions.AMQPConnectionError(attempts)
            d.errback(exc)

    def _on_connection_closed(self, _connection, exception):
        # errback all pending calls
        for d in self._calls:
            d.errback(exception)
        self._calls = set()

        d, self.closed = self.closed, None
        if d:
            if isinstance(exception, Failure):
                # Calling `callback` with a Failure instance will trigger the
                # errback path.
                exception = exception.value
            d.callback(exception)

    def _clear_call(self, ret, d):
        self._calls.discard(d)
        return ret


class _TimerHandle(nbio_interface.AbstractTimerReference):
    """This module's adaptation of `nbio_interface.AbstractTimerReference`.

    """

    def __init__(self, handle):
        """

        :param twisted.internet.base.DelayedCall handle:
        """
        self._handle = handle

    def cancel(self):
        if self._handle is not None:
            try:
                self._handle.cancel()
            except (twisted_error.AlreadyCalled,
                    twisted_error.AlreadyCancelled):
                pass

            self._handle = None
