from commlib.connection import BaseConnectionParameters
from commlib.endpoints import EndpointState
from commlib.pubsub import BasePublisher, BaseSubscriber
from commlib.rpc import BaseRPCClient, BaseRPCService
from commlib.transports.base_transport import BaseTransport


class ConnectionParameters(BaseConnectionParameters):
    pass


class MockTransport(BaseTransport):
    def start(self):
        self._connected = True

    def stop(self):
        self._connected = False


class Publisher(BasePublisher):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._transport = MockTransport(self._conn_params)


class Subscriber(BaseSubscriber):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._transport = MockTransport(self._conn_params)

    def run(self) -> None:
        """
        Start the subscriber thread in the background without blocking
        the main thread.
        """
        if self._transport is None:
            raise RuntimeError(
                f"Transport not initialized - cannot run {self.__class__.__name__}")
        if not self._transport.is_connected and \
            self._state not in (EndpointState.CONNECTED,
                                EndpointState.CONNECTING):
            self._state = EndpointState.CONNECTED
        else:
            self.logger().debug(
                f"Transport already connected - cannot run {self.__class__.__name__}")

    def stop(self) -> None:
        """
        Stop the subscriber thread and disconnect the transport.
        """

        if self._t_stop_event is not None:
            self._t_stop_event.set()
        super().stop()


class RPCService(BaseRPCService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._transport = MockTransport(self._conn_params)

    def run(self) -> None:
        """
        Start the subscriber thread in the background without blocking
        the main thread.
        """
        if self._transport is None:
            raise RuntimeError(
                f"Transport not initialized - cannot run {self.__class__.__name__}")
        if not self._transport.is_connected and \
            self._state not in (EndpointState.CONNECTED,
                                EndpointState.CONNECTING):
            self._state = EndpointState.CONNECTED
        else:
            self.logger().debug(
                f"Transport already connected - cannot run {self.__class__.__name__}")

    def stop(self) -> None:
        """
        Stop the subscriber thread and disconnect the transport.
        """

        if self._t_stop_event is not None:
            self._t_stop_event.set()
        super().stop()


class RPCClient(BaseRPCClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._transport = MockTransport(self._conn_params)
