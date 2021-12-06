import aiohttp
import asyncio
import logging
import json
import ujson

from typing import Any, AsyncIterable, Optional, List, Dict

import websockets

from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.connector.exchange.beaxy.beaxy_active_order_tracker import BeaxyActiveOrderTracker
from hummingbot.connector.exchange.beaxy.beaxy_constants import BeaxyConstants
from hummingbot.connector.exchange.beaxy.beaxy_order_book import BeaxyOrderBook
from hummingbot.connector.exchange.beaxy.beaxy_order_book_tracker_entry import BeaxyOrderBookTrackerEntry
from hummingbot.logger import HummingbotLogger


ORDERBOOK_MESSAGE_SNAPSHOT = 'SNAPSHOT_FULL_REFRESH'
ORDERBOOK_MESSAGE_DIFF = 'INCREMENTAL_UPDATE'


class BeaxyAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    _bxyaobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, str] = {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bxyaobds_logger is None:
            cls._bxyaobds_logger = logging.getLogger(__name__)
        return cls._bxyaobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)

    @classmethod
    async def init_trading_pair_symbols(cls, shared_session: Optional[aiohttp.ClientSession] = None):
        """Initialize _trading_pair_symbol_map class variable
        """
        client_session = shared_session or aiohttp.ClientSession()
        async with client_session as client:
            async with client.get(BeaxyConstants.PublicApi.SYMBOLS_URL, timeout=5) as response:
                if response.status == 200:
                    symbols: List[Dict[str, Any]] = await response.json()
                    cls._trading_pair_symbol_map = {
                        symbol_data["name"]: (f"{symbol_data['baseCurrency']}-{symbol_data['termCurrency']}")
                        for symbol_data in symbols
                    }
                else:
                    IOError(f"There was an error requesting the list of symbols from the exchange ({response})")

    @classmethod
    async def trading_pair_symbol_map(cls) -> Dict[str, str]:
        if not cls._trading_pair_symbol_map:
            await cls.init_trading_pair_symbols()

        return cls._trading_pair_symbol_map

    @staticmethod
    async def exchange_symbol_associated_to_pair(trading_pair: str) -> str:
        symbol_map = await BeaxyAPIOrderBookDataSource.trading_pair_symbol_map()
        symbols = [symbol for symbol, pair in symbol_map.items() if pair == trading_pair]

        if symbols:
            symbol = symbols[0]
        else:
            raise ValueError(f"There is no symbol mapping for trading pair {trading_pair}")

        return symbol

    @staticmethod
    async def trading_pair_associated_to_exchange_symbol(symbol: str) -> str:
        symbol_map = await BeaxyAPIOrderBookDataSource.trading_pair_symbol_map()
        return symbol_map[symbol]

    @staticmethod
    async def fetch_trading_pairs() -> Optional[List[str]]:
        trading_pairs = []
        try:
            symbols_map = await BeaxyAPIOrderBookDataSource.trading_pair_symbol_map()
            trading_pairs.extend(list(symbols_map.values()))
        except Exception:  # nopep8
            # Do nothing if the request fails -- there will be no autocomplete for beaxy trading pairs
            pass
        return trading_pairs

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:

        async def last_price_for_pair(trading_pair):
            symbol = await cls.exchange_symbol_associated_to_pair(trading_pair)
            async with aiohttp.ClientSession() as client:
                async with client.get(BeaxyConstants.PublicApi.RATE_URL.format(symbol=symbol)) as response:
                    response: aiohttp.ClientResponse
                    if response.status != 200:
                        raise IOError(f'Error fetching Beaxy market trade for {trading_pair}. '
                                      f'HTTP status is {response.status}.')
                    data: Dict[str, Any] = await response.json()
                    return trading_pair, float(data['price'])

        fetches = [last_price_for_pair(p) for p in trading_pairs]

        prices = await asyncio.gather(*fetches)

        return {pair: price for pair, price in prices}

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str, depth: int = 20) -> Dict[str, Any]:
        assert depth in [5, 10, 20]

        symbol = await BeaxyAPIOrderBookDataSource.exchange_symbol_associated_to_pair(trading_pair)

        async with client.get(BeaxyConstants.PublicApi.ORDER_BOOK_URL.format(symbol=symbol, depth=depth)) as response:
            response: aiohttp.ClientResponse
            if response.status != 200:
                raise IOError(f'Error fetching Beaxy market snapshot for {trading_pair}. '
                              f'HTTP status is {response.status}.')

            if not await response.text():  # if test is empty it marks that there is no rows
                return {
                    'timestamp': 1,
                    'entries': [],
                    'sequenceNumber': 1,
                }

            data: Dict[str, Any] = await response.json()
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 20)
            snapshot_timestamp = snapshot['timestamp']
            snapshot_msg: OrderBookMessage = BeaxyOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={'trading_pair': trading_pair}
            )
            order_book: OrderBook = self.order_book_create_function()
            active_order_tracker: BeaxyActiveOrderTracker = BeaxyActiveOrderTracker()
            bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
            order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
            return order_book

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        async with aiohttp.ClientSession() as client:
            trading_pairs: Optional[List[str]] = await self.get_trading_pairs()
            assert trading_pairs is not None
            retval: Dict[str, OrderBookTrackerEntry] = {}
            number_of_pairs: int = len(trading_pairs)
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 20)
                    snapshot_timestamp = snapshot['timestamp']
                    snapshot_msg: OrderBookMessage = BeaxyOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={'trading_pair': trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    active_order_tracker: BeaxyActiveOrderTracker = BeaxyActiveOrderTracker()
                    bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                    order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
                    retval[trading_pair] = BeaxyOrderBookTrackerEntry(
                        trading_pair,
                        snapshot_timestamp,
                        order_book,
                        active_order_tracker
                    )

                    self.logger().info(f'Initialized order book for {trading_pair}. '
                                       f'{index+1}/{number_of_pairs} completed.')
                except Exception:
                    self.logger().error(f'Error getting snapshot for {trading_pair}. ', exc_info=True)
                    await asyncio.sleep(5.0)
            return retval

    async def _inner_messages(
        self,
        ws: websockets.WebSocketClientProtocol
    ) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    pong_waiter = await ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning('WebSocket ping timed out. Going to reconnect...')
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # As Beaxy orderbook stream go in one ws and it need to be consistent,
        # tracking is done only from listen_for_order_book_snapshots
        pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                # at Beaxy all pairs listed without splitter
                trading_pairs = [await self.exchange_symbol_associated_to_pair(p) for p in self._trading_pairs]

                ws_path: str = '/'.join([f'{trading_pair}@depth20' for trading_pair in trading_pairs])
                stream_url: str = f'{BeaxyConstants.PublicApi.WS_BASE_URL}/book/{ws_path}'

                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self._inner_messages(ws):
                        msg = json.loads(raw_msg)  # ujson may round floats incorrectly
                        msg_type = msg['type']
                        trading_pair = await self.trading_pair_associated_to_exchange_symbol(msg['security'])
                        if msg_type == ORDERBOOK_MESSAGE_DIFF:
                            order_book_message: OrderBookMessage = BeaxyOrderBook.diff_message_from_exchange(
                                msg,
                                msg['timestamp'],
                                metadata={'trading_pair': trading_pair})
                            output.put_nowait(order_book_message)
                        if msg_type == ORDERBOOK_MESSAGE_SNAPSHOT:
                            order_book_message: OrderBookMessage = BeaxyOrderBook.snapshot_message_from_exchange(
                                msg,
                                msg['timestamp'],
                                metadata={'trading_pair': trading_pair})
                            output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error('Unexpected error with WebSocket connection. Retrying after 30 seconds...',
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs = [await self.exchange_symbol_associated_to_pair(p) for p in self._trading_pairs]

                ws_path: str = '/'.join([trading_pair for trading_pair in trading_pairs])
                stream_url: str = f'{BeaxyConstants.PublicApi.WS_BASE_URL}/trades/{ws_path}'

                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        trading_pair = await self.trading_pair_associated_to_exchange_symbol(msg['symbol'])
                        trade_msg: OrderBookMessage = BeaxyOrderBook.trade_message_from_exchange(
                            msg,
                            metadata={"trading_pair": trading_pair})
                        output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error('Unexpected error with WebSocket connection. Retrying after 30 seconds...',
                                    exc_info=True)
                await asyncio.sleep(30.0)
