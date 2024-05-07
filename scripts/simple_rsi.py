import os
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase


class SimpleRSIConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    exchange: str = Field("hyperliquid_perpetual", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Exchange where the bot will trade"))
    trading_pair: str = Field("ETH-USD", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Trading pair where the bot will place orders"))
    candles_exchange: str = Field("binance_perpetual", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Candles exchange where the bot will fetch data"))
    candles_pair: str = Field("ETH-USDT", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Candles pair where the bot will fetch data"))
    candles_interval: str = Field(default="1m", client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Candle interval (1s/1m/5m/1h)"))
    candles_length: int = Field(default=60, gt=0, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Number of candles used to calculate R"))
    order_amount_usd: Decimal = Field(20, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Order amount (denominated in quote asset)"))
    leverage: int = Field(10, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Leverage scalar to use"))
    rsi_low: float = Field(default=30, gt=0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "RSI lower bound to enter long position"))
    rsi_high: float = Field(default=70, gt=0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "RSI upper bound to enter short position"))


class SimpleRSI(DirectionalStrategyBase):
    """
    This strategy uses RSI (Relative Strength Index) to generate trading signals and execute trades based on the RSI values.
    It defines the specific parameters and configurations for the RSI strategy.
    """

    @classmethod
    def init_markets(cls, config: SimpleRSIConfig):
        cls.markets = {config.exchange: {config.trading_pair}}
        cls.candles = [CandlesFactory.get_candle(CandlesConfig(connector=config.candles_exchange,
                                                               trading_pair=config.candles_pair,
                                                               interval=config.candles_interval,
                                                               max_records=config.candles_length * 2))]

    def __init__(self, connectors: Dict[str, ConnectorBase], config: SimpleRSIConfig):
        super().__init__(connectors)
        self.config = config
        self.directional_strategy_name = self.config.script_file_name
        self.exchange: str = self.config.exchange
        self.trading_pair: str = self.config.trading_pair
        self.order_amount_usd = self.config.order_amount_usd
        self.leverage = self.config.leverage

    def get_signal(self):
        """
        Generates the trading signal based on the RSI indicator.
        Returns:
            int: The trading signal (-1 for sell, 0 for hold, 1 for buy).
        """
        candles_df = self.get_processed_df()
        rsi_value = candles_df.iat[-1, -1]
        if rsi_value > self.config.rsi_low:
            return -1
        elif rsi_value < self.config.rsi_high:
            return 1
        else:
            return 0

    def get_processed_df(self):
        """
        Retrieves the processed dataframe with RSI values.
        Returns:
            pd.DataFrame: The processed dataframe with RSI values.
        """
        candles_df = self.candles[0].candles_df
        candles_df.ta.rsi(length=7, append=True)
        return candles_df

    def market_data_extra_info(self):
        """
        Provides additional information about the market data to the format status.
        Returns:
            List[str]: A list of formatted strings containing market data information.
        """
        lines = []
        columns_to_show = ["timestamp", "open", "low", "high", "close", "volume", "RSI_7"]
        candles_df = self.get_processed_df()
        lines.extend([f"Candles: {self.candles[0].name} | Interval: {self.candles[0].interval}\n"])
        lines.extend(self.candles_formatted_list(candles_df, columns_to_show))
        return lines
