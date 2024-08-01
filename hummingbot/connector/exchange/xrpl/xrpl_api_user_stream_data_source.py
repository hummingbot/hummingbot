import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models import Subscribe

from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange


class XRPLAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: XRPLAuth,
                 connector: 'XrplExchange'):
        super().__init__()
        self._connector = connector
        self._auth = auth
        self._xrpl_client = self._connector.user_stream_client
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message

        :return: the timestamp of the last received message in seconds
        """
        return self._last_recv_time

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue

        :param output: the queue to use to store the received messages
        """
        while True:
            listener = None
            try:
                subscribe = Subscribe(accounts=[self._auth.get_account()])

                async with self._xrpl_client as client:
                    # set up a listener task
                    listener = asyncio.create_task(self.on_message(client, output_queue=output))

                    # subscribe to the ledger
                    await client.send(subscribe)

                    # sleep infinitely until the connection closes on us
                    while client.is_open():
                        await asyncio.sleep(0)

                    listener.cancel()
                    await listener
            except asyncio.CancelledError:
                self.logger().info("User stream listener task has been cancelled. Exiting...")
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except TimeoutError:
                self.logger().warning(
                    "Timeout error occurred while listening to user stream. Retrying...")
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying...")
            finally:
                if listener is not None:
                    listener.cancel()
                    try:
                        await listener
                    except asyncio.CancelledError:
                        pass  # Swallow the cancellation error if it happens
                await self._xrpl_client.close()

    async def on_message(self, client: AsyncWebsocketClient, output_queue: asyncio.Queue):
        async for message in client:
            self._last_recv_time = time.time()
            await self._process_event_message(event_message=message, queue=output_queue)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        queue.put_nowait(event_message)
