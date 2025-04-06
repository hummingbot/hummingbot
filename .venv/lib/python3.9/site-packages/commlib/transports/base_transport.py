import logging

from commlib.connection import BaseConnectionParameters

transport_logger = None


class BaseTransport:
    """BaseTransport.
    The `BaseTransport` class provides a base implementation for a transport
    layer in the `commlib` library. It defines common properties and methods
    that should be implemented by concrete transport implementations.
    """

    _connected = False

    @classmethod
    def logger(cls) -> logging.Logger:
        global transport_logger
        if transport_logger is None:
            transport_logger = logging.getLogger(__name__)
        return transport_logger

    def __init__(self,
                 conn_params: BaseConnectionParameters,
                 debug: bool = False):
        """__init__.
        Initializes a new instance of the `BaseTransport` class.

        Args:
            conn_params (BaseConnectionParameters): The connection parameters to use for the transport.
            debug (bool, optional): Whether to enable debug logging for the transport. Defaults to False.
        """

        self._conn_params = conn_params
        self._debug = debug

    @property
    def log(self):
        return self.logger()

    @property
    def debug(self):
        return self._debug

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self):
        raise NotImplementedError()

    def disconnect(self):
        raise NotImplementedError()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def loop_forever(self):
        raise NotImplementedError()
