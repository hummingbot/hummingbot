
import asyncio
import aiohttp
import logging
import pandas as pd
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.logger import HummingbotLogger
from hummingbot.market.liquid.liquid_order_book import LiquidOrderBook
from hummingbot.market.liquid.liquid_active_order_tracker import LiquidActiveOrderTracker
from hummingbot.market.liquid.constants import Constants


class LiquidAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _baobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> (HummingbotLogger):
        if cls._baobds_logger is None:
            cls._baobds_logger = logging.getLogger(__name__)
        return cls._baobds_logger

    def __init__(self, symbols: Optional[List[str]]=None):
        super().__init__()

        self._symbols: Optional[List[str]] = symbols
        self._order_book_create_function = lambda: OrderBook()
    
        self.symbol_id_conversion_dict: Dict[str, int] = {}
    
    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)  #TODO: Not really sure what this does
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

        # Build the data frame
        all_markets_df: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index='currency_pair_code')

        btc_price: float = float(all_markets_df.loc['BTCUSDC'].last_traded_price)
        eth_price: float = float(all_markets_df.loc['ETHUSDC'].last_traded_price)
        usd_volume: float = [
            (
                quoteVolume * btc_price if trading_pair.endswith('BTC') else
                quoteVolume * eth_price if trading_pair.endswith('ETH') else
                quoteVolume
            )
            for trading_pair, quoteVolume in zip(
                all_markets_df.index,
                all_markets_df.volume_24h.astype('float')
            )
        ]
        
        all_markets_df.loc[:, 'USDVolume'] = usd_volume
        all_markets_df.loc[:, 'volume'] = all_markets_df.volume_24h
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
        * Market with invalid 'symbol'
        * Market with 'disabled' field set to True
        """
        return [
            item for item in exchange_markets_data
            if item['disabled'] is False
        ]

    async def get_trading_pairs(self) -> List[str]:
        """
        Extract trading_pairs information from all_markets_df generated
        in get_active_exchange_markets method.

        Along the way, also populate the self._symbol_id_conversion_dict,
        for downstream reference since Liquid API uses id instead of trading
        pair as the identifier
        """
        if not self._symbols:
            try:
                active_markets_df: pd.DataFrame = await self.get_active_exchange_markets()
                self._symbols = active_markets_df.index.tolist()
                
                self.symbol_id_conversion_dict = {
                    symbol: active_markets_df.loc[symbol, 'id']
                    for symbol in self._symbols
                }
   
            except Exception:
                self._symbols = []
                self.logger().network(
                    f"Error getting active exchange information.",
                    exe_info=True,
                    app_warning_msg=f"Error getting active exchange information. Check network connection."
                )
        return self._symbols
    
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
        product_id = self.symbol_id_conversion_dict.get(trading_pair, None)
        if not product_id:
            raise ValueError(f"Invalid trading pair {trading_pair} and product id {product_id} found")

        async with client.get(Constants.GET_SNAPSHOT_URL.format(id=product_id, full=full)) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Liquid market snapshot for {id}. "
                              f"HTTP status is {response.status}.")
            snapshot: Dict[str, Any] = await response.json()
            return snapshot

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        """
        Create tracking pairs by using trading pairs (symbols) fetched from
        active markets
        """
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:

            trading_pairs: List[str] = await self.get_trading_pairs()

            retval: Dict[str, OrderBookTrackerEntry] = {}
            number_of_pairs: int = len(trading_pairs)

            for index, trading_pair in enumerate(trading_pairs):

                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = LiquidOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"symbol": trading_pair}
                    )

                    order_book: OrderBook = self.order_book_create_function()
                    active_order_tracker: LiquidActiveOrderTracker = LiquidActiveOrderTracker()
                    bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)

                    order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                    retval[trading_pair] = OrderBookTrackerEntry(trading_pair, snapshot_timestamp, order_book)

                    self.logger().info(f"Initialized order book for {trading_pair}." 
                                    f"{index*1}/{number_of_pairs} completed")
                    # Each 1000 limit snapshot costs ?? requests and Liquid rate limit is ?? requests per second.
                    await asyncio.sleep(1.0) # Might need to be changed
                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                    await asyncio.sleep(5)
            return retval

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Liquid API does not have incremental snapshot (order book diff) feature as of Oct. 2019
        """
        pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass
