import asyncio
from abc import (
    ABCMeta,
    abstractmethod,
)


class UserStreamTrackerDataSource(metaclass=ABCMeta):

    @abstractmethod
    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue

        :param output: the queue to use to store the received messages
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def last_recv_time(self) -> float:
        raise NotImplementedError

    async def _sleep(self, delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module

        :param delay: number of seconds to sleep
        """
        await asyncio.sleep(delay)
