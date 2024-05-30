from decimal import Decimal
from typing import Dict

import pandas as pd

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import PriceType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig, HistoricalCandlesConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider


class BacktestingDataProvider(MarketDataProvider):
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.start_time = None
        self.end_time = None
        self.prices = {}
        self._time = None

    def time(self):
        return self._time

    async def initialize_candles_feed(self, config: CandlesConfig):
        await self.get_candles_feed(config)

    def update_backtesting_time(self, start_time: int, end_time: int):
        if (self.start_time is None or self.end_time is None) or \
                (start_time < self.start_time or end_time > self.end_time):
            self.candles_feeds = {}
        self.start_time = start_time
        self.end_time = end_time
        self._time = start_time

    async def get_candles_feed(self, config: CandlesConfig):
        """
        Retrieves or creates and starts a candle feed based on the given configuration.
        If an existing feed has a higher or equal max_records, it is reused.
        :param config: CandlesConfig
        :return: Candle feed instance.
        """
        key = self._generate_candle_feed_key(config)
        existing_feed = self.candles_feeds.get(key, pd.DataFrame())

        if not existing_feed.empty:
            # Existing feed is sufficient, return it
            return existing_feed
        else:
            # Create a new feed or restart the existing one with updated max_records
            candle_feed = CandlesFactory.get_candle(config)
            candles_df = await candle_feed.get_historical_candles(config=HistoricalCandlesConfig(
                connector_name=config.connector,
                trading_pair=config.trading_pair,
                interval=config.interval,
                start_time=self.start_time,
                end_time=self.end_time,
            ))
            self.candles_feeds[key] = candles_df
            return candles_df

    def get_candles_df(self, connector_name: str, trading_pair: str, interval: str, max_records: int = 500):
        """
        Retrieves the candles for a trading pair from the specified connector.
        :param connector_name: str
        :param trading_pair: str
        :param interval: str
        :param max_records: int
        :return: Candles dataframe.
        """
        candles_df = self.candles_feeds.get(f"{connector_name}_{trading_pair}_{interval}")
        return candles_df[(candles_df["timestamp"] >= self.start_time) & (candles_df["timestamp"] <= self.end_time)]

    def get_price_by_type(self, connector_name: str, trading_pair: str, price_type: PriceType):
        """
        Retrieves the price for a trading pair from the specified connector based on the price type.
        :param connector_name: str
        :param trading_pair: str
        :param price_type: PriceType
        :return: Price.
        """
        return self.prices.get(f"{connector_name}_{trading_pair}", Decimal("1"))
