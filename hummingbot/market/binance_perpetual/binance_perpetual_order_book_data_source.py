import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, AsyncIterable

import aiohttp
import pandas as pd
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.market.binance_perpetual.binance_perpetual_order_book import BinancePerpetualOrderBook

DIFF_STREAM_URL = "wss://fstream.binance.com/stream"
PERPETUAL_BASE_URL = "https://fapi.binance.com/fapi/v1"
SNAPSHOT_REST_URL = PERPETUAL_BASE_URL + "/depth"
TICKER_PRICE_CHANGE_URL = PERPETUAL_BASE_URL + "/ticker/24hr"
EXCHANGE_INFO_URL = PERPETUAL_BASE_URL + "/exchangeInfo"
RECENT_TRADES_URL = PERPETUAL_BASE_URL + "/trades"


class BinancePerpetualOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._order_book_create_function = lambda: OrderBook()

    _bpobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpobds_logger is None:
            cls._bpobds_logger = logging.getLogger(__name__)
        return cls._bpobds_logger

    # TODO: DEPRECATED
    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have trading_pair as index and include usd volume, baseAsset and quoteAsset
        """
        async with aiohttp.ClientSession() as client:
            market_response, exchange_response = await safe_gather(
                client.get(TICKER_PRICE_CHANGE_URL),
                client.get(EXCHANGE_INFO_URL)
            )
            market_response: aiohttp.ClientResponse = market_response
            exchange_response: aiohttp.ClientResponse = exchange_response

            if market_response.status != 200:
                raise IOError(f"Error fetching Binance Perpetual markets information. "
                              f"HTTP status is {market_response.status}.")
            if exchange_response.status != 200:
                raise IOError(f"Error fetching Binance Perpetual exchange information. "
                              f"HTTP status is {exchange_response.status}.")
            market_data = await market_response.json()
            exchange_data = await exchange_response.json()

            trading_pairs: Dict[str, Any] = {ticker["symbol"]: {asset: ticker[asset]
                                                                for asset in ["baseAsset", "quoteAsset"]}
                                             for ticker in exchange_data["symbols"]
                                             if ticker["status"] == "TRADING"}
            market_data: List[Dict[str, Any]] = [{**item, **trading_pairs[item["symbol"]]}
                                                 for item in market_data
                                                 if item["symbol"] in trading_pairs]
            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index="symbol")
            btc_price: float = float(all_markets.loc["BTCUSDT"].lastPrice)
            eth_price: float = float(all_markets.loc["ETHUSDT"].lastPrice)
            usd_volume = [
                (
                    quoteVolume * btc_price if trading_pair.endswith("BTC") else
                    quoteVolume * eth_price if trading_pairs.endswith("ETH") else
                    quoteVolume
                )
                for trading_pair, quoteVolume in zip(all_markets.index,
                                                     all_markets.quoteVolume.astype("float"))
            ]
            all_markets.loc[:, "USDVolume"] = usd_volume
            all_markets.loc[:, "volume"] = all_markets.quoteVolume

            return all_markets.sort_values("USDVolume", ascending=False)

    async def get_trading_pairs(self) -> List[str]:
        if not self._trading_pairs:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._trading_pairs = active_markets.index.tolist()
            except Exception as e:
                self._trading_pairs = []
                self.logger().network(
                    "Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg="Error getting active exchange information. Check network connection."
                )
                raise e
        return self._trading_pairs

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str, limit: int = 1000) -> Dict[str, Any]:
        params: Dict = {"limit": str(limit), "symbol": trading_pair} if limit != 0 else {"symbol": trading_pair}
        async with client.get(SNAPSHOT_REST_URL, params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Binance market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = await response.json()
            return data

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            return_val: Dict[str, OrderBookTrackerEntry] = {}
            for trading_pair in trading_pairs:
                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1000)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = BinancePerpetualOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
                    return_val[trading_pair] = OrderBookTrackerEntry(trading_pair, snapshot_timestamp, order_book)
                    self.logger().info(f"Initialized order book for {trading_pair}. ")
                    await asyncio.sleep(1)
                except Exception as e:
                    self.logger().error(f"Error getting snapshot for {trading_pair}: {e}", exc_info=True)
                    await asyncio.sleep(5)
            return return_val

    async def ws_messages(self, client: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                try:
                    raw_msg: str = await asyncio.wait_for(client.recv(), timeout=30.0)
                    yield raw_msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await client.ping()
                        await asyncio.wait_for(pong_waiter, timeout=10.0)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("Websocket ping timed out. Going to reconnect... ")
            return
        except ConnectionClosed:
            return
        finally:
            await client.close()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                ws_subscription_path: str = "/".join([f"{trading_pair.lower()}@depth"
                                                      for trading_pair in trading_pairs])
                stream_url: str = f"{DIFF_STREAM_URL}?streams={ws_subscription_path}"
                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self.ws_messages(ws):
                        msg_json = ujson.loads(raw_msg)
                        timestamp: float = time.time()
                        order_book_message: OrderBookMessage = BinancePerpetualOrderBook.diff_message_from_exchange(
                            msg_json,
                            timestamp
                        )
                        output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with Websocket connection. Retrying after 30 seconds... ",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                ws_subscription_path: str = "/".join([f"{trading_pair.lower()}@aggTrade"
                                                      for trading_pair in trading_pairs])
                stream_url = f"{DIFF_STREAM_URL}?streams={ws_subscription_path}"
                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self.ws_messages(ws):
                        msg_json = ujson.loads(raw_msg)
                        trade_msg: OrderBookMessage = BinancePerpetualOrderBook.trade_message_from_exchange(msg_json)
                        output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = BinancePerpetualOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            await asyncio.sleep(5)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
                            await asyncio.sleep(5)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
