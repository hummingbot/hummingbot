#!/usr/bin/env python

import aiohttp
import asyncio
import logging
import pandas as pd
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional
)
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils import async_ttl_cache
from hummingbot.market.idex.idex_active_order_tracker import IDEXActiveOrderTracker
from hummingbot.market.idex.idex_order_book import IDEXOrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.market.idex.idex_order_book_message import IDEXOrderBookMessage
from hummingbot.market.idex.idex_order_book_tracker_entry import IDEXOrderBookTrackerEntry

IDEX_REST_URL = "https://api.idex.market"
IDEX_WS_URL = "wss://datastream.idex.market"
IDEX_WS_VERSION = "1.0.0"
IDEX_WS_TRADING_PAIRS_SUBSCRIPTION_LIMIT = 100


class IDEXAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _iaobds_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._iaobds_logger is None:
            cls._iaobds_logger = logging.getLogger(__name__)
        return cls._iaobds_logger

    def __init__(self, idex_api_key: str, trading_pairs: Optional[List[str]] = None):
        super().__init__()
        self._idex_api_key = idex_api_key
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._get_tracking_pair_done_event: asyncio.Event = asyncio.Event()

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_all_token_info(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns all token information
        """
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{IDEX_REST_URL}/returnCurrencies") as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f"Error fetching token info. HTTP status is {response.status}.")
                data: Dict[str, Dict[str, Any]] = await response.json()
                return data

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have trading pair as index and include usd volume, baseAsset and quoteAsset
        """
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{IDEX_REST_URL}/return24Volume") as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f"Error fetching active ddex markets. HTTP status is {response.status}.")
                parsed_response: Dict[str, Dict[str, str]] = await response.json()
                data: List[Dict[str, Any]] = []
                for trading_pair, volume_data in parsed_response.items():
                    # filter out all non trading pair data. IDEX format is "TUSD_ETH"
                    if "_" in trading_pair:
                        quote_asset, base_asset = trading_pair.split("_")
                        data.append({
                            "market": trading_pair,
                            "volumeData": volume_data,
                            "baseAsset": base_asset,
                            "quoteAsset": quote_asset
                        })
                all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data, index="market")

                tusd_eth_volume_in_tusd: float = float(all_markets.loc["TUSD_ETH"].volumeData["TUSD"])
                tusd_eth_volume_in_eth: float = float(all_markets.loc["TUSD_ETH"].volumeData["ETH"])
                usd_eth_price: float = tusd_eth_volume_in_tusd / tusd_eth_volume_in_eth if tusd_eth_volume_in_eth > 0 else 0
                tusd_wbtc_volume_in_tusd: float = float(all_markets.loc["TUSD_WBTC"].volumeData["TUSD"])
                tusd_wbtc_volume_in_wbtc: float = float(all_markets.loc["TUSD_WBTC"].volumeData["WBTC"])
                usd_wtbc_price: float = tusd_wbtc_volume_in_tusd / tusd_wbtc_volume_in_wbtc if tusd_wbtc_volume_in_wbtc > 0 else 0
                tusd_eurs_volume_in_tusd: float = float(all_markets.loc["TUSD_EURS"].volumeData["TUSD"])
                tusd_eurs_volume_in_eurs: float = float(all_markets.loc["TUSD_EURS"].volumeData["EURS"])
                usd_eurs_price: float = tusd_eurs_volume_in_tusd / tusd_eurs_volume_in_eurs if tusd_eurs_volume_in_eurs > 0 else 0

                usd_volume: List[float] = []
                for row in all_markets.itertuples():
                    product_name: str = row.Index
                    quote_asset: str = product_name.split("_")[0]
                    quote_volume: float = float(row.volumeData[quote_asset])
                    if quote_asset in ["TUSD", "USDC", "DAI"]:
                        usd_volume.append(quote_volume)
                    elif quote_asset == "ETH":
                        usd_volume.append(quote_volume * usd_eth_price)
                    elif quote_asset == "WBTC":
                        usd_volume.append(quote_volume * usd_wtbc_price)
                    elif quote_asset == "EURS":
                        usd_volume.append(quote_volume * usd_eurs_price)
                    else:
                        raise ValueError(f"Unable to convert volume to USD for market - {product_name}.")
                all_markets["USDVolume"] = usd_volume
                return all_markets.sort_values("USDVolume", ascending=False)

    async def get_trading_pairs(self) -> List[str]:
        if self._trading_pairs is None:
            active_markets: pd.DataFrame = await self.get_active_exchange_markets()
            trading_pairs: List[str] = active_markets.index.tolist()
            self._trading_pairs = trading_pairs
        else:
            trading_pairs: List[str] = self._trading_pairs
        return trading_pairs

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        quote_asset: str = trading_pair.split("_")[0]
        base_asset: str = trading_pair.split("_")[1]
        params: Dict[str, str] = {
            "selectedMarket": quote_asset,
            "tradeForMarket": base_asset
        }
        orders: List[Dict[str, Any]] = []
        try:
            async with client.get(f"{IDEX_REST_URL}/returnOrderBookForMarket", params=params) as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f"Error fetching IDEX market snapshot for {trading_pair}. "
                                  f"HTTP status is {response.status}.")
                orders: List[Dict[str, Any]] = await response.json()
                return {"orders": orders}

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                f"Error getting snapshot for {trading_pair}.",
                exc_info=True,
                app_warning_msg=f"Error getting snapshot for {trading_pair}. Check network connection."
            )
            await asyncio.sleep(5.0)

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, IDEXOrderBookTrackerEntry] = {}
            number_of_pairs: int = len(trading_pairs)
            token_info: Dict[str, Dict[str, Any]] = await self.get_all_token_info()
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                    snapshot_msg: IDEXOrderBookMessage = IDEXOrderBook.snapshot_message_from_exchange(
                        msg=snapshot,
                        timestamp=None,
                        metadata={"market": trading_pair}
                    )
                    quote_asset_str, base_asset_str = trading_pair.split("_")
                    base_asset: Dict[str, Any] = token_info[base_asset_str]
                    quote_asset: Dict[str, Any] = token_info[quote_asset_str]
                    idex_active_order_tracker: IDEXActiveOrderTracker = IDEXActiveOrderTracker(base_asset=base_asset,
                                                                                               quote_asset=quote_asset)
                    bids, asks = idex_active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                    snapshot_timestamp: float = idex_active_order_tracker.latest_snapshot_timestamp
                    idex_order_book: OrderBook = self.order_book_create_function()
                    idex_order_book.apply_snapshot(bids, asks, snapshot_timestamp)
                    retval[trading_pair] = IDEXOrderBookTrackerEntry(
                        trading_pair,
                        snapshot_timestamp,
                        idex_order_book,
                        idex_active_order_tracker
                    )

                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index+1}/{number_of_pairs} completed.")
                    await asyncio.sleep(1.0)
                except Exception:
                    self.logger().error(f"Error initializing order book for {trading_pair}.", exc_info=True)
                    await asyncio.sleep(5)

            self._get_tracking_pair_done_event.set()
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

    async def _send_handshake(self, ws: websockets.WebSocketClientProtocol):
        handshake_request = {
            "request": "handshake",
            "payload": {
                "version": IDEX_WS_VERSION,
                "key": self._idex_api_key
            }
        }
        await ws.send(ujson.dumps(handshake_request))

    async def _send_subscribe(self,
                              ws: websockets.WebSocketClientProtocol,
                              markets: List[str],
                              decoded: Dict[str, Any]):
        # Send subscribe message for all active market to the connection
        sid: str = decoded["sid"]
        subscribe_payload: Dict[str, Any] = {
            "action": "subscribe",
            "topics": markets,
            "events": ["market_orders", "market_cancels", "market_trades"]
        }
        subscribe_request: Dict[str, Any] = {
            "sid": sid,
            "request": "subscribeToMarkets",
            "payload": subscribe_payload
        }
        await ws.send(ujson.dumps(subscribe_request))

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Trade messages are received from the order book web socket
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs_full_list: List[str] = await self.get_trading_pairs()
                trading_pairs_partial_lists: List[List[str]] = [
                    trading_pairs_full_list[m: m + IDEX_WS_TRADING_PAIRS_SUBSCRIPTION_LIMIT] for m in
                    range(0, len(trading_pairs_full_list), IDEX_WS_TRADING_PAIRS_SUBSCRIPTION_LIMIT)]
                for trading_pairs in trading_pairs_partial_lists:
                    async with websockets.connect(IDEX_WS_URL) as ws:
                        ws: websockets.WebSocketClientProtocol = ws
                        await self._send_handshake(ws)
                        async for raw_message in self._inner_messages(ws):
                            decoded: Dict[str, Any] = ujson.loads(raw_message)
                            request: str = decoded.get("request")
                            diff_messages: List[Dict[str, Any]] = []
                            # after response from handshake, send subscribe message
                            if request == "handshake":
                                await self._send_subscribe(ws, trading_pairs, decoded)
                                continue

                            event: str = decoded.get("event")
                            payload: Dict[str, Any] = ujson.loads(decoded["payload"])  # payload is stringified json
                            if event == "market_orders":
                                orders: List[str, Any] = payload["orders"]
                                market: str = payload["market"]
                                diff_messages = [{**o, "event": event, "market": market} for o in orders]
                            elif event == "market_cancels":
                                cancels: List[str, Any] = payload["cancels"]
                                market: str = payload["market"]
                                diff_messages = [{**c, "event": event, "market": market} for c in cancels]
                            elif event == "market_trades":
                                trades: List[str, Any] = payload["trades"]
                                diff_messages = [{**t, "event": event} for t in trades]
                            else:
                                # ignore message if event is not recognized
                                continue
                            for diff_message in diff_messages:
                                ob_message: IDEXOrderBookMessage = IDEXOrderBook.diff_message_from_exchange(
                                    diff_message)
                                output.put_nowait(ob_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Error getting order book diff messages.",
                    exc_info=True,
                    app_warning_msg=f"Error getting order book diff messages. Check network connection."
                )
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        await self._get_tracking_pair_done_event.wait()
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: IDEXOrderBookMessage = IDEXOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                {"market": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair} at {snapshot_timestamp}")
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().network(
                                f"Error getting snapshot for {trading_pair}.",
                                exc_info=True,
                                app_warning_msg=f"Error getting snapshot for {trading_pair}. Check network connection."
                            )
                            await asyncio.sleep(5.0)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error listening for order book snapshot.",
                    exc_info=True,
                    app_warning_msg=f"Unexpected error listening for order book snapshot. Check network connection."
                )
                await asyncio.sleep(5.0)
