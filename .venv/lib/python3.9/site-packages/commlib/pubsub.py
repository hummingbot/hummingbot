import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Optional

from commlib.endpoints import BaseEndpoint, EndpointState
from commlib.msg import PubSubMessage
from commlib.utils import gen_random_id

pubsub_logger = None


class BasePublisher(BaseEndpoint):
    """BasePublisher."""

    @classmethod
    def logger(cls) -> logging.Logger:
        global pubsub_logger
        if pubsub_logger is None:
            pubsub_logger = logging.getLogger(__name__)
        return pubsub_logger

    def __init__(self, topic: str, msg_type: PubSubMessage = None,
                 *args, **kwargs):
        """__init__.
        Initializes a new instance of the `BaseSubscriber` class.

        Args:
            topic (str): The topic to subscribe to.
            msg_type (PubSubMessage, optional): The type of message to expect for this subscription.
            *args: Additional positional arguments to pass to the base class constructor.
            **kwargs: Additional keyword arguments to pass to the base class constructor.
        """

        super().__init__(*args, **kwargs)
        self._topic: str = topic
        self._msg_type: PubSubMessage = msg_type
        self._gen_random_id: str = gen_random_id

    @property
    def topic(self) -> str:
        """topic"""
        return self._topic

    def publish(self, msg: PubSubMessage) -> None:
        raise NotImplementedError()


class BaseSubscriber(BaseEndpoint):
    """BaseSubscriber."""

    @classmethod
    def logger(cls) -> logging.Logger:
        global pubsub_logger
        if pubsub_logger is None:
            pubsub_logger = logging.getLogger(__name__)
        return pubsub_logger

    def __init__(
        self,
        topic: str,
        msg_type: Optional[PubSubMessage] = None,
        on_message: Optional[Callable] = None,
        *args,
        **kwargs):
        """__init__.
        Initializes a new instance of the `BaseSubscriber` class.

        Args:
            topic (str): The topic to subscribe to.
            msg_type (Optional[PubSubMessage]): The type of message to expect for this subscription.
            on_message (Optional[Callable]): A callback function to be called when a message is received.
            *args: Additional positional arguments to pass to the base class constructor.
            **kwargs: Additional keyword arguments to pass to the base class constructor.
        """

        super().__init__(*args, **kwargs)
        self._topic = topic
        self._msg_type = msg_type
        self.onmessage = on_message
        self._gen_random_id = gen_random_id

        self._executor = ThreadPoolExecutor(max_workers=2)
        self._main_thread = None
        self._t_stop_event = None

    @property
    def topic(self) -> str:
        """topic"""
        return self._topic

    @property
    def executor(self) -> ThreadPoolExecutor:
        """topic"""
        return self._executor

    def run_forever(self) -> None:
        """run_forever.
        Start subscriber thread in background and blocks main thread.

        Args:

        Returns:
            None:
        """
        raise NotImplementedError()

    def on_message(self, data: Dict) -> None:
        """on_message.

        Args:
            data (Dict): data

        Returns:
            None:
        """
        raise NotImplementedError()

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
            self._main_thread = threading.Thread(target=self.run_forever)
            self._main_thread.daemon = True
            self._t_stop_event = threading.Event()
            self._main_thread.start()
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
