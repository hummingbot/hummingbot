import asyncio
import aiohttp
import logging
import pandas as pd
import time
from typing import Any, AsyncIterable, Dict, List, Optional
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.liquid.liquid_order_book import LiquidOrderBook
from hummingbot.connector.exchange.liquid.liquid_order_book_tracker_entry import LiquidOrderBookTrackerEntry
from hummingbot.connector.exchange.liquid.constants import Constants


class LiquidAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _laobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> (HummingbotLogger):
        if cls._laobds_logger is None:
            cls._laobds_logger = logging.getLogger(__name__)
        return cls._laobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)

        self._order_book_create_function = lambda: OrderBook()
        self.trading_pair_id_conversion_dict: Dict[str, int] = {}

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        results = dict()
        async with aiohttp.ClientSession() as client:
            resp = await client.get(Constants.GET_EXCHANGE_MARKETS_URL)
            resp_json = await resp.json()
            for record in resp_json:
                trading_pair = f"{record['base_currency']}-{record['quoted_currency']}"
                if trading_pair in trading_pairs:
                    results[trading_pair] = float(record["last_traded_price"])
        return results

    @staticmethod
    def reformat_trading_pairs(products):
        """
        Add a new key 'trading_pair' to the incoming json list
        Modify trading pair from '{baseAsset}{quoteAsset}' to '{baseAsset}-{quoteAsset}' format
        """
        for data in products:
            data['trading_pair'] = '-'.join([data['base_currency'], data['quoted_currency']])

        return products

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)  # TODO: Not really sure what this does
    async def get_active_exchange_markets(cls) -> (pd.DataFrame):
        """
        Returned data frame should have 'currency_pair_code' as index and include
        * usd volume
        * baseAsset
        * quoteAsset
        """
        # Fetch raw exchange and markets data from Liquid
        exchange_markets_data: list = await cls.get_exchange_markets_data()

        # TODO: Understand the behavior of a non async method wrapped by another async method
        # Make sure doing this will not block other task
        market_data: List[str, Any] = cls.filter_market_data(
            exchange_markets_data=exchange_markets_data)

        market_data = cls.reformat_trading_pairs(market_data)

        # Build the data frame
        all_markets_df: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index='trading_pair')

        btc_price: float = float(all_markets_df.loc['BTC-USD'].last_traded_price)
        eth_price: float = float(all_markets_df.loc['ETH-USD'].last_traded_price)
        usd_volume: float = [
            (
                volume * quote_price if trading_pair.endswith(("USD", "USDC")) else
                volume * quote_price * btc_price if trading_pair.endswith("BTC") else
                volume * quote_price * eth_price if trading_pair.endswith("ETH") else
                volume
            )
            for trading_pair, volume, quote_price in zip(
                all_markets_df.index,
                all_markets_df.volume_24h.astype('float'),
                all_markets_df.last_traded_price.astype('float')
            )
        ]

        all_markets_df.loc[:, 'USDVolume'] = usd_volume
        all_markets_df.loc[:, 'volume'] = all_markets_df.volume_24h
        all_markets_df.rename(
            {"base_currency": "baseAsset", "quoted_currency": "quoteAsset"}, axis="columns", inplace=True
        )

        return all_markets_df.sort_values("USDVolume", ascending=False)

    @classmethod
    async def get_exchange_markets_data(cls) -> (List):
        """
        Fetch Liquid exchange data from '/products' with following structure:
        exchange_markets_data (Dict)
        |-- id: str
        |-- product_type: str
        |-- code: str
        |-- name: str
        |-- market_ask: float
        |-- market_bid: float
        |-- indicator: int
        |-- currency: str
        |-- currency_pair_code: str
        |-- symbol: str
        |-- btc_minimum_withdraw: float
        |-- fiat_minimum_withdraw: float
        |-- pusher_channel: str
        |-- taker_fee: str (float)
        |-- maker_fee: str (float)
        |-- low_market_bid: str (float)
        |-- high_market_ask: str (float)
        |-- volume_24h: str (float)
        |-- last_price_24h: str (float)
        |-- last_traded_price: str (float)
        |-- last_traded_quantity: str (float)
        |-- quoted_currency: str
        |-- base_currency: str
        |-- disabled: bool
        |-- margin_enabled: bool
        |-- cfd_enabled: bool
        |-- last_event_timestamp: str
        """
        async with aiohttp.ClientSession() as client:
            exchange_markets_response: aiohttp.ClientResponse = await client.get(
                Constants.GET_EXCHANGE_MARKETS_URL)

            if exchange_markets_response.status != 200:
                raise IOError(f"Error fetching Liquid markets information. "
                              f"HTTP status is {exchange_markets_response.status}.")

            exchange_markets_data = await exchange_markets_response.json()
            return exchange_markets_data

    @classmethod
    def filter_market_data(cls, exchange_markets_data) -> (List[dict]):
        """
        Filter out:
        * Market with invalid 'symbol' key, note: symbol here is not the same as trading pair
        * Market with 'disabled' field set to True
        """
        return [
            item for item in exchange_markets_data
            if item['disabled'] is False
        ]

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            # Returns a List of str, representing each active trading pair on the exchange.
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{Constants.BASE_URL}{Constants.PRODUCTS_URI}", timeout=10) as response:
                    if response.status == 200:
                        products: List[Dict[str, Any]] = await response.json()
                        for data in products:
                            data['trading_pair'] = '-'.join([data['base_currency'], data['quoted_currency']])
                        return [
                            product["trading_pair"] for product in products
                            if product['disabled'] is False
                        ]

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete available
            pass

        return []

    async def get_trading_pairs(self) -> List[str]:
        """
        Extract trading_pairs information from all_markets_df generated
        in get_active_exchange_markets method.
        Along the way, also populate the self._trading_pair_id_conversion_dict,
        for downstream reference since Liquid API uses id instead of trading
        pair as the identifier
        """
        try:
            if not self.trading_pair_id_conversion_dict:
                active_markets_df: pd.DataFrame = await self.get_active_exchange_markets()

                if not self._trading_pairs:
                    self._trading_pairs = active_markets_df.index.tolist()

                self.trading_pair_id_conversion_dict = {
                    trading_pair: active_markets_df.loc[trading_pair, 'id']
                    for trading_pair in self._trading_pairs
                }
        except Exception:
            self._trading_pairs = []
            self.logger().network(
                "Error getting active exchange information.",
                exe_info=True,
                app_warning_msg="Error getting active exchange information. Check network connection."
            )

        return self._trading_pairs

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str, full: int = 1) -> Dict[str, Any]:
        """
        Method designed to fetch individual trading_pair corresponded order book, aka snapshot
        param: client - aiohttp client session
        param: trading_pair - used to identify different order book, will be converted to id
        param: full - with full set to 1, return full order book, otherwise return 20 records
                      if 0 is selected
        snapshot (dict)
        |-- buy_price_levels: list[str, str]  # [price, amount]
        |-- sell_price_levels: list[str, str]  # [price, amount]
        """
        product_id = self.trading_pair_id_conversion_dict.get(trading_pair, None)
        if not product_id:
            raise ValueError(f"Invalid trading pair {trading_pair} and product id {product_id} found")

        async with client.get(Constants.GET_SNAPSHOT_URL.format(id=product_id, full=full)) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Liquid market snapshot for {id}. "
                              f"HTTP status is {response.status}.")
            snapshot: Dict[str, Any] = await response.json()
            return {
                **snapshot,
                'trading_pair': trading_pair
            }

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        await self.get_trading_pairs()
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = LiquidOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )

            order_book: OrderBook = self.order_book_create_function()
            order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
            return order_book

    async def get_tracking_pairs(self) -> Dict[str, LiquidOrderBookTrackerEntry]:
        """
        Create tracking pairs by using trading pairs (trading_pairs) fetched from
        active markets
        """
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:

            trading_pairs: List[str] = await self.get_trading_pairs()

            retval: Dict[str, LiquidOrderBookTrackerEntry] = {}
            number_of_pairs: int = len(trading_pairs)

            for index, trading_pair in enumerate(trading_pairs):

                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = LiquidOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )

                    order_book: OrderBook = self.order_book_create_function()
                    order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)

                    retval[trading_pair] = LiquidOrderBookTrackerEntry(trading_pair, snapshot_timestamp, order_book)

                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index+1}/{number_of_pairs} completed")
                    # Each 1000 limit snapshot costs ?? requests and Liquid rate limit is ?? requests per second.
                    await asyncio.sleep(1.0)  # Might need to be changed
                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                    await asyncio.sleep(5)
            return retval

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

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
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=Constants.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        await asyncio.wait_for(pong_waiter, timeout=Constants.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Subscribe to diff channel via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        # {old_trading_pair: new_trading_pair}
        old_trading_pair_conversions = {}

        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()

                async with websockets.connect(Constants.BAEE_WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:

                        old_trading_pair = trading_pair.replace('-', '')
                        old_trading_pair_conversions[old_trading_pair] = trading_pair

                        for side in [Constants.SIDE_BID, Constants.SIDE_ASK]:
                            subscribe_request: Dict[str, Any] = {
                                "event": Constants.WS_PUSHER_SUBSCRIBE_EVENT,
                                "data": {
                                    "channel": Constants.WS_ORDER_BOOK_DIFF_SUBSCRIPTION.format(
                                        currency_pair_code=old_trading_pair.lower(), side=side)
                                }
                            }

                            await ws.send(ujson.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        diff_msg: Dict[str, Any] = ujson.loads(raw_msg)

                        event_type = diff_msg.get('event', None)
                        if event_type == 'updated':

                            # Channel example: 'price_ladders_cash_ethusd_sell'
                            old_trading_pair = diff_msg.get('channel').split('_')[-2].upper()
                            trading_pair = old_trading_pair_conversions[old_trading_pair]

                            buy_or_sell = diff_msg.get('channel').split('_')[-1].lower()
                            side = 'asks' if buy_or_sell == Constants.SIDE_ASK else 'bids'
                            diff_msg = {
                                '{0}'.format(side): ujson.loads(diff_msg.get('data', [])),
                                'trading_pair': trading_pair
                            }
                            diff_timestamp: float = time.time()
                            msg: OrderBookMessage = LiquidOrderBook.diff_message_from_exchange(
                                diff_msg,
                                diff_timestamp,
                                metadata={
                                    "trading_pair": trading_pair,
                                    "update_id": int(diff_timestamp * 1e-3)
                                }
                            )
                            output.put_nowait(msg)
                        elif not event_type:
                            raise ValueError(f"Liquid Websocket message does not contain an event type - {diff_msg}")

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Fetches order book snapshots for each trading pair, and use them to update the local order book
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        TODO: This method needs to be further break down, otherwise, whenever error occurs, the only message
        getting is something similar to `Unexpected error with WebSocket connection.`
        """
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot['asks'] = snapshot.get('sell_price_levels')
                            snapshot['bids'] = snapshot.get('buy_price_levels')
                            snapshot_msg: OrderBookMessage = LiquidOrderBook.snapshot_message_from_exchange(
                                msg=snapshot,
                                timestamp=snapshot_timestamp,
                                metadata={
                                    'trading_pair': trading_pair
                                }
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
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
