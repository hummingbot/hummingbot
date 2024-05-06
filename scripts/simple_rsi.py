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
    exchange: str = Field("binance_perpetual", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Exchange where the bot will trade"))
    trading_pair: str = Field("ETH-USDT", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Trading pair where the bot will place orders"))
    order_amount_usd: Decimal = Field(40, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Order amount (denominated in quote asset)"))
    leverage: int = Field(10, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Leverage scalar to use"))
    stop_loss: float = Field(0.0075, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Position stop loss level"))
    take_profit: float = Field(0.015, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Position take profit level"))
    time_limit: int = Field(60 * 1, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Position time limit in seconds"))
    trailing_stop_activation_delta: float = Field(0.004, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Position trailing stop activation delta"))
    cooldown_after_execution: int = Field(10, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Cooldown after execution in seconds"))


class SimpleRSI(DirectionalStrategyBase):
    """
    This strategy uses RSI (Relative Strength Index) to generate trading signals and execute trades based on the RSI values.
    It defines the specific parameters and configurations for the RSI strategy.
    """

    @classmethod
    def init_markets(cls, config: SimpleRSIConfig):
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: SimpleRSIConfig):
        super().__init__(connectors)
        self.config = config
        self.directional_strategy_name = self.config.script_file_name
        self.ltrading_pair: str = self.config.trading_pair
        self.order_amount_usd = self.config.order_amount_usd
        self.leverage = self.config.leverage
        self.stop_loss = self.config.stop_loss
        self.take_profit = self.config.take_profit
        self.time_limit = self.config.time_limit
        self.trailing_stop_activation_delta = self.config.trailing_stop_activation_delta
        self.cooldown_after_execution = self.config.cooldown_after_execution
        self.candles = [CandlesFactory.get_candle(CandlesConfig(
            connector=self.config.exchange, trading_pair=self.config.trading_pair, interval="3m", max_records=1000))]

    def get_signal(self):
        """
        Generates the trading signal based on the RSI indicator.
        Returns:
            int: The trading signal (-1 for sell, 0 for hold, 1 for buy).
        """
        candles_df = self.get_processed_df()
        rsi_value = candles_df.iat[-1, -1]
        if rsi_value > 70:
            return -1
        elif rsi_value < 30:
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
