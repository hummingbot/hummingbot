import time
from typing import Dict, List, Tuple

import pandas as pd

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import PriceType
from hummingbot.core.data_type.order_book_query_result import OrderBookQueryResult
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig


class MarketDataProvider:
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        self.candles_feeds = {}  # Stores instances of candle feeds
        self.connectors = connectors  # Stores instances of connectors

    def stop(self):
        for candle_feed in self.candles_feeds.values():
            candle_feed.stop()
        self.candles_feeds.clear()

    @property
    def ready(self) -> bool:
        # TODO: unify the ready property for connectors and feeds
        all_connectors_running = all(connector.ready for connector in self.connectors.values())
        all_candles_feeds_running = all(feed.ready for feed in self.candles_feeds.values())
        return all_connectors_running and all_candles_feeds_running

    def time(self):
        return time.time()

    def initialize_candles_feed(self, config: CandlesConfig):
        """
        Initializes a candle feed based on the given configuration.
        :param config: CandlesConfig
        """
        self.get_candles_feed(config)

    def initialize_candles_feed_list(self, config_list: List[CandlesConfig]):
        """
        Initializes a list of candle feeds based on the given configurations.
        :param config_list: List[CandlesConfig]
        """
        for config in config_list:
            self.get_candles_feed(config)

    def get_candles_feed(self, config: CandlesConfig):
        """
        Retrieves or creates and starts a candle feed based on the given configuration.
        If an existing feed has a higher or equal max_records, it is reused.
        :param config: CandlesConfig
        :return: Candle feed instance.
        """
        key = self._generate_candle_feed_key(config)
        existing_feed = self.candles_feeds.get(key)

        if existing_feed and existing_feed.max_records >= config.max_records:
            # Existing feed is sufficient, return it
            return existing_feed
        else:
            # Create a new feed or restart the existing one with updated max_records
            candle_feed = CandlesFactory.get_candle(config)
            self.candles_feeds[key] = candle_feed
            if hasattr(candle_feed, 'start'):
                candle_feed.start()
            return candle_feed

    @staticmethod
    def _generate_candle_feed_key(config: CandlesConfig) -> str:
        """
        Generates a unique key for a candle feed based on its configuration.
        :param config: CandlesConfig
        :return: Unique key as a string.
        """
        return f"{config.connector}_{config.trading_pair}_{config.interval}"

    def stop_candle_feed(self, config: CandlesConfig):
        """
        Stops a candle feed based on the given configuration.
        :param config: CandlesConfig
        """
        key = self._generate_candle_feed_key(config)
        candle_feed = self.candles_feeds.get(key)
        if candle_feed and hasattr(candle_feed, 'stop'):
            candle_feed.stop()
            del self.candles_feeds[key]

    def get_connector(self, connector_name: str) -> ConnectorBase:
        """
        Retrieves a connector instance based on the given name.
        :param connector_name: str
        :return: ConnectorBase
        """
        connector = self.connectors.get(connector_name)
        if not connector:
            raise ValueError(f"Connector {connector_name} not found.")
        return connector

    def get_order_book(self, connector_name: str, trading_pair: str):
        """
        Retrieves the order book for a trading pair from the specified connector.
        :param connector_name: str
        :param trading_pair: str
        :return: Order book instance.
        """
        connector = self.get_connector(connector_name)
        return connector.get_order_book(trading_pair)

    def get_price_by_type(self, connector_name: str, trading_pair: str, price_type: PriceType):
        """
        Retrieves the price for a trading pair from the specified connector.
        :param connector_name: str
        :param trading_pair: str
        :param price_type: str
        :return: Price instance.
        """
        connector = self.get_connector(connector_name)
        return connector.get_price_by_type(trading_pair, price_type)

    def get_candles_df(self, connector_name: str, trading_pair: str, interval: str, max_records: int = 500):
        """
        Retrieves the candles for a trading pair from the specified connector.
        :param connector_name: str
        :param trading_pair: str
        :param interval: str
        :param max_records: int
        :return: Candles dataframe.
        """
        candles = self.get_candles_feed(CandlesConfig(
            connector=connector_name,
            trading_pair=trading_pair,
            interval=interval,
            max_records=max_records,
        ))
        return candles.candles_df.iloc[-max_records:]

    def get_trading_pairs(self, connector_name: str):
        """
        Retrieves the trading pairs from the specified connector.
        :param connector_name: str
        :return: List of trading pairs.
        """
        connector = self.get_connector(connector_name)
        return connector.trading_pairs

    def get_price_for_volume(self, connector_name: str, trading_pair: str, volume: float,
                             is_buy: bool) -> OrderBookQueryResult:
        """
        Gets the price for a specified volume on the order book.

        :param connector_name: The name of the connector.
        :param trading_pair: The trading pair for which to retrieve the data.
        :param volume: The volume for which to find the price.
        :param is_buy: True if buying, False if selling.
        :return: OrderBookQueryResult containing the result of the query.
        """

        order_book = self.get_order_book(connector_name, trading_pair)
        return order_book.get_price_for_volume(is_buy, volume)

    def get_order_book_snapshot(self, connector_name, trading_pair) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Retrieves the order book snapshot for a trading pair from the specified connector, as a tuple of bid and ask in
        DataFrame format.
        :param connector_name: str
        :param trading_pair: str
        :return: Tuple of bid and ask in DataFrame format.
        """
        order_book = self.get_order_book(connector_name, trading_pair)
        return order_book.snapshot

    def get_price_for_quote_volume(self, connector_name: str, trading_pair: str, quote_volume: float, is_buy: bool) -> OrderBookQueryResult:
        """
        Gets the price for a specified quote volume on the order book.

        :param connector_name: The name of the connector.
        :param trading_pair: The trading pair for which to retrieve the data.
        :param quote_volume: The quote volume for which to find the price.
        :param is_buy: True if buying, False if selling.
        :return: OrderBookQueryResult containing the result of the query.
        """
        order_book = self.get_order_book(connector_name, trading_pair)
        return order_book.get_price_for_quote_volume(is_buy, quote_volume)

    def get_volume_for_price(self, connector_name: str, trading_pair: str, price: float, is_buy: bool) -> OrderBookQueryResult:
        """
        Gets the volume for a specified price on the order book.

        :param connector_name: The name of the connector.
        :param trading_pair: The trading pair for which to retrieve the data.
        :param price: The price for which to find the volume.
        :param is_buy: True if buying, False if selling.
        :return: OrderBookQueryResult containing the result of the query.
        """
        order_book = self.get_order_book(connector_name, trading_pair)
        return order_book.get_volume_for_price(is_buy, price)

    def get_quote_volume_for_price(self, connector_name: str, trading_pair: str, price: float, is_buy: bool) -> OrderBookQueryResult:
        """
        Gets the quote volume for a specified price on the order book.

        :param connector_name: The name of the connector.
        :param trading_pair: The trading pair for which to retrieve the data.
        :param price: The price for which to find the quote volume.
        :param is_buy: True if buying, False if selling.
        :return: OrderBookQueryResult containing the result of the query.
        """
        order_book = self.get_order_book(connector_name, trading_pair)
        return order_book.get_quote_volume_for_price(is_buy, price)

    def get_vwap_for_volume(self, connector_name: str, trading_pair: str, volume: float,
                            is_buy: bool) -> OrderBookQueryResult:
        """
        Gets the VWAP (Volume Weighted Average Price) for a specified volume on the order book.

        :param connector_name: The name of the connector.
        :param trading_pair: The trading pair for which to retrieve the data.
        :param volume: The volume for which to calculate the VWAP.
        :param is_buy: True if buying, False if selling.
        :return: OrderBookQueryResult containing the result of the query.
        """
        order_book = self.get_order_book(connector_name, trading_pair)
        return order_book.get_vwap_for_volume(is_buy, volume)
