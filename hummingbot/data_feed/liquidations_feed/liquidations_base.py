import asyncio
from collections import deque
from typing import List, Optional

import pandas as pd

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class LiquidationsBase(NetworkBase):
    """
    ...
    """
    columns = ["timestamp", "trading_pair", "side", "order_type", "time_in_force", "original_quantity", "price",
               "average_price", "order_status", "order_last_filled_quantity", "order_filled_accumulated_quantity",
               "order_trade_time"]

    def __init__(self, trading_pairs: List[str], max_records: int = 100):
        # TODO: adapt this class to use a time based queue
        super().__init__()
        async_throttler = AsyncThrottler(rate_limits=self.rate_limits)
        self._api_factory = WebAssistantsFactory(throttler=async_throttler)
        self.max_records = max_records
        self._trading_pairs = trading_pairs
        self._liquidations = {trading_pair: deque(maxlen=max_records) for trading_pair in trading_pairs}
        self._listen_liquidations_task: Optional[asyncio.Task] = None

    async def start_network(self):
        """
        This method starts the network and starts a task for listen_for_subscriptions.
        """
        await self.stop_network()
        self._listen_liquidations_task = safe_ensure_future(self.listen_for_subscriptions())

    async def stop_network(self):
        """
        This method stops the network by canceling the _listen_candles_task task.
        """
        if self._listen_liquidations_task is not None:
            self._listen_liquidations_task.cancel()
            self._listen_candles_task = None

    @property
    def ready(self):
        """
        This property returns a boolean indicating whether the _candles deque has reached its maximum length.
        """
        return any(len(liquidations) > 1 for liquidations in self._liquidations.values())

    @property
    def name(self):
        raise NotImplementedError

    @property
    def rest_url(self):
        raise NotImplementedError

    @property
    def health_check_url(self):
        raise NotImplementedError

    @property
    def wss_url(self):
        raise NotImplementedError

    @property
    def rate_limits(self):
        raise NotImplementedError

    async def check_network(self) -> NetworkStatus:
        raise NotImplementedError

    def liquidations_df(self, trading_pair) -> pd.DataFrame:
        """
        This property returns the candles stored in the _candles deque as a Pandas DataFrame.
        """
        return pd.DataFrame(self._liquidations.get(trading_pair), columns=self.columns)

    def get_exchange_trading_pair(self, trading_pair):
        raise NotImplementedError

    async def listen_for_subscriptions(self):
        """
        Connects to the candlestick websocket endpoint and listens to the messages sent by the
        exchange.
        """
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws: WSAssistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(websocket_assistant=ws)
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to public liquidations. Retrying in 1 seconds...",
                )
                await self._sleep(1.0)
            finally:
                await self._on_order_stream_interruption(websocket_assistant=ws)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=self.wss_url,
                         ping_timeout=30)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the candles events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        raise NotImplementedError

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        raise NotImplementedError

    async def _sleep(self, delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)

    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        websocket_assistant and await websocket_assistant.disconnect()
