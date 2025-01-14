import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter, get_connector_class
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import PriceType, TradeType
from hummingbot.core.data_type.order_book_query_result import OrderBookQueryResult
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy_v2.executors.data_types import ConnectorPair


class MarketDataProvider:
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, connectors: Dict[str, ConnectorBase], rates_update_interval: int = 60):
        self.candles_feeds = {}  # Stores instances of candle feeds
        self.connectors = connectors  # Stores instances of connectors
        self._rates_update_task = None
        self._rates_update_interval = rates_update_interval
        self._rates = {}
        self._rate_sources = {}
        self._rates_required = {}
        self.gateway_client = GatewayHttpClient.get_instance()
        self.conn_settings = AllConnectorSettings.get_connector_settings()

    def stop(self):
        for candle_feed in self.candles_feeds.values():
            candle_feed.stop()
        if self._rates_update_task:
            self._rates_update_task.cancel()
            self._rates_update_task = None
        self.candles_feeds.clear()

    @property
    def ready(self) -> bool:
        # TODO: unify the ready property for connectors and feeds
        all_connectors_running = all(connector.ready for connector in self.connectors.values())
        all_candles_feeds_running = all(feed.ready for feed in self.candles_feeds.values())
        return all_connectors_running and all_candles_feeds_running

    def time(self):
        return time.time()

    def initialize_rate_sources(self, connector_pairs: List[ConnectorPair]):
        """
        Initializes a rate source based on the given connector pair.
        :param connector_pair: ConnectorPair
        """
        for connector_pair in connector_pairs:
            if connector_pair.is_amm_connector():
                if "gateway" not in self._rates_required:
                    self._rates_required["gateway"] = []
                self._rates_required["gateway"].append(connector_pair)
                continue
            if connector_pair.connector_name not in self._rates_required:
                self._rates_required[connector_pair.connector_name] = []
            self._rates_required[connector_pair.connector_name].append(connector_pair)
            if connector_pair.connector_name not in self._rate_sources:
                self._rate_sources[connector_pair.connector_name] = self.get_non_trading_connector(
                    connector_pair.connector_name)
        if not self._rates_update_task:
            self._rates_update_task = safe_ensure_future(self.update_rates_task())

    async def update_rates_task(self):
        """
        Updates the rates for all rate sources.
        """
        while True:
            rate_oracle = RateOracle.get_instance()
            for connector, connector_pairs in self._rates_required.items():
                if connector == "gateway":
                    tasks = []
                    for connector_pair in connector_pairs:
                        connector, chain, network = connector_pair.connector_name.split("_")
                        base, quote = connector_pair.trading_pair.split("-")
                        tasks.append(
                            self.gateway_client.get_price(
                                chain=chain, network=network, connector=connector,
                                base_asset=base, quote_asset=quote, amount=Decimal("1"),
                                side=TradeType.BUY))
                    try:
                        results = await asyncio.gather(*tasks)
                        for connector_pair, rate in zip(connector_pairs, results):
                            rate_oracle.set_price(connector_pair.trading_pair, Decimal(rate["price"]))
                    except Exception as e:
                        self.logger().error(f"Error fetching prices from {connector_pairs}: {e}", exc_info=True)
                else:
                    connector = self._rate_sources[connector]
                    prices = await self._safe_get_last_traded_prices(connector,
                                                                     [pair.trading_pair for pair in connector_pairs])
                    for pair, rate in prices.items():
                        rate_oracle.set_price(pair, rate)
            await asyncio.sleep(self._rates_update_interval)

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

    def get_non_trading_connector(self, connector_name: str):
        conn_setting = self.conn_settings.get(connector_name)
        if conn_setting is None:
            self.logger().error(f"Connector {connector_name} not found")
            raise ValueError(f"Connector {connector_name} not found")

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector_config = AllConnectorSettings.get_connector_config_keys(connector_name)
        api_keys = {key: "" for key in connector_config.__fields__.keys() if key != "connector"}
        init_params = conn_setting.conn_init_parameters(
            trading_pairs=[],
            trading_required=False,
            api_keys=api_keys,
            client_config_map=client_config_map,
        )
        connector_class = get_connector_class(connector_name)
        connector = connector_class(**init_params)
        return connector

    def get_balance(self, connector_name: str, asset: str):
        connector = self.get_connector(connector_name)
        return connector.get_balance(asset)

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

    def get_trading_rules(self, connector_name: str, trading_pair: str):
        """
        Retrieves the trading rules from the specified connector.
        :param connector_name: str
        :return: Trading rules.
        """
        connector = self.get_connector(connector_name)
        return connector.trading_rules[trading_pair]

    def quantize_order_price(self, connector_name: str, trading_pair: str, price: Decimal):
        connector = self.get_connector(connector_name)
        return connector.quantize_order_price(trading_pair, price)

    def quantize_order_amount(self, connector_name: str, trading_pair: str, amount: Decimal):
        connector = self.get_connector(connector_name)
        return connector.quantize_order_amount(trading_pair, amount)

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

    def get_price_for_quote_volume(self, connector_name: str, trading_pair: str, quote_volume: float,
                                   is_buy: bool) -> OrderBookQueryResult:
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

    def get_volume_for_price(self, connector_name: str, trading_pair: str, price: float,
                             is_buy: bool) -> OrderBookQueryResult:
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

    def get_quote_volume_for_price(self, connector_name: str, trading_pair: str, price: float,
                                   is_buy: bool) -> OrderBookQueryResult:
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

    def get_rate(self, pair: str) -> Decimal:
        """
        Finds a conversion rate for a given trading pair, this can be direct or indirect prices as
        long as it can find a route to achieve this.

        :param pair: A trading pair, e.g. BTC-USDT
        :return A conversion rate
        """
        return RateOracle.get_instance().get_pair_rate(pair)

    async def _safe_get_last_traded_prices(self, connector, trading_pairs, timeout=5):
        try:
            last_traded = await connector.get_last_traded_prices(trading_pairs=trading_pairs)
            return {pair: Decimal(rate) for pair, rate in last_traded.items()}
        except Exception as e:
            logging.error(
                f"Error getting last traded prices in connector {connector} for trading pairs {trading_pairs}: {e}")
            return {}
