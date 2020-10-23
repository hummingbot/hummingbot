#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import pandas as pd
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.connector.exchange.eterbase.eterbase_order_book import EterbaseOrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils import async_ttl_cache
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.connector.exchange.eterbase.eterbase_active_order_tracker import EterbaseActiveOrderTracker
import hummingbot.connector.exchange.eterbase.eterbase_constants as constants
from hummingbot.connector.exchange.eterbase.eterbase_utils import (
    convert_to_exchange_trading_pair,
    convert_from_exchange_trading_pair)

MAX_RETRIES = 20
NaN = float("nan")


class EterbaseAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    API_CALL_TIMEOUT = 30.0

    _eaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._eaobds_logger is None:
            cls._eaobds_logger = logging.getLogger(__name__)
        return cls._eaobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)
        self._tp_map_mrktid: Dict[str, str] = None

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        results = dict()
        async with aiohttp.ClientSession() as client:
            resp = await client.get(f"{constants.REST_URL}/tickers")
            resp_json = await resp.json()
            for trading_pair in trading_pairs:
                resp_record = [o for o in resp_json if o["symbol"] == convert_to_exchange_trading_pair(trading_pair)][0]
                results[trading_pair] = float(resp_record["price"])
        return results

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        *required
        Returns all currently active BTC trading pairs from Eterbase, sorted by volume in descending order.
        """
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{constants.REST_URL}/markets") as products_response:
                products_response: aiohttp.ClientResponse = products_response
                if products_response.status != 200:
                    raise IOError(f"Error fetching active Eterbase markets. HTTP status is {products_response.status}.")
                data = await products_response.json()
                for pair in data:
                    pair["symbol"] = convert_from_exchange_trading_pair(pair["symbol"])
                all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data, index="id")
                all_markets.rename({"base": "baseAsset", "quote": "quoteAsset"},
                                   axis="columns", inplace=True)
                all_markets = all_markets[(all_markets.state == 'Trading')]
                ids: List[str] = list(all_markets.index)
                volumes: List[float] = []
                prices: List[float] = []

                tickers = None
                async with client.get(f"{constants.REST_URL}/tickers") as tickers_response:
                    tickers_response: aiohttp.ClientResponse = tickers_response
                    if tickers_response.status == 200:
                        data = await tickers_response.json()
                        tickers: pd.DataFrame = pd.DataFrame.from_records(data=data, index="marketId")
                    else:
                        raise IOError(f"Error fetching tickers on Eterbase. "
                                      f"HTTP status is {tickers_response.status}.")

                for product_id in ids:
                    volumes.append(float(tickers.loc[product_id].volume))
                    prices.append(float(tickers.loc[product_id].price))
                all_markets["volume"] = volumes
                all_markets["price"] = prices

                cross_rates = None
                async with client.get(f"{constants.REST_URL}/tickers/cross-rates") as crossrates_response:
                    crossrates_response: aiohttp.ClientResponse = crossrates_response
                    if crossrates_response.status == 200:
                        data = await crossrates_response.json()
                        cross_rates: pd.DataFrame = pd.json_normalize(data, record_path ='rates', meta = ['base'])
                    else:
                        raise IOError(f"Error fetching cross-rates on Eterbase. "
                                      f"HTTP status is {crossrates_response.status}.")

                usd_volume: List[float] = []
                cross_rates_ids: List[str] = list(cross_rates.base)
                for row in all_markets.itertuples():
                    quote_name: str = row.quoteAsset
                    quote_volume: float = row.volume
                    quote_price: float = row.price

                    found = False
                    for product_id in cross_rates_ids:
                        if quote_name == product_id:
                            rate: float = cross_rates.loc[(cross_rates['base'] == product_id) & (cross_rates['quote'].str.startswith("USDT"))].iat[0, 1]
                            usd_volume.append(quote_volume * quote_price * rate)
                            found = True
                            break
                    if found is False:
                        usd_volume.append(NaN)
                        cls.logger().error(f"Unable to convert volume to USD for market - {quote_name}.")
                all_markets["USDVolume"] = usd_volume
                return all_markets.sort_values(by = ["USDVolume"], ascending = False)

    async def get_map_marketid(self) -> Dict[str, str]:
        """
        Get a list of active trading pairs
        (if the market class already specifies a list of trading pairs,
        returns that list instead of all active trading pairs)
        :returns: A list of trading pairs defined by the market class, or all active trading pairs from the rest API
        """
        if not self._tp_map_mrktid:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                active_markets['id'] = active_markets.index
                self._tp_map_mrktid = dict(zip(active_markets.symbol, active_markets.id))
            except Exception:
                self._tp_map_mrktid = None
                self.logger().network(
                    "Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg="Error getting active exchange information. Check network connection."
                )
        return self._tp_map_mrktid

    @staticmethod
    async def get_map_market_id() -> Dict[str, str]:
        """
        """
        tp_map_mid: Dict[str, str] = {}
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{constants.REST_URL}/markets") as products_response:
                products_response: aiohttp.ClientResponse = products_response
                if products_response.status != 200:
                    raise IOError(f"Error fetching active Eterbase markets. HTTP status is {products_response.status}.")
                data = await products_response.json()
                for dt in data:
                    tp_map_mid[convert_from_exchange_trading_pair(dt['symbol'])] = dt['id']
        return tp_map_mid

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            from hummingbot.connector.exchange.eterbase.eterbase_utils import convert_from_exchange_trading_pair

            async with aiohttp.ClientSession() as client:
                async with client.get("https://api.eterbase.exchange/api/markets", timeout=10) as response:
                    if response.status == 200:
                        markets = await response.json()
                        raw_trading_pairs: List[str] = list(map(lambda trading_market: trading_market.get('symbol'), filter(lambda details: details.get('state') == 'Trading', markets)))
                        trading_pair_list: List[str] = []
                        for raw_trading_pair in raw_trading_pairs:
                            converted_trading_pair: Optional[str] = \
                                convert_from_exchange_trading_pair(raw_trading_pair)
                            if converted_trading_pair is not None:
                                trading_pair_list.append(converted_trading_pair)
                        return trading_pair_list
        except Exception:
            pass
            # Do nothing if the request fails -- there will be no autocomplete for eterbase trading pairs
        return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, any]:
        """
        Fetches order book snapshot for a particular trading pair from the rest API
        :returns: Response from the rest API
        """

        map_market = await EterbaseAPIOrderBookDataSource.get_map_market_id()
        market_id = map_market[trading_pair]
        product_order_book_url: str = f"{constants.REST_URL}/markets/{market_id}/order-book"
        async with client.get(product_order_book_url) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Eterbase market snapshot for marketId: {market_id}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = await response.json()
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            td_map_id: Dict[str, str] = await self.get_map_marketid()
            snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = EterbaseOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair, "market_id": td_map_id[trading_pair]}
            )
            order_book: OrderBook = self.order_book_create_function()
            active_order_tracker: EterbaseActiveOrderTracker = EterbaseActiveOrderTracker()
            bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
            order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
            return order_book

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout = self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        await ws.send('{"type": "ping"}')
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Trade messages are received from the order book web socket
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to diff channel via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                trading_pairs = self._trading_pairs
                tp_map_mrktid = await self.get_map_marketid()
                marketsDict = dict(zip(tp_map_mrktid.values(), tp_map_mrktid.keys()))
                marketIds = []
                for tp in trading_pairs:
                    marketIds.append(tp_map_mrktid[tp])

                async with websockets.connect(constants.WSS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = {
                        "type": "subscribe",
                        "channelId": "order_book",
                        "marketIds": marketIds,
                    }
                    await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        msg_type: str = msg.get("type", None)
                        if msg_type is None:
                            raise ValueError(f"Eterbase Websocket message does not contain a type - {msg}")
                        elif msg_type == "error":
                            raise ValueError(f"Eterbase Websocket received error message - {msg['message']}")
                        elif msg_type == "pong":
                            self.logger().debug("Eterbase websocket received event pong - {msg}")
                        elif msg_type == "ob_snapshot":
                            order_book_message: OrderBookMessage = EterbaseOrderBook.snapshot_message_from_exchange(msg, pd.Timestamp.now("UTC").timestamp())
                            output.put_nowait(order_book_message)
                        elif msg_type == "ob_update":
                            msg["trading_pair"] = marketsDict[msg["marketId"]]
                            order_book_message: OrderBookMessage = EterbaseOrderBook.diff_message_from_exchange(msg, pd.Timestamp.now("UTC").timestamp())
                            output.put_nowait(order_book_message)
                        else:
                            raise ValueError(f"Unrecognized Eterbase Websocket message received - {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    "Check network connection."
                )
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Fetches order book snapshots for each trading pair, and use them to update the local order book
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = EterbaseOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"product_id": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            # Be careful not to go above API rate limits.
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().network(
                                "Unexpected error with WebSocket connection.",
                                exc_info=True,
                                app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                                "Check network connection."
                            )
                            await asyncio.sleep(5.0)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute = 0, second = 0, microsecond = 0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours = 1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info = True)
                await asyncio.sleep(5.0)
