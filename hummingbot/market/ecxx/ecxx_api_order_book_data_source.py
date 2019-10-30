#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import time
import pandas as pd

from typing import (
    Any,
    Dict,
    List,
    Optional
)

from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.market.ecxx.ecxx_order_book import EcxxOrderBook

ECXX_MARKET_ORDER_REST_URL = "https://www.ecxx.com/klineApi/getmarket"
ECXX_TICKER_AND_SYMBOL_REST_URL = "https://www.ecxx.com/exapi/api/klinevtwo/message"
MAX_RETRIES = 20
NaN = float("nan")


class EcxxAPIOrderBookDataSource(OrderBookTrackerDataSource):
    PING_TIMEOUT = 10.0
    MESSAGE_TIMEOUT = 30.0
    SNAPSHOT_TIMEOUT = 10.0

    _ecaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._ecaobds_logger is None:
            cls._ecaobds_logger = logging.getLogger(__name__)
        return cls._ecaobds_logger

    def __init__(self, symbols: Optional[List[str]] = None):
        super().__init__()
        self._symbols: Optional[List[str]] = symbols

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have symbol as index and include usd volume, baseAsset and quoteAsset
        """
        async with aiohttp.ClientSession() as client:

            response = await safe_ensure_future(
                client.get(ECXX_TICKER_AND_SYMBOL_REST_URL)
            )

            response: aiohttp.ClientResponse = response

            if response.status != 200:
                raise IOError(f"Error fetching Ecxx markets & exchange information. "
                              f"HTTP status is {response.status}.")

            response_data = await response.json(content_type=None)

            # split the response
            market_data = response_data["lastKLine"]
            exchange_data = response_data["productList"]

            trading_pairs: Dict[str, Any] = {
                item: dict(zip(['baseAsset', 'quoteAsset'], item.split('_')))
                for item in exchange_data
            }

            # index is set to 5 to refer market data at 24H
            market_data: List[Dict[str, Any]] = [
                {**market_data[item][5]['payload'], **trading_pairs[item]}
                for item in trading_pairs
            ]

            def x(item):
                # remove fields
                if '_id' in item:
                    item.pop('_id')
                if 'period' in item:
                    item.pop('period')
                if 'time' in item:
                    item.pop('time')
                if 'dayTotalDealAmount' in item:
                    item.pop('dayTotalDealAmount')

                # rename fields
                if 'symbolId' in item:
                    item['symbol'] = item.pop('symbolId')
                if 'priceOpen' in item:
                    item['open'] = item.pop('priceOpen')
                if 'priceHigh' in item:
                    item['high'] = item.pop('priceHigh')
                if 'priceLow' in item:
                    item['low'] = item.pop('priceLow')
                if 'priceLast' in item:
                    item['close'] = item.pop('priceLast')
                if 'volume' in item:
                    item['vol'] = item.pop('volume')

                return item

            market_data = list(map(x, market_data))

            # Build the data frame.
            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index="symbol")
            btc_price: float = float(all_markets.loc["BTC_USDT"].close)
            eth_price: float = float(all_markets.loc["ETH_USDT"].close)
            usd_volume: float = [
                (
                    vol * btc_price if symbol.endswith("BTC") else
                    vol * eth_price if symbol.endswith("ETH") else
                    vol
                )
                for symbol, vol in zip(all_markets.index,
                                       all_markets.vol.astype("float"))]
            all_markets.loc[:, "USDVolume"] = usd_volume
            all_markets.loc[:, "volume"] = all_markets.vol

            return all_markets.sort_values("USDVolume", ascending=False)

    async def get_trading_pairs(self) -> List[str]:
        if not self._symbols:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._symbols = active_markets.index.tolist()
            except Exception:
                self._symbols = []
                self.logger().network(
                    f"Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg=f"Error getting active exchange information. Check network connection."
                )
        return self._symbols

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        url = f'{ECXX_MARKET_ORDER_REST_URL}/{trading_pair}'
        async with client.get(url) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Ecxx market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            api_data = await response.json(content_type=None)

            asks_data = list(map(list, zip(api_data['asks']['price'], api_data['asks']['amount'])))
            bids_data = list(map(list, zip(api_data['bids']['price'], api_data['bids']['amount'])))

            asks_bids_data = {'asks': asks_data, 'bids': bids_data}
            return asks_bids_data

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, OrderBookTrackerEntry] = {}

            number_of_pairs: int = len(trading_pairs)
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                    snapshot_msg: OrderBookMessage = EcxxOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        metadata={"symbol": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
                    retval[trading_pair] = OrderBookTrackerEntry(trading_pair, snapshot_msg.timestamp, order_book)
                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index + 1}/{number_of_pairs} completed.")
                    # Ecxx rate limit is 100 https requests per second
                    await asyncio.sleep(4)  # divide by 10 based on Huobi connector
                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                    await asyncio.sleep(5)
            return retval

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_message: OrderBookMessage = EcxxOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                metadata={"symbol": trading_pair}
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
