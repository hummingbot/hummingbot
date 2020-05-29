from hummingbot.market.beaxy.beaxy_order_book_tracker_entry import BeaxyOrderBookTrackerEntry
import logging
import aiohttp
import asyncio
import ujson
from typing import (
    Any,
    AsyncIterable
)
import pandas as pd
import websockets
from websockets.exceptions import ConnectionClosed
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from typing import Optional, List, Dict
from hummingbot.market.beaxy.beaxy_constants import BeaxyConstants
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.market.beaxy.beaxy_active_order_tracker import BeaxyActiveOrderTracker
from hummingbot.market.beaxy.beaxy_order_book import BeaxyOrderBook


ORDERBOOK_MESSAGE_SNAPSHOT = "SNAPSHOT_FULL_REFRESH"
ORDERBOOK_MESSAGE_DIFF = "INCREMENTAL_UPDATE"


class BeaxyAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    _bxyaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bxyaobds_logger is None:
            cls._bxyaobds_logger = logging.getLogger(__name__)
        return cls._bxyaobds_logger

    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__()

        self._trading_pairs: Optional[List[str]] = trading_pairs

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        async with aiohttp.ClientSession() as client:
            symbols_response, rates_response = await asyncio.gather(
                client.get(BeaxyConstants.PublicApi.SYMBOLS_URL),
                client.get(BeaxyConstants.PublicApi.RATES_URL)
            )
            symbols_response: aiohttp.ClientResponse = symbols_response
            rates_response: aiohttp.ClientResponse = rates_response

            if symbols_response.status != 200:
                raise IOError(f"Error fetching Beaxy markets information. "
                              f"HTTP status is {symbols_response.status}.")
            if rates_response.status != 200:
                raise IOError(f"Error fetching Beaxy exchange information. "
                              f"HTTP status is {symbols_response.status}.")

            symbols_data = await symbols_response.json()
            rates_data = await rates_response.json()

            market_data: List[Dict[str, Any]] = [{"pair": pair, **rates_data[pair], **item}
                                                 for pair in rates_data
                                                 for item in symbols_data
                                                 if item["suspendedForTrading"] is False
                                                 if pair in item["symbol"]]

            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index="pair")

            btc_price: float = float(all_markets.loc['BTCUSDC'].price)
            eth_price: float = float(all_markets.loc['ETHUSDC'].price)

            usd_volume: List[float] = [
                (
                    volume * quote_price if trading_pair.endswith(("USDC")) else
                    volume * quote_price * btc_price if trading_pair.endswith("BTC") else
                    volume * quote_price * eth_price if trading_pair.endswith("ETH") else
                    volume
                )
                for trading_pair, volume, quote_price in zip(
                    all_markets.index,
                    all_markets.volume24.astype('float'),
                    all_markets.price.astype('float')
                )
            ]

        all_markets.loc[:, 'USDVolume'] = usd_volume
        del all_markets['volume']
        all_markets.rename(columns={'baseCurrency': 'baseAsset',
                                    'termCurrency': 'quoteAsset',
                                    'volume24': 'volume'}, inplace=True)

        return all_markets.sort_values("USDVolume", ascending=False)

    async def get_trading_pairs(self) -> Optional[List[str]]:
        if not self._trading_pairs:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._trading_pairs = active_markets.index.tolist()
            except Exception:
                self.logger().network(
                    "Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg="Error getting active exchange information. Check network connection."
                )
        return self._trading_pairs

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str, depth: int = 20) -> Dict[str, Any]:
        assert depth in [5, 10, 20]
        async with client.get(BeaxyConstants.PublicApi.ORDER_BOOK_URL.format(symbol=trading_pair, depth=depth)) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Beaxy market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = await response.json()
            return data

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        async with aiohttp.ClientSession() as client:
            trading_pairs: Optional[List[str]] = await self.get_trading_pairs()
            assert trading_pairs is not None
            retval: Dict[str, OrderBookTrackerEntry] = {}
            number_of_pairs: int = len(trading_pairs)
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 20)
                    snapshot_timestamp = snapshot["timestamp"]
                    snapshot_msg: OrderBookMessage = BeaxyOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
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

                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index+1}/{number_of_pairs} completed.")
                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                    await asyncio.sleep(5.0)
            return retval

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_order_book_stream(self,
                                           ev_loop: asyncio.BaseEventLoop,
                                           snapshot_queue: asyncio.Queue,
                                           diff_queue: asyncio.Queue):
        while True:
            try:
                trading_pairs: Optional[List[str]] = await self.get_trading_pairs()
                assert trading_pairs is not None
                ws_path: str = "/".join([f"{trading_pair}@depth20" for trading_pair in trading_pairs])
                stream_url: str = f"{BeaxyConstants.PublicApi.WS_BASE_URL}/book/{ws_path}"

                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        msg_type = msg["type"]
                        if msg_type.lower() == ORDERBOOK_MESSAGE_SNAPSHOT.lower():
                            order_book_message: OrderBookMessage = BeaxyOrderBook.snapshot_message_from_exchange(
                                msg, msg["timestamp"])
                            snapshot_queue.put_nowait(order_book_message)
                        elif msg_type.lower() == ORDERBOOK_MESSAGE_DIFF.lower():
                            for entry in msg["entries"]:
                                order_book_message: OrderBookMessage = BeaxyOrderBook.diff_message_from_exchange(
                                    entry, msg["timestamp"])
                                diff_queue.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Diffs and snapshots are received and processed in listen_for_order_book_stream
        pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Diffs and snapshots are received and processed in listen_for_order_book_stream
        pass

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: Optional[List[str]] = await self.get_trading_pairs()
                assert trading_pairs is not None
                ws_path: str = "/".join([trading_pair for trading_pair in trading_pairs])
                stream_url: str = f"{BeaxyConstants.PublicApi.WS_BASE_URL}/trades/{ws_path}"

                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        trade_msg: OrderBookMessage = BeaxyOrderBook.trade_message_from_exchange(msg)
                        output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)
