#!/usr/bin/env python
import aiohttp
import aiohttp.client_ws
import asyncio
import logging
import pandas as pd
import time
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from hummingbot.connector.exchange.mexc.mexc_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    microseconds,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.mexc.mexc_order_book import MexcOrderBook
from hummingbot.connector.exchange.mexc import mexc_constants as CONSTANTS
from dateutil.parser import parse as dateparse
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.connector.exchange.mexc.mexc_websocket_adaptor import MexcWebSocketAdaptor
from collections import defaultdict


class MexcAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 120.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(self, trading_pairs: List[str],
                 shared_client: Optional[aiohttp.ClientSession] = None,
                 throttler: Optional[AsyncThrottler] = None, ):
        super().__init__(trading_pairs)
        self._trading_pairs: List[str] = trading_pairs
        self._throttler = throttler or self._get_throttler_instance()
        self._shared_client = shared_client or self._get_session_instance()
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    def _get_session_instance(cls) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession()
        return session

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        async with aiohttp.ClientSession() as client:
            throttler = MexcAPIOrderBookDataSource._get_throttler_instance()
            async with throttler.execute_task(CONSTANTS.MEXC_SYMBOL_URL):
                url = CONSTANTS.MEXC_BASE_URL + CONSTANTS.MEXC_SYMBOL_URL
                async with client.get(url) as products_response:

                    products_response: aiohttp.ClientResponse = products_response
                    if products_response.status != 200:
                        return []
                        # raise IOError(f"Error fetching active MEXC. HTTP status is {products_response.status}.")

                    data = await products_response.json()
                    data = data['data']

                    trading_pairs = []
                    for item in data:
                        if item['state'] == "ENABLED":
                            trading_pairs.append(convert_from_exchange_trading_pair(item["symbol"]))
        return trading_pairs

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_snapshot(self._shared_client, trading_pair)

        snapshot_msg: OrderBookMessage = MexcOrderBook.snapshot_message_from_exchange(
            snapshot,
            trading_pair,
            timestamp=microseconds(),
            metadata={"trading_pair": trading_pair})
        order_book: OrderBook = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str], throttler: Optional[AsyncThrottler] = None,
                                     shared_client: Optional[aiohttp.ClientSession] = None) -> Dict[str, float]:
        client = shared_client or cls._get_session_instance()
        throttler = throttler or cls._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.MEXC_TICKERS_URL):
            url = CONSTANTS.MEXC_BASE_URL + CONSTANTS.MEXC_TICKERS_URL
            async with client.get(url) as products_response:
                products_response: aiohttp.ClientResponse = products_response
                if products_response.status != 200:
                    # raise IOError(f"Error get tickers from MEXC markets. HTTP status is {products_response.status}.")
                    return {}
                data = await products_response.json()
                data = data['data']
                all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data)
                all_markets.set_index("symbol", inplace=True)

                out: Dict[str, float] = {}

                for trading_pair in trading_pairs:
                    exchange_trading_pair = convert_to_exchange_trading_pair(trading_pair)
                    out[trading_pair] = float(all_markets['last'][exchange_trading_pair])
                return out

    async def get_trading_pairs(self) -> List[str]:
        if not self._trading_pairs:
            try:
                self._trading_pairs = await self.fetch_trading_pairs()
            except Exception:
                self._trading_pairs = []
                self.logger().network(
                    "Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg="Error getting active exchange information. Check network connection."
                )
        return self._trading_pairs

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str,
                           throttler: Optional[AsyncThrottler] = None) -> Dict[str, Any]:
        throttler = throttler or MexcAPIOrderBookDataSource._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.MEXC_DEPTH_URL):
            trading_pair = convert_to_exchange_trading_pair(trading_pair)
            tick_url = CONSTANTS.MEXC_DEPTH_URL.format(trading_pair=trading_pair)
            url = CONSTANTS.MEXC_BASE_URL + tick_url
            async with client.get(url) as response:
                response: aiohttp.ClientResponse = response
                status = response.status
                if status != 200:
                    raise IOError(f"Error fetching MEXC market snapshot for {trading_pair}. "
                                  f"HTTP status is {status}.")
                api_data = await response.json()
                data = api_data['data']
                data['ts'] = microseconds()

                return data

    @classmethod
    def iso_to_timestamp(cls, date: str):
        return dateparse(date).timestamp()

    async def _sleep(self, delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)

    async def _create_websocket_connection(self) -> MexcWebSocketAdaptor:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            ws = MexcWebSocketAdaptor(throttler=self._throttler, shared_client=self._shared_client)
            await ws.connect()
            return ws
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured connecting to {CONSTANTS.EXCHANGE_NAME} WebSocket API. "
                                  f"({e})")
            raise

    async def listen_for_subscriptions(self):
        ws = None
        while True:
            try:
                ws = await self._create_websocket_connection()
                await ws.subscribe_to_order_book_streams(self._trading_pairs)

                async for msg in ws.iter_messages():
                    decoded_msg: dict = msg

                    if 'channel' in decoded_msg.keys() and decoded_msg['channel'] in MexcWebSocketAdaptor.SUBSCRIPTION_LIST:
                        self._message_queue[decoded_msg['channel']].put_nowait(decoded_msg)
                    else:
                        self.logger().debug(f"Unrecognized message received from MEXC websocket: {decoded_msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    exc_info=True,
                )
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        msg_queue = self._message_queue[MexcWebSocketAdaptor.DEAL_CHANNEL_ID]
        while True:
            try:
                decoded_msg = await msg_queue.get()
                self.logger().debug(f"Recived new trade: {decoded_msg}")

                for data in decoded_msg['data']['deals']:
                    trading_pair = convert_from_exchange_trading_pair(decoded_msg['symbol'])
                    trade_message: OrderBookMessage = MexcOrderBook.trade_message_from_exchange(
                        data, data['t'], metadata={"trading_pair": trading_pair}
                    )
                    self.logger().debug(f'Putting msg in queue: {str(trade_message)}')
                    output.put_nowait(trade_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection ,Retrying after 30 seconds...",
                                    exc_info=True)
                await self._sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        msg_queue = self._message_queue[MexcWebSocketAdaptor.DEPTH_CHANNEL_ID]
        while True:
            try:
                decoded_msg = await msg_queue.get()
                if decoded_msg['data'].get('asks'):
                    asks = [
                        {
                            'price': ask['p'],
                            'quantity': ask['q']
                        }
                        for ask in decoded_msg["data"]["asks"]]
                    decoded_msg['data']['asks'] = asks
                if decoded_msg['data'].get('bids'):
                    bids = [
                        {
                            'price': bid['p'],
                            'quantity': bid['q']
                        }
                        for bid in decoded_msg["data"]["bids"]]
                    decoded_msg['data']['bids'] = bids
                order_book_message: OrderBookMessage = MexcOrderBook.diff_message_from_exchange(
                    decoded_msg['data'], microseconds(),
                    metadata={"trading_pair": convert_from_exchange_trading_pair(decoded_msg['symbol'])}
                )
                output.put_nowait(order_book_message)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await self._sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                session = self._shared_client
                for trading_pair in trading_pairs:
                    try:
                        snapshot: Dict[str, Any] = await self.get_snapshot(session, trading_pair)
                        snapshot_msg: OrderBookMessage = MexcOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            trading_pair,
                            timestamp=microseconds(),
                            metadata={"trading_pair": trading_pair})
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                        await self._sleep(5.0)
                    except asyncio.CancelledError:
                        raise
                    except Exception as ex:
                        self.logger().error("Unexpected error." + repr(ex), exc_info=True)
                        await self._sleep(5.0)
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - time.time()
                await self._sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception as ex1:
                self.logger().error("Unexpected error." + repr(ex1), exc_info=True)
                await self._sleep(5.0)
