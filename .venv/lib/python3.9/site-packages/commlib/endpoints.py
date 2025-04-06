import logging
from enum import Enum

from commlib.compression import CompressionType
from commlib.connection import BaseConnectionParameters
from commlib.serializer import JSONSerializer, Serializer
from commlib.transports.base_transport import BaseTransport

e_logger = None


class EndpointState(Enum):
    DISCONNECTED = 0
    CONNECTED = 1
    CONNECTING = 2
    DISCONNECTING = 3


class BaseEndpoint:
    """
    Defines the base class for all endpoints in the commlib library.

    The `BaseEndpoint` class provides common functionality for all endpoint types, such as:
    - Logging
    - Serialization
    - Connection parameters
    - Compression

    Subclasses of `BaseEndpoint` should implement the specific functionality for their
    endpoint type, such as RPC, publish/subscribe, etc.
    """

    _transport: BaseTransport = None

    @classmethod
    def logger(cls) -> logging.Logger:
        global e_logger
        if e_logger is None:
            e_logger = logging.getLogger(__name__)
        return e_logger

    def __init__(
        self,
        debug: bool = False,
        serializer: Serializer = JSONSerializer,
        conn_params: BaseConnectionParameters = None,
        compression: CompressionType = CompressionType.NO_COMPRESSION):
        """__init__.
        Initializes a new instance of the `BaseEndpoint` class.

        Args:
            debug (bool, optional): A flag indicating whether debug mode is enabled. Defaults to `False`.
            serializer (Serializer, optional): The serializer to use for data serialization. Defaults to `JSONSerializer`.
            conn_params (BaseConnectionParameters, optional): The connection parameters to use for the transport. Defaults to `None`.
            compression (CompressionType, optional): The compression type to use for the transport. Defaults to `CompressionType.NO_COMPRESSION`.
        """

        self._debug = debug
        self._serializer = serializer
        self._compression = compression
        self._conn_params = conn_params
        self._state = EndpointState.DISCONNECTED

    @property
    def log(self):
        return self.logger()

    @property
    def debug(self):
        return self._debug

    def run(self):
        """
        Starts the subscriber and connects to the transport if it is not already connected.

        If the transport is not initialized, raises a `RuntimeError`.

        If the transport is not connected and the subscriber is not in the `CONNECTED` or `CONNECTING` state, it starts the transport.

        Finally, it sets the subscriber state to `CONNECTED`.
        """

        if self._transport is None:
            raise RuntimeError(
                f"Transport not initialized - cannot run {self.__class__.__name__}")
        if not self._transport.is_connected and \
            self._state not in (EndpointState.CONNECTED,
                                EndpointState.CONNECTING):
            self._transport.start()
            self._state = EndpointState.CONNECTED
        else:
            self.logger().debug(
                f"Transport already connected - cannot run {self.__class__.__name__}")

    def stop(self) -> None:
        """
        Stops the subscriber and disconnects from the transport if it is connected.

        If the transport is not initialized, raises a `RuntimeError`.

        If the transport is connected and the subscriber is not in the `DISCONNECTED` or `DISCONNECTING` state, it stops the transport.
        """

        if self._transport is None:
            raise RuntimeError(
                f"Transport not initialized - cannot stop {self.__class__.__name__}")
        if self._transport.is_connected and \
            self._state not in (EndpointState.DISCONNECTED,
                                EndpointState.DISCONNECTING):
            self._transport.stop()
            self._state = EndpointState.DISCONNECTED
        else:
            self.logger().debug(
                f"Transport is not connected - cannot stop {self.__class__.__name__}")

    def __del__(self):
        self.stop()


class EndpointType(Enum):
    """EndpointType.
    Types of supported Endpoints.
    """

    RPCService = 1
    RPCClient = 2
    Publisher = 3
    Subscriber = 4
    ActionService = 5
    ActionClient = 6
    MPublisher = 7
    PSubscriber = 8


class TransportType(Enum):
    """TransportType.
    Types of supported Transports
    """

    AMQP = 1
    REDIS = 2
    MQTT = 3
    KAFKA = 4


def endpoint_factory(etype: EndpointType, etransport: TransportType):
    """endpoint_factory.
    Create an instance of an endpoint
        (RPCClient, RPCService, Publisher, Subscriber etc..),
        by simply giving its type and transport (MQTT, AMQP, Redis)

    Args:
        etype (EndpointType): Endpoint type
        etransport (TransportType): Transport type
    """
    if etransport == TransportType.AMQP:
        import commlib.transports.amqp as comm
    elif etransport == TransportType.REDIS:
        import commlib.transports.redis as comm
    elif etransport == TransportType.MQTT:
        import commlib.transports.mqtt as comm
    else:
        raise ValueError()
    if etype == EndpointType.RPCService:
        return comm.RPCService
    elif etype == EndpointType.RPCClient:
        return comm.RPCClient
    elif etype == EndpointType.Publisher:
        return comm.Publisher
    elif etype == EndpointType.Subscriber:
        return comm.Subscriber
    elif etype == EndpointType.ActionService:
        return comm.ActionService
    elif etype == EndpointType.ActionClient:
        return comm.ActionClient
    elif etype == EndpointType.MPublisher:
        return comm.MPublisher
    elif etype == EndpointType.PSubscriber:
        return comm.PSubscriber
