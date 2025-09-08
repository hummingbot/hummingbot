import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import pandas as pd

from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    api_keys_from_connector_config_map,
    get_connector_class,
)
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import GroupedSetDict, LazyDict, PriceType, TradeType
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

    def __init__(self,
                 connectors: Dict[str, ConnectorBase],
                 rates_update_interval: int = 60):
        self.candles_feeds = {}  # Stores instances of candle feeds
        self.connectors = connectors  # Stores instances of connectors
        self._rates_update_task = None
        self._rates_update_interval = rates_update_interval
        self._rates = {}
        self._non_trading_connectors = LazyDict[str, ConnectorBase](self._create_non_trading_connector)
        self._rates_required = GroupedSetDict[str, ConnectorPair]()
        self.conn_settings = AllConnectorSettings.get_connector_settings()

    def stop(self):
        for candle_feed in self.candles_feeds.values():
            candle_feed.stop()
        if self._rates_update_task:
            self._rates_update_task.cancel()
            self._rates_update_task = None
        self.candles_feeds.clear()
        self._rates_required.clear()

    @property
    def ready(self) -> bool:
        all_connectors_running = all(connector.ready for connector in self.connectors.values())
        all_candles_feeds_running = all(feed.ready for feed in self.candles_feeds.values())
        return all_connectors_running and all_candles_feeds_running

    def time(self):
        return time.time()

    def initialize_rate_sources(self, connector_pairs: List[ConnectorPair]):
        """
        Initializes a rate source based on the given connector pair.
        :param connector_pairs: List[ConnectorPair]
        """
        for connector_pair in connector_pairs:
            connector_name, _ = connector_pair
            if connector_pair.is_amm_connector():
                self._rates_required.add_or_update("gateway", connector_pair)
                continue
            self._rates_required.add_or_update(connector_name, connector_pair)
        if not self._rates_update_task:
            self._rates_update_task = safe_ensure_future(self.update_rates_task())

    def remove_rate_sources(self, connector_pairs: List[ConnectorPair]):
        """
        Removes rate sources for the given connector pairs.
        :param connector_pairs: List[ConnectorPair]
        """
        for connector_pair in connector_pairs:
            connector_name, _ = connector_pair
            if connector_pair.is_amm_connector():
                self._rates_required.remove("gateway", connector_pair)
                continue
            self._rates_required.remove(connector_name, connector_pair)

        # Stop the rates update task if no more rates are required
        if len(self._rates_required) == 0 and self._rates_update_task:
            self._rates_update_task.cancel()
            self._rates_update_task = None

    async def update_rates_task(self):
        """
        Updates the rates for all rate sources.
        """
        try:
            while True:
                # Exit if no more rates to update
                if len(self._rates_required) == 0:
                    break

                rate_oracle = RateOracle.get_instance()
                for connector, connector_pairs in self._rates_required.items():
                    if connector == "gateway":
                        tasks = []
                        gateway_client = GatewayHttpClient.get_instance()
                        for connector_pair in connector_pairs:
                            # Handle new connector format like "jupiter/router"
                            connector_name = connector_pair.connector_name
                            base, quote = connector_pair.trading_pair.split("-")

                            # Parse connector to get chain and connector name
                            # First try to get chain and network from gateway
                            try:
                                chain, network, error = await gateway_client.get_connector_chain_network(
                                    connector_name
                                )
                                if error:
                                    self.logger().warning(f"Could not get chain/network for {connector_name}: {error}")
                                    continue

                                tasks.append(
                                    gateway_client.get_price(
                                        chain=chain, network=network, connector=connector_name,
                                        base_asset=base, quote_asset=quote, amount=Decimal("1"),
                                        side=TradeType.BUY))
                            except Exception as e:
                                self.logger().warning(f"Error getting chain info for {connector_name}: {e}")
                                continue
                        try:
                            if tasks:
                                results = await asyncio.gather(*tasks, return_exceptions=True)
                                for connector_pair, rate in zip(connector_pairs, results):
                                    if isinstance(rate, Exception):
                                        self.logger().error(f"Error fetching price for {connector_pair.trading_pair}: {rate}")
                                    elif rate and "price" in rate:
                                        rate_oracle.set_price(connector_pair.trading_pair, Decimal(rate["price"]))
                        except Exception as e:
                            self.logger().error(f"Error fetching prices from {connector_pairs}: {e}", exc_info=True)
                    else:
                        connector_instance = self._non_trading_connectors[connector]
                        prices = await self._safe_get_last_traded_prices(connector_instance,
                                                                         [pair.trading_pair for pair in connector_pairs])
                        for pair, rate in prices.items():
                            rate_oracle.set_price(pair, rate)

                await asyncio.sleep(self._rates_update_interval)
        except asyncio.CancelledError:
            raise
        finally:
            self._rates_update_task = None

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
            # Stop the existing feed if it exists before creating a new one
            if existing_feed and hasattr(existing_feed, 'stop'):
                existing_feed.stop()

            # Create a new feed with updated max_records
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

    def get_connector_with_fallback(self, connector_name: str) -> ConnectorBase:
        """
        Retrieves a connector instance with fallback to non-trading connector.
        Prefers existing connected connector with API keys if available,
        otherwise creates a non-trading connector for public data access.
        :param connector_name: str
        :return: ConnectorBase
        """
        # Try to get existing connector first (has API keys)
        connector = self.connectors.get(connector_name)
        if connector:
            return connector

        # Fallback to non-trading connector for public data
        return self.get_non_trading_connector(connector_name)

    def get_non_trading_connector(self, connector_name: str):
        """
        Retrieves a non-trading connector from cache or creates one if not exists.
        Uses the _non_trading_connectors cache to avoid creating multiple instances.
        :param connector_name: str
        :return: ConnectorBase
        """
        return self._non_trading_connectors[connector_name]

    def _create_non_trading_connector(self, connector_name: str):
        """
        Creates a new non-trading connector instance.
        This is the factory method used by the LazyDict cache.
        :param connector_name: str
        :return: ConnectorBase
        """
        conn_setting = self.conn_settings.get(connector_name)
        if conn_setting is None:
            self.logger().error(f"Connector {connector_name} not found")
            raise ValueError(f"Connector {connector_name} not found")

        init_params = conn_setting.conn_init_parameters(
            trading_pairs=[],
            trading_required=False,
            api_keys=self.get_connector_config_map(connector_name),
        )
        connector_class = get_connector_class(connector_name)
        connector = connector_class(**init_params)
        return connector

    @staticmethod
    def get_connector_config_map(connector_name: str):
        connector_config = AllConnectorSettings.get_connector_config_keys(connector_name)
        if getattr(connector_config, "use_auth_for_public_endpoints", False):
            api_keys = api_keys_from_connector_config_map(ClientConfigAdapter(connector_config))
        else:
            api_keys = {key: "" for key in connector_config.__class__.model_fields.keys() if key != "connector"}
        return api_keys

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
        connector = self.get_connector_with_fallback(connector_name)
        return connector.get_order_book(trading_pair)

    def get_price_by_type(self, connector_name: str, trading_pair: str, price_type: PriceType):
        """
        Retrieves the price for a trading pair from the specified connector.
        :param connector_name: str
        :param trading_pair: str
        :param price_type: str
        :return: Price instance.
        """
        connector = self.get_connector_with_fallback(connector_name)
        return connector.get_price_by_type(trading_pair, price_type)

    def get_funding_info(self, connector_name: str, trading_pair: str):
        """
        Retrieves the funding rate for a trading pair from the specified connector.
        :param connector_name: str
        :param trading_pair: str
        :return: Funding rate.
        """
        connector = self.get_connector_with_fallback(connector_name)
        return connector.get_funding_info(trading_pair)

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

    async def get_historical_candles_df(self, connector_name: str, trading_pair: str, interval: str,
                                        start_time: Optional[int] = None, end_time: Optional[int] = None,
                                        max_records: Optional[int] = None, max_cache_records: int = 10000):
        """
        Retrieves historical candles with intelligent caching and partial fetch optimization.

        :param connector_name: str
        :param trading_pair: str
        :param interval: str
        :param start_time: Start timestamp in seconds (optional)
        :param end_time: End timestamp in seconds (optional)
        :param max_records: Maximum number of records to return (optional)
        :param max_cache_records: Maximum records to keep in cache for efficiency
        :return: Candles dataframe for the requested range
        """
        import time

        from hummingbot.data_feed.candles_feed.data_types import HistoricalCandlesConfig

        # Set default end_time to current time if not provided
        if end_time is None:
            end_time = int(time.time())

        # Calculate start_time based on max_records if not provided
        if start_time is None and max_records is not None:
            # Get interval in seconds to calculate approximate start time
            candles_feed = self.get_candles_feed(CandlesConfig(
                connector=connector_name,
                trading_pair=trading_pair,
                interval=interval,
                max_records=min(100, max_records)  # Small initial fetch to get interval info
            ))
            interval_seconds = candles_feed.interval_in_seconds
            start_time = end_time - (max_records * interval_seconds)

        if start_time is None:
            # Fallback to regular method if no time range specified
            return self.get_candles_df(connector_name, trading_pair, interval, max_records or 500)

        # Get or create candles feed with extended cache
        candles_feed = self.get_candles_feed(CandlesConfig(
            connector=connector_name,
            trading_pair=trading_pair,
            interval=interval,
            max_records=max_cache_records
        ))

        # Check if we have cached data and what range it covers
        current_df = candles_feed.candles_df

        if len(current_df) > 0:
            cached_start = int(current_df['timestamp'].iloc[0])
            cached_end = int(current_df['timestamp'].iloc[-1])

            # Check if requested range is completely covered by cache
            if start_time >= cached_start and end_time <= cached_end:
                # Filter existing data for requested range
                filtered_df = current_df[
                    (current_df['timestamp'] >= start_time) &
                    (current_df['timestamp'] <= end_time)
                ]
                return filtered_df.iloc[-max_records:] if max_records else filtered_df

            # Partial cache hit - determine what additional data we need
            fetch_start = min(start_time, cached_start)
            fetch_end = max(end_time, cached_end)

            # If the extended range is too large, limit it
            max_fetch_range = max_cache_records * candles_feed.interval_in_seconds
            if (fetch_end - fetch_start) > max_fetch_range:
                # Prioritize the requested range
                if start_time < cached_start:
                    fetch_start = max(start_time, fetch_end - max_fetch_range)
                else:
                    fetch_end = min(end_time, fetch_start + max_fetch_range)
        else:
            # No cached data - fetch requested range with some buffer
            buffer_records = min(max_cache_records // 4, 1000)  # 25% buffer or 1000 records max
            interval_seconds = candles_feed.interval_in_seconds
            buffer_time = buffer_records * interval_seconds

            fetch_start = start_time - buffer_time
            fetch_end = end_time

        # Fetch historical data
        try:
            historical_config = HistoricalCandlesConfig(
                connector_name=connector_name,
                trading_pair=trading_pair,
                interval=interval,
                start_time=fetch_start,
                end_time=fetch_end
            )

            new_df = await candles_feed.get_historical_candles(historical_config)

            if len(new_df) > 0:
                # Merge with existing data if any
                if len(current_df) > 0:
                    combined_df = pd.concat([current_df, new_df], ignore_index=True)
                    # Remove duplicates and sort
                    combined_df = combined_df.drop_duplicates(subset=['timestamp'])
                    combined_df = combined_df.sort_values('timestamp')

                    # Limit cache size
                    if len(combined_df) > max_cache_records:
                        # Keep most recent records
                        combined_df = combined_df.iloc[-max_cache_records:]

                    # Update the candles feed cache
                    candles_feed._candles.clear()
                    for _, row in combined_df.iterrows():
                        candles_feed._candles.append(row.values)
                else:
                    # Update the candles feed cache with new data
                    candles_feed._candles.clear()
                    for _, row in new_df.iloc[-max_cache_records:].iterrows():
                        candles_feed._candles.append(row.values)

                # Return filtered data for requested range
                final_df = candles_feed.candles_df
                filtered_df = final_df[
                    (final_df['timestamp'] >= start_time) &
                    (final_df['timestamp'] <= end_time)
                ]
                return filtered_df.iloc[-max_records:] if max_records else filtered_df

        except Exception as e:
            self.logger().warning(f"Error fetching historical candles: {e}. Falling back to regular method.")

        # Fallback to existing method if historical fetch fails
        return self.get_candles_df(connector_name, trading_pair, interval, max_records or 500)

    def get_trading_pairs(self, connector_name: str):
        """
        Retrieves the trading pairs from the specified connector.
        :param connector_name: str
        :return: List of trading pairs.
        """
        connector = self.get_connector_with_fallback(connector_name)
        return connector.trading_pairs

    def get_trading_rules(self, connector_name: str, trading_pair: str):
        """
        Retrieves the trading rules from the specified connector.
        :param connector_name: str
        :return: Trading rules.
        """
        connector = self.get_connector_with_fallback(connector_name)
        return connector.trading_rules[trading_pair]

    def quantize_order_price(self, connector_name: str, trading_pair: str, price: Decimal):
        connector = self.get_connector_with_fallback(connector_name)
        return connector.quantize_order_price(trading_pair, price)

    def quantize_order_amount(self, connector_name: str, trading_pair: str, amount: Decimal):
        connector = self.get_connector_with_fallback(connector_name)
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
        connector = self.get_connector_with_fallback(connector_name)
        order_book = connector.get_order_book(trading_pair)
        return order_book.get_price_for_volume(is_buy, volume)

    def get_order_book_snapshot(self, connector_name, trading_pair) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Retrieves the order book snapshot for a trading pair from the specified connector, as a tuple of bid and ask in
        DataFrame format.
        :param connector_name: str
        :param trading_pair: str
        :return: Tuple of bid and ask in DataFrame format.
        """
        connector = self.get_connector_with_fallback(connector_name)
        order_book = connector.get_order_book(trading_pair)
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
        connector = self.get_connector_with_fallback(connector_name)
        order_book = connector.get_order_book(trading_pair)
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
        connector = self.get_connector_with_fallback(connector_name)
        order_book = connector.get_order_book(trading_pair)
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
        connector = self.get_connector_with_fallback(connector_name)
        order_book = connector.get_order_book(trading_pair)
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
        connector = self.get_connector_with_fallback(connector_name)
        order_book = connector.get_order_book(trading_pair)
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
            tasks = [self._safe_get_last_traded_price(connector, trading_pair) for trading_pair in trading_pairs]
            prices = await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout)
            return {pair: Decimal(rate) for pair, rate in zip(trading_pairs, prices)}
        except Exception as e:
            logging.error(f"Error getting last traded prices in connector {connector} for trading pairs {trading_pairs}: {e}")
            return {}

    async def _safe_get_last_traded_price(self, connector, trading_pair):
        try:
            last_traded = await connector._get_last_traded_price(trading_pair=trading_pair)
            return Decimal(last_traded)
        except Exception as e:
            logging.error(f"Error getting last traded price in connector {connector} for trading pair {trading_pair}: {e}")
            return Decimal(0)
