#!/usr/bin/env python
import asyncio
import logging
import time
import aiohttp

from hummingbot.connector.exchange.wazirx import wazirx_constants as CONSTANTS
from typing import Optional, List, Dict, AsyncIterable, Any
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from . import wazirx_utils
from .wazirx_active_order_tracker import WazirxActiveOrderTracker
from .wazirx_order_book import WazirxOrderBook
from .wazirx_utils import ms_timestamp_to_s


class WazirxAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        trading_pairs: List[str] = None,
        throttler: Optional[AsyncThrottler] = None,
        shared_client: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(trading_pairs)
        self._trading_pairs: List[str] = trading_pairs
        self._snapshot_msg: Dict[str, any] = {}
        self._shared_client = shared_client or self._get_session_instance()
        self._throttler = throttler or self._get_throttler_instance()

    @classmethod
    def _get_session_instance(cls) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession()
        return session

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    @classmethod
    async def get_last_traded_prices(
        cls,
        trading_pairs: List[str],
        throttler: Optional[AsyncThrottler] = None,
        shared_client: Optional[aiohttp.ClientSession] = None
    ) -> Dict[str, float]:

        shared_client = shared_client or cls._get_session_instance()

        result = {}

        throttler = throttler or cls._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.GET_TICKER_24H):
            async with shared_client.get(f"{CONSTANTS.WAZIRX_API_BASE}/{CONSTANTS.GET_TICKER_24H}") as resp:
                resp_json = await resp.json()
                for t_pair in trading_pairs:
                    last_trade = [float(o["lastPrice"]) for o in resp_json if o["symbol"] == wazirx_utils.convert_to_exchange_trading_pair(t_pair)]
                    if last_trade and last_trade[0] is not None:
                        result[t_pair] = last_trade[0]
                return result

    @staticmethod
    async def fetch_trading_pairs(throttler: Optional[AsyncThrottler] = None) -> List[str]:
        async with aiohttp.ClientSession() as client:
            throttler = throttler or WazirxAPIOrderBookDataSource._get_throttler_instance()
            async with throttler.execute_task(CONSTANTS.GET_EXCHANGE_INFO):
                async with client.get(f"{CONSTANTS.WAZIRX_API_BASE}/{CONSTANTS.GET_EXCHANGE_INFO}", timeout=10) as response:
                    if response.status == 200:
                        try:
                            data: Dict[str, Any] = await response.json()
                            return [str(item["baseAsset"]).upper() + '-' + str(item["quoteAsset"]).upper()
                                    for item in data["symbols"]
                                    if item["isSpotTradingAllowed"] is True]
                        except Exception:
                            pass
                            # Do nothing if the request fails -- there will be no autocomplete for kucoin trading pairs
                    return []

    async def get_order_book_data(self, trading_pair: str, throttler: Optional[AsyncThrottler] = None) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        throttler = throttler or self._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.GET_ORDERBOOK):
            async with self._shared_client.get(
                f"{CONSTANTS.WAZIRX_API_BASE}/{CONSTANTS.GET_ORDERBOOK}?limit=100&symbol="
                f"{wazirx_utils.convert_to_exchange_trading_pair(trading_pair)}"
            ) as orderbook_response:
                if orderbook_response.status != 200:
                    raise IOError(
                        f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                        f"HTTP status is {orderbook_response.status}."
                    )

                orderbook_data: List[Dict[str, Any]] = await safe_gather(orderbook_response.json())
                return orderbook_data[0]

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = WazirxOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        active_order_tracker: WazirxActiveOrderTracker = WazirxActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def _create_websocket_connection(self) -> aiohttp.ClientWebSocketResponse:
        """
        Initialize WebSocket client for APIOrderBookDataSource
        """
        try:
            return await aiohttp.ClientSession().ws_connect(url=CONSTANTS.WSS_URL)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured when connecting to WebSocket server. "
                                  f"Error: {e}")
            raise

    async def _iter_messages(self,
                             ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[Any]:
        try:
            while True:
                yield await ws.receive_json()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured when parsing websocket payload. "
                                  f"Error: {e}")
            raise
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        ws = None
        while True:
            try:
                ws = await self._create_websocket_connection()
                streams = [wazirx_utils.convert_to_exchange_trading_pair(pair) + "@trades" for pair in self._trading_pairs]
                subscribe_request: Dict[str, Any] = {
                    "event": "subscribe",
                    "streams": streams
                }

                await ws.send_json(subscribe_request)

                async for json_msg in self._iter_messages(ws):
                    if "stream" in json_msg:
                        if "@trades" in json_msg["stream"]:
                            for trade in json_msg["data"]["trades"]:
                                trade: Dict[Any] = trade
                                trade_timestamp: int = ms_timestamp_to_s(trade["E"])
                                trade_msg: OrderBookMessage = WazirxOrderBook.trade_message_from_exchange(
                                    trade,
                                    trade_timestamp,
                                    metadata={"trading_pair": wazirx_utils.convert_from_exchange_trading_pair(trade["s"])}
                                )
                                output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
            finally:
                ws and await ws.close()
                await self._sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        WazirX doesn't provide order book diff update at this moment.
        """
        pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        ws = None
        while True:
            try:
                ws = await self._create_websocket_connection()
                streams = [wazirx_utils.convert_to_exchange_trading_pair(pair) + "@depth" for pair in self._trading_pairs]
                subscribe_request: Dict[str, Any] = {
                    "event": "subscribe",
                    "streams": streams
                }

                await ws.send_json(subscribe_request)

                async for json_msg in self._iter_messages(ws):
                    if "stream" in json_msg:
                        if "@depth" in json_msg["stream"]:
                            data = json_msg["data"]
                            snapshot_timestamp: int = ms_timestamp_to_s(data["E"])
                            _msg = {
                                'asks': [list(map(float, item)) for item in data['a']],
                                'bids': [list(map(float, item)) for item in data['b']],
                            }
                            snapshot_msg: OrderBookMessage = WazirxOrderBook.snapshot_message_from_exchange(
                                _msg,
                                snapshot_timestamp,
                                {"trading_pair": wazirx_utils.convert_from_exchange_trading_pair(data["s"])}
                            )
                            output.put_nowait(snapshot_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
            finally:
                ws and await ws.close()
                await self._sleep(30.0)
