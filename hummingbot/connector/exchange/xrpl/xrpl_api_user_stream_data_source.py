import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models import Subscribe

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange


class XRPLAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self, auth: XRPLAuth, connector: "XrplExchange"):
        super().__init__()
        self._connector = connector
        self._auth = auth
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
            client: AsyncWebsocketClient | None = None
            node_url: str | None = None
            try:
                self._connector._node_pool.add_burst_tokens(1)
                subscribe = Subscribe(accounts=[self._auth.get_account()])
                client = await self._get_client()
                node_url = client.url
                async with client as ws_client:
                    if ws_client._websocket is None:
                        continue

                    ws_client._websocket.max_size = CONSTANTS.WEBSOCKET_MAX_SIZE_BYTES
                    ws_client._websocket.ping_interval = 10
                    ws_client._websocket.ping_timeout = CONSTANTS.WEBSOCKET_CONNECTION_TIMEOUT

                    # set up a listener task
                    listener = asyncio.create_task(self.on_message(ws_client, output_queue=output))

                    # subscribe to the ledger
                    await ws_client.send(subscribe)

                    # Wait for listener to complete naturally when connection closes
                    # The on_message async iterator will exit when WebSocket closes
                    # WebSocket ping/pong mechanism handles keep-alive automatically
                    await listener
            except asyncio.CancelledError:
                self.logger().info("User stream listener task has been cancelled. Exiting...")
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
                if node_url is not None:
                    self._connector._node_pool.mark_bad_node(node_url)
            except TimeoutError:
                self.logger().warning("Timeout error occurred while listening to user stream. Retrying...")
                if node_url is not None:
                    self._connector._node_pool.mark_bad_node(node_url)
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying...")
            finally:
                if listener is not None:
                    listener.cancel()
                    await listener
                if client is not None:
                    await client.close()

    async def on_message(self, client: AsyncWebsocketClient, output_queue: asyncio.Queue):
        async for message in client:
            self._last_recv_time = time.time()
            await self._process_event_message(event_message=message, queue=output_queue)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        queue.put_nowait(event_message)

    async def _get_client(self) -> AsyncWebsocketClient:
        return await self._connector._get_async_client()
