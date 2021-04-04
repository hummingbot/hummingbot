import asyncio
import aiohttp
import logging
import pandas as pd
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional
)
from decimal import Decimal
import re
import requests
import cachetools.func
import time
import ujson
import websockets
import socketio
from websockets.exceptions import ConnectionClosed
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.stex.stex_order_book import StexOrderBook
from hummingbot.connector.exchange.stex.stex_utils import (convert_to_exchange_trading_pair, convert_from_exchange_trading_pair)

STEX_TICKER_URL = "https://api3.stex.com/public/ticker"
STEX_DEPTH_URL = "https://api3.stex.com/public/orderbook/{}"
STEX_CURRENCY_PAIRS_ID_CONVERSION = "https://api3.stex.com/public/currency_pairs/list/ALL"
STEX_WS_URL = "https://socket.stex.com"

class StexAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _stobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._stobds_logger is None:
            cls._stobds_logger = logging.getLogger(__name__)
        return cls._stobds_logger

    def __init__(self,trading_pairs: List[str]):
        super().__init__(trading_pairs)
        self._order_book_create_function = lambda: OrderBook()
        self.trading_pair_id_conversion_dict: Dict[str, int] = {}
        self.trades_client: socketio.AsyncClient = socketio.AsyncClient()
        self.diffs_client: socketio.AsyncClient = socketio.AsyncClient()

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        results = dict()
        async with aiohttp.ClientSession() as client:
            resp = await client.get(STEX_TICKER_URL)
            resp_json = await resp.json()
            for trading_pair in trading_pairs:
                resp_record = [o for o in resp_json["data"] if o["symbol"] == convert_to_exchange_trading_pair(trading_pair)][0]
                results[trading_pair] = float(resp_record["last"])
        return results

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        currencyPairId = self.trading_pair_id_conversion_dict.get(trading_pair, None)
        if not currencyPairId:
            raise ValueError("Invalid trading pair {} and Currency Pair Id {}".format(trading_pair,currencyPairId))

        params = {} #default 20
        async with client.get(STEX_DEPTH_URL.format(currencyPairId),params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching market snapshot for {trading_pair}.HTTP status is {response.status}.")
            data: Dict[str,Any] = await response.json()
            return data

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get("STEX_CURRENCY_PAIRS_ID_CONVERSION",timeout=10) as response:
                    if response.status != 200:
                        raise IOError(f"Error fetching trading pairs from Stex. HTTP status is {response.status}.")

                    raw_trading_pairs = await response.json()

                    trading_pairs = []
                    for object in raw_trading_pairs["data"]:
                        converted_trading_pair = convert_from_exchange_trading_pair(object['symbol'])
                        if converted_trading_pair is not None:
                            trading_pairs.append(converted_trading_pair)
                    return trading_pairs

        except Exception:
            pass

        return []

    async def get_trading_pairs(self) -> List[str]:
        try:
            if not self.trading_pair_id_conversion_dict:
                async with aiohttp.ClientSession() as client:
                    exchange_currency_pair_response: aiohttp.ClientResponse = await client.get(STEX_CURRENCY_PAIRS_ID_CONVERSION)
                    if exchange_currency_pair_response.status !=200:
                        raise IOError(f"Error fetching currency pairs information. HTTP status code is {exchange_currency_pair_response.status}.")
                    exchange_currency_pair_data = await exchange_currency_pair_response.json()
                    self._trading_pairs = []
                    for object in exchange_currency_pair_data["data"]:
                        trading_pair = convert_from_exchange_trading_pair(object["symbol"])
                        self._trading_pairs.append(trading_pair)
                        self.trading_pair_id_conversion_dict.update({trading_pair : object["id"]})

        except Exception:
            self._trading_pairs = []
            self.logger().network(
                "Error getting exchange information.",
                exe_info=True,
                app_warning_msg="Error getting active exchange information. Check network connection."
            )

        return self._trading_pairs


    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        await self.get_trading_pairs()
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = StexOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )
            order_book: OrderBook = self.order_book_create_function()
            order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
            return order_book

    async def on_connect_trade(self):
        trading_pairs = self._trading_pairs
        for trading_pair in trading_pairs:
            currencyPairId = self.trading_pair_id_conversion_dict[trading_pair]
            event_name = "trade_c{}".format(currencyPairId)
            await self.trades_client.emit('subscribe',{'channel':event_name,'auth':{}})
    async def listen_for_trades(self, ev_loop: Optional[asyncio.BaseEventLoop], output: asyncio.Queue):
        while True:
            try:
                await self.trades_client.connect(STEX_WS_URL,transports=["websocket"])
                self.trades_client.on('connect',self.on_connect_trade)
                async def data_stream_callback(*msg):
                    trading_pair = None
                    for t_pair,id in self.trading_pair_id_conversion_dict.items():
                        if msg[1]['currency_pair_id']==id:
                            trading_pair = t_pair
                            break
                    if trading_pair is not None:
                        trade_msg: OrderBookMessage = StexOrderBook.trade_message_from_exchange(msg[1],metadata={"trading_pair": trading_pair})
                        output.put_nowait(trade_msg)

                self.trades_client.on("App\Events\OrderFillCreated",data_stream_callback)
                await self.trades_client.wait()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",exc_info=True)
                await asyncio.sleep(30.0)

    async def on_connect_diffs(self):
        trading_pairs = await self.get_trading_pairs()
        for trading_pair in trading_pairs:
            currencyPairId = self.trading_pair_id_conversion_dict[trading_pair]
            event_name = "orderbook_data{}".format(currencyPairId)
            await self.diffs_client.emit('subscribe',{'channel':event_name,'auth':{}})

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                await self.diffs_client.connect(STEX_WS_URL,transports=["websocket"])
                self.diffs_client.on('connect',self.on_connect_diffs)
                async def data_stream_callback(*msg):
                    trading_pair = None
                    for t_pair,id in self.trading_pair_id_conversion_dict.items():
                        if msg[1]['currency_pair_id']==id:
                            trading_pair = t_pair
                            break
                    if trading_pair is not None:
                        msg_dict = {"trading_pair": trading_pair,
                                    "asks":[msg[1]] if msg[1]["type"]=="SELL" else [],
                                    "bids":[msg[1]] if msg[1]["type"]=="BUY" else []}
                        order_book_message: OrderBookMessage = StexOrderBook.diff_message_from_exchange(msg_dict,time.time())
                        output.put_nowait(order_book_message)
                self.diffs_client.on("App\Events\GlassRowChanged",data_stream_callback)
                await self.diffs_client.wait()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_message: OrderBookMessage = StexOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                timestamp=time.time(),
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_message)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
                            await asyncio.sleep(5.0)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
