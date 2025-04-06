import logging
import time
from enum import IntEnum
from typing import List

from commlib.connection import BaseConnectionParameters
from commlib.endpoints import EndpointType, TransportType, endpoint_factory
from commlib.msg import PubSubMessage, RPCMessage

br_logger = None


class RPCBridgeType(IntEnum):
    """RPCBridgeType."""

    REDIS_TO_AMQP = 1
    AMQP_TO_REDIS = 2
    AMQP_TO_AMQP = 3
    REDIS_TO_REDIS = 4
    MQTT_TO_REDIS = 5
    MQTT_TO_AMQP = 6
    MQTT_TO_MQTT = 7
    REDIS_TO_MQTT = 8
    AMQP_TO_MQTT = 9


class TopicBridgeType(IntEnum):
    """TopicBridgeType."""

    REDIS_TO_AMQP = 1
    AMQP_TO_REDIS = 2
    AMQP_TO_AMQP = 3
    REDIS_TO_REDIS = 4
    MQTT_TO_REDIS = 5
    MQTT_TO_AMQP = 6
    MQTT_TO_MQTT = 7
    REDIS_TO_MQTT = 8
    AMQP_TO_MQTT = 9


class Bridge:
    """Bridge.
    Base Bridge Class.
    """

    @classmethod
    def logger(cls) -> logging.Logger:
        global br_logger
        if br_logger is None:
            br_logger = logging.getLogger(__name__)
        return br_logger

    def __init__(
        self,
        from_uri: str,
        to_uri: str,
        from_broker_params: BaseConnectionParameters,
        to_broker_params: BaseConnectionParameters,
        auto_transform_uris: bool = True,
        debug: bool = False,
    ):
        """__init__.

        Args:
            btype:
            debug (bool): debug
        """
        self._from_broker_params = from_broker_params
        self._to_broker_params = to_broker_params
        self._from_uri = from_uri
        self._to_uri = to_uri
        self._debug = debug
        self._auto_transform_uris = auto_transform_uris

        bA_type_str = str(type(self._from_broker_params)).split("'")[1]
        bB_type_str = str(type(self._to_broker_params)).split("'")[1]
        if "redis" in bA_type_str and "amqp" in bB_type_str:
            self._btype = RPCBridgeType.REDIS_TO_AMQP
            from_transport = TransportType.REDIS
            to_transport = TransportType.AMQP
        elif "amqp" in bA_type_str and "redis" in bB_type_str:
            self._btype = RPCBridgeType.AMQP_TO_REDIS
            from_transport = TransportType.AMQP
            to_transport = TransportType.REDIS
        elif "amqp" in bA_type_str and "amqp" in bB_type_str:
            self._btype = RPCBridgeType.AMQP_TO_AMQP
            from_transport = TransportType.AMQP
            to_transport = TransportType.AMQP
        elif "redis" in bA_type_str and "redis" in bB_type_str:
            self._btype = RPCBridgeType.REDIS_TO_REDIS
            from_transport = TransportType.REDIS
            to_transport = TransportType.REDIS
        elif "mqtt" in bA_type_str and "redis" in bB_type_str:
            self._btype = RPCBridgeType.MQTT_TO_REDIS
            from_transport = TransportType.MQTT
            to_transport = TransportType.REDIS
        elif "mqtt" in bA_type_str and "amqp" in bB_type_str:
            self._btype = RPCBridgeType.MQTT_TO_AMQP
            from_transport = TransportType.MQTT
            to_transport = TransportType.AMQP
        elif "mqtt" in bA_type_str and "mqtt" in bB_type_str:
            self._btype = RPCBridgeType.MQTT_TO_MQTT
            from_transport = TransportType.MQTT
            to_transport = TransportType.MQTT
        elif "redis" in bA_type_str and "mqtt" in bB_type_str:
            self._btype = RPCBridgeType.REDIS_TO_MQTT
            from_transport = TransportType.REDIS
            to_transport = TransportType.MQTT
        elif "amqp" in bA_type_str and "mqtt" in bB_type_str:
            self._btype = RPCBridgeType.AMQP_TO_MQTT
            from_transport = TransportType.AMQP
            to_transport = TransportType.MQTT
        self._from_transport = from_transport
        self._to_transport = to_transport

        if self._auto_transform_uris:
            self._to_uri = self._transform_uri(self._to_uri)

    @property
    def debug(self) -> bool:
        return self._debug

    @property
    def log(self) -> logging.Logger:
        return self.logger()

    def run(self):
        raise NotImplementedError()

    def run_forever(self):
        """run_forever.
        Runs the bridge implementation indefinitely, sleeping briefly between iterations.
        """

        self.run()
        while True:
            time.sleep(0.001)

    def _transform_uri(self, uri: str):
        """_transform_uri.
        Transforms the URI based on the RPCBridgeType.

        Args:
            uri (str): The URI to transform.

        Returns:
            str: The transformed URI.
        """

        if self._btype == RPCBridgeType.REDIS_TO_AMQP:
            uri = uri.replace("/", ".")
        elif self._btype == RPCBridgeType.AMQP_TO_REDIS:
            pass
        elif self._btype == RPCBridgeType.AMQP_TO_AMQP:
            pass
        elif self._btype == RPCBridgeType.REDIS_TO_REDIS:
            pass
        elif self._btype == RPCBridgeType.MQTT_TO_REDIS:
            pass
            # uri = uri.replace('/', '.')
        elif self._btype == RPCBridgeType.MQTT_TO_AMQP:
            uri = uri.replace("/", ".")
        elif self._btype == RPCBridgeType.MQTT_TO_MQTT:
            pass
        elif self._btype == RPCBridgeType.REDIS_TO_MQTT:
            uri = uri.replace(".", "/")
        elif self._btype == RPCBridgeType.AMQP_TO_MQTT:
            uri = uri.replace(".", "/")
        return uri


class RPCBridge(Bridge):
    """
    RPCBridge is a class that implements a bridge between two RPC
    (Remote Procedure Call) endpoints. It allows messages of type RPCMessage
    to be passed between the two endpoints.
    """

    def __init__(self, msg_type: RPCMessage = None, *args, **kwargs):
        """__init__.
        Initializes an RPCBridge instance.

        Args:
            msg_type (RPCMessage): The message type to use for RPC communication.
            *args: Additional positional arguments to pass to the parent class constructor.
            **kwargs: Additional keyword arguments to pass to the parent class constructor.

        The RPCBridge class is responsible for bridging two RPC (Remote Procedure Call) endpoints, allowing RPCMessage objects to be passed between them. The __init__ method sets up the necessary server and client endpoints for the bridge.
        """

        super().__init__(*args, **kwargs)
        self._msg_type = msg_type

        self._server = endpoint_factory(EndpointType.RPCService, self._from_transport)(
            conn_params=self._from_broker_params,
            msg_type=self._msg_type,
            rpc_name=self._from_uri,
            on_request=self.on_request,
            debug=self.debug,
        )
        self._client = endpoint_factory(EndpointType.RPCClient, self._to_transport)(
            rpc_name=self._to_uri,
            msg_type=self._msg_type,
            conn_params=self._to_broker_params,
            debug=self.debug,
        )

    def on_request(self, msg: RPCMessage.Request):
        """on_request.
        Handles an incoming RPC request by forwarding it to the client endpoint and returning the response.

        Args:
            msg (RPCMessage.Request): The incoming RPC request message.

        Returns:
            The response from the client endpoint.
        """

        # print(msg)
        resp = self._client.call(msg)
        return resp

    def stop(self):
        """stop.
        Stops the RPC bridge by stopping the server and client endpoints.

        This method is responsible for stopping the RPC bridge, which involves stopping the server and client
        endpoints that were started in the `run()` method. Once the bridge is stopped, it will no longer
        forward RPC requests between the server and client endpoints.
        """

        self._server.stop()
        self._client.stop()

    def run(self):
        """run.
        Starts the RPC bridge by running the server and client endpoints.

        This method is responsible for starting the RPC bridge, which involves running the server and client
        endpoints that were set up in the __init__ method. Once the bridge is started, it will begin
        forwarding RPC requests from the server endpoint to the client endpoint, and vice versa.

        The method also logs information about the bridge, including the source and destination broker
        parameters and URIs.
        """

        self._server.run()
        self._client.run()
        self.log.info(
            "Started B2B RPC Bridge "
            + f"<{self._from_broker_params.host}:"
            + f"{self._from_broker_params.port}[{self._from_uri}] "
            + f"-> {self._to_broker_params.host}:"
            + f"{self._to_broker_params.port}[{self._to_uri}.*]>"
        )


class TopicBridge(Bridge):
    """
    Represents a topic bridge that subscribes to a topic on one broker and
    publishes messages to a topic on another broker.

    The `TopicBridge` class is responsible for creating and managing the subscriber
    and publisher endpoints that are used to forward messages between two different
    message brokers. It takes in a `PubSubMessage` type that defines the message
    format to be used, and optionally a list of topic URI transformations to apply.
    """

    def __init__(self, msg_type: PubSubMessage = None, *args, **kwargs):
        """__init__.
        Initializes a PTopicBridge instance with the specified parameters.

        Args:
            msg_type (PubSubMessage): The message type to be used for the subscriber and publisher.
            uri_transform (List): A list of tuples containing the from and to strings for transforming the topic URIs.
            *args: Additional positional arguments to be passed to the parent class.
            **kwargs: Additional keyword arguments to be passed to the parent class.
        """

        super().__init__(*args, **kwargs)
        self._msg_type = msg_type

        self._sub = endpoint_factory(EndpointType.Subscriber, self._from_transport)(
            topic=self._from_uri,
            msg_type=self._msg_type,
            conn_params=self._from_broker_params,
            on_message=self.on_message,
        )
        self._pub = endpoint_factory(EndpointType.Publisher, self._to_transport)(
            topic=self._to_uri,
            msg_type=self._msg_type,
            conn_params=self._to_broker_params,
        )

    def on_message(self, msg: PubSubMessage):
        """on_message.

        Args:
            msg (PubSubMessage): Published Message
        """
        self._pub.publish(msg)

    def stop(self):
        """
        Stops the subscriber component of the topic bridge.

        This method is used to gracefully stop the subscriber component of the topic bridge,
        which is responsible for receiving messages from the source broker and forwarding
        them to the destination broker. Calling this method will cause the subscriber to
        disconnect from the source broker and stop processing incoming messages.
        """

        self._sub.stop()
        self._pub.stop()

    def run(self):
        """run.
        Runs the topic bridge, starting the subscriber and logging the bridge details.

        The `run()` method starts the subscriber and logs information about the topic bridge,
        including the host, port, and topic URIs for the from and to brokers.
        """

        self._sub.run()
        self._pub.run()
        self.log.info(
            "Started Topic B2B Bridge "
            + f"<{self._from_broker_params.host}:"
            + f"{self._from_broker_params.port}[{self._from_uri}] "
            + f"-> {self._to_broker_params.host}:"
            + f"{self._to_broker_params.port}[{self._to_uri}]>"
        )


class PTopicBridge(Bridge):
    """PTopicBridge.
    Initializes a PTopicBridge instance with the specified parameters.

    Args:
        msg_type (PubSubMessage): The message type to be used for the subscriber and publisher.
        uri_transform (List): A list of tuples containing the from and to strings for transforming the topic URIs.
        *args: Additional positional arguments to be passed to the parent class.
        **kwargs: Additional keyword arguments to be passed to the parent class.

    The constructor determines the type of the topic bridge based on the types of
    the from and to broker parameters. It then creates the subscriber and publisher
    endpoints using the appropriate endpoint factory functions.
    """

    def __init__(
        self,
        msg_type: PubSubMessage = None,
        uri_transform: List = [],
        *args,
        **kwargs):
        """
        Initializes a PTopicBridge instance with the specified parameters.

        Args:
            msg_type (PubSubMessage): The message type to be used for the subscriber and publisher.
            uri_transform (List): A list of tuples containing the from and to strings for transforming the topic URIs.
            *args: Additional positional arguments to be passed to the parent class.
            **kwargs: Additional keyword arguments to be passed to the parent class.

        The constructor determines the type of the topic bridge based on the types of
        the from and to broker parameters. It then creates the subscriber and publisher
        endpoints using the appropriate endpoint factory functions.
        """

        super().__init__(*args, **kwargs)
        self._msg_type = msg_type
        self._uri_transform = uri_transform

        bA_type_str = str(type(self._from_broker_params)).split("'")[1]
        bB_type_str = str(type(self._to_broker_params)).split("'")[1]
        if "redis" in bA_type_str and "amqp" in bB_type_str:
            self._btype = TopicBridgeType.REDIS_TO_AMQP
        elif "amqp" in bA_type_str and "redis" in bB_type_str:
            self._btype = TopicBridgeType.AMQP_TO_REDIS
        elif "amqp" in bA_type_str and "amqp" in bB_type_str:
            self._btype = TopicBridgeType.AMQP_TO_AMQP
        elif "redis" in bA_type_str and "redis" in bB_type_str:
            self._btype = TopicBridgeType.REDIS_TO_REDIS
        elif "mqtt" in bA_type_str and "redis" in bB_type_str:
            self._btype = TopicBridgeType.MQTT_TO_REDIS
        elif "mqtt" in bA_type_str and "amqp" in bB_type_str:
            self._btype = TopicBridgeType.MQTT_TO_AMQP
        elif "mqtt" in bA_type_str and "mqtt" in bB_type_str:
            self._btype = TopicBridgeType.MQTT_TO_MQTT
        elif "redis" in bA_type_str and "mqtt" in bB_type_str:
            self._btype = TopicBridgeType.REDIS_TO_MQTT
        elif "amqp" in bA_type_str and "mqtt" in bB_type_str:
            self._btype = TopicBridgeType.AMQP_TO_MQTT
        self._sub = endpoint_factory(EndpointType.PSubscriber, self._from_transport)(
            topic=self._from_uri,
            msg_type=self._msg_type,
            conn_params=self._from_broker_params,
            on_message=self.on_message,
        )
        self._pub = endpoint_factory(EndpointType.MPublisher, self._to_transport)(
            msg_type=self._msg_type,
            conn_params=self._to_broker_params,
        )

    def on_message(self, msg: PubSubMessage, topic: str):
        """on_message.
        Handles the processing of a received message from the subscriber and publishes
        it to the appropriate topic on the publisher.

        Args:
            msg (PubSubMessage): The received message from the subscriber.
            topic (str): The topic the message was received on.

        Returns:
            None
        """

        if self._to_uri != "":
            to_topic = f"{self._to_uri}.{topic}"
        else:
            to_topic = topic
        if self._auto_transform_uris:
            to_topic = self._transform_uri(to_topic)
        for tr in self._uri_transform:
            _from = tr[0]
            _to = tr[1]
            to_topic = to_topic.replace(_from, _to)
        self._pub.publish(msg, to_topic)

    def stop(self):
        """
        Stops the B2B P-Topic Bridge by stopping the subscriber and publisher.

        This method should be called to gracefully shut down the bridge and release
        any resources it is holding.
        """

        self._sub.stop()
        self._pub.stop()

    def run(self):
        """
        Starts the B2B P-Topic Bridge, connecting the subscriber to the publisher.

        The subscriber is configured with the `_from_broker_params` and `_from_uri` parameters, and the publisher is configured with the `_to_broker_params` and `_to_uri` parameters.
        """

        self._sub.run()
        self.log.info(
            "Started B2B P-Topic Bridge "
            + f"<{self._from_broker_params.host}:"
            + f"{self._from_broker_params.port}[{self._from_uri}] "
            + f"-> {self._to_broker_params.host}:"
            + f"{self._to_broker_params.port}[{self._to_uri}.*]>"
        )
