import os
from typing import Dict, List

import pandas as pd
import pandas_ta as ta  # noqa: F401
from pydantic import Field, field_validator

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import MarketDict
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class CandlesExampleConfig(StrategyV2ConfigBase):
    """
    Configuration for the Candles Example strategy.
    This example demonstrates how to use candles without requiring any trading markets.
    """
    script_file_name: str = os.path.basename(__file__)

    # Override controllers_config to ensure no controllers are loaded
    controllers_config: List[str] = Field(default=[], exclude=True)

    # Candles configuration - user can modify these
    candles_config: List[CandlesConfig] = Field(
        default_factory=lambda: [
            CandlesConfig(connector="binance", trading_pair="ETH-USDT", interval="1m", max_records=1000),
            CandlesConfig(connector="binance", trading_pair="ETH-USDT", interval="1h", max_records=1000),
            CandlesConfig(connector="binance", trading_pair="ETH-USDT", interval="1w", max_records=200),
        ],
        json_schema_extra={
            "prompt": "Enter candles configurations (format: connector.pair.interval.max_records, separated by colons): ",
            "prompt_on_new": True,
        }
    )

    @field_validator('candles_config', mode="before")
    @classmethod
    def parse_candles_config(cls, v) -> List[CandlesConfig]:
        # Handle string input (user provided)
        if isinstance(v, str):
            return cls.parse_candles_config_str(v)
        # Handle list input (could be already CandlesConfig objects or dicts)
        elif isinstance(v, list):
            # If empty list, return as is
            if not v:
                return v
            # If already CandlesConfig objects, return as is
            if isinstance(v[0], CandlesConfig):
                return v
            # Otherwise, let Pydantic handle the conversion
            return v
        # Return as-is and let Pydantic validate
        return v

    @staticmethod
    def parse_candles_config_str(v: str) -> List[CandlesConfig]:
        configs = []
        if v.strip():
            entries = v.split(':')
            for entry in entries:
                parts = entry.split('.')
                if len(parts) != 4:
                    raise ValueError(f"Invalid candles config format in segment '{entry}'. "
                                     "Expected format: 'exchange.tradingpair.interval.maxrecords'")
                connector, trading_pair, interval, max_records_str = parts
                try:
                    max_records = int(max_records_str)
                except ValueError:
                    raise ValueError(f"Invalid max_records value '{max_records_str}' in segment '{entry}'. "
                                     "max_records should be an integer.")
                config = CandlesConfig(
                    connector=connector,
                    trading_pair=trading_pair,
                    interval=interval,
                    max_records=max_records
                )
                configs.append(config)
        return configs

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """
        This candles example doesn't require any trading markets.
        We only need data connections which will be handled by the MarketDataProvider.
        """
        # Return empty markets since we're not trading, just consuming data
        return markets


class CandlesExample(StrategyV2Base):
    """
    This strategy demonstrates how to use candles data without requiring any trading markets.

    Key Features:
    - Configurable candles via config.candles_config
    - No trading markets required
    - Uses MarketDataProvider for clean candles access
    - Displays technical indicators (RSI, Bollinger Bands, EMA)
    - Shows multiple timeframes in status

    Available intervals: |1s|1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d|3d|1w|1M|

    The candles configuration is defined in the config class and automatically
    initialized by the MarketDataProvider. No manual candle management required!
    """

    def __init__(self, connectors: Dict[str, ConnectorBase], config: CandlesExampleConfig):
        super().__init__(connectors, config)
        # Note: self.config is already set by parent class

        # Initialize candles based on config
        for candles_config in self.config.candles_config:
            self.market_data_provider.initialize_candles_feed(candles_config)
        self.logger().info(f"Initialized {len(self.config.candles_config)} candle feeds successfully")

    @property
    def all_candles_ready(self):
        """
        Checks if all configured candles are ready.
        """
        for candle in self.config.candles_config:
            candles_feed = self.market_data_provider.get_candles_feed(candle)
            # Check if the feed is ready and has data
            if not candles_feed.ready or candles_feed.candles_df.empty:
                return False
        return True

    async def on_stop(self):
        """
        Clean shutdown - the MarketDataProvider will handle stopping candles automatically.
        """
        self.logger().info("Stopping Candles Example strategy...")
        # The MarketDataProvider and candles feeds will be stopped automatically
        # by the parent class when the strategy stops

    def format_status(self) -> str:
        """
        Displays all configured candles with technical indicators.
        """
        lines = []
        lines.extend(["\n" + "=" * 100])
        lines.extend(["                              CANDLES EXAMPLE - MARKET DATA"])
        lines.extend(["=" * 100])

        if self.all_candles_ready:
            for i, candle_config in enumerate(self.config.candles_config):
                # Get candles dataframe from market data provider
                # Request more data for indicator calculation, but only display the last few
                candles_df = self.market_data_provider.get_candles_df(
                    connector_name=candle_config.connector,
                    trading_pair=candle_config.trading_pair,
                    interval=candle_config.interval,
                    max_records=50  # Get enough data for indicators
                )

                if candles_df is not None and not candles_df.empty:
                    # Add technical indicators
                    candles_df = candles_df.copy()  # Avoid modifying original

                    # Calculate indicators if we have enough data
                    if len(candles_df) >= 20:
                        candles_df.ta.rsi(length=14, append=True)
                        candles_df.ta.bbands(length=20, std=2, append=True)
                        candles_df.ta.ema(length=14, append=True)

                    candles_df["timestamp"] = pd.to_datetime(candles_df["timestamp"], unit="s")

                    # Display candles info
                    lines.extend([f"\n[{i + 1}] {candle_config.connector.upper()} | {candle_config.trading_pair} | {candle_config.interval}"])
                    lines.extend(["-" * 80])

                    # Show last 5 rows with basic columns (OHLC + volume)
                    basic_columns = ["timestamp", "open", "high", "low", "close", "volume"]
                    indicator_columns = []

                    # Include indicators if they exist and have data
                    if "RSI_14" in candles_df.columns and candles_df["RSI_14"].notna().any():
                        indicator_columns.append("RSI_14")
                    if "BBP_20_2.0_2.0" in candles_df.columns and candles_df["BBP_20_2.0_2.0"].notna().any():
                        indicator_columns.append("BBP_20_2.0_2.0")
                    if "EMA_14" in candles_df.columns and candles_df["EMA_14"].notna().any():
                        indicator_columns.append("EMA_14")

                    display_columns = basic_columns + indicator_columns
                    display_df = candles_df.tail(5)[display_columns]
                    # Round only numeric columns, exclude datetime columns like timestamp
                    numeric_columns = display_df.select_dtypes(include=[float, int]).columns
                    display_df[numeric_columns] = display_df[numeric_columns].round(4)
                    lines.extend(["    " + line for line in display_df.to_string(index=False).split("\n")])

                    # Current values
                    current = candles_df.iloc[-1]
                    lines.extend([""])
                    current_price = f"Current Price: ${current['close']:.4f}"

                    # Add indicator values if available
                    if "RSI_14" in candles_df.columns and pd.notna(current.get('RSI_14')):
                        current_price += f" | RSI: {current['RSI_14']:.2f}"

                    if "BBP_20_2.0_2.0" in candles_df.columns and pd.notna(current.get('BBP_20_2.0_2.0')):
                        current_price += f" | BB%: {current['BBP_20_2.0_2.0']:.3f}"

                    lines.extend([f"    {current_price}"])
                else:
                    lines.extend([f"\n[{i + 1}] {candle_config.connector.upper()} | {candle_config.trading_pair} | {candle_config.interval}"])
                    lines.extend(["    No data available yet..."])
        else:
            lines.extend(["\n⏳ Waiting for candles data to be ready..."])
            for candle_config in self.config.candles_config:
                candles_feed = self.market_data_provider.get_candles_feed(candle_config)
                ready = candles_feed.ready and not candles_feed.candles_df.empty
                status = "✅" if ready else "❌"
                lines.extend([f"    {status} {candle_config.connector}.{candle_config.trading_pair}.{candle_config.interval}"])

        lines.extend(["\n" + "=" * 100 + "\n"])
        return "\n".join(lines)
