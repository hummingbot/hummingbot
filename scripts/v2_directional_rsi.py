import os
from decimal import Decimal
from typing import Dict, List, Optional

import pandas_ta as ta  # noqa: F401
from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionMode, PriceType, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction


class SimpleDirectionalRSIConfig(StrategyV2ConfigBase):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    markets: Dict[str, List[str]] = {}
    candles_config: List[CandlesConfig] = []
    controllers_config: List[str] = []
    exchange: str = Field(default="hyperliquid_perpetual", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Exchange where the bot will trade"))
    trading_pair: str = Field(default="ETH-USD", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Trading pair where the bot will trade"))
    candles_exchange: str = Field(default="binance_perpetual", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Candles exchange used to calculate RSI"))
    candles_pair: str = Field(default="ETH-USDT", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Candles trading pair used to calculate RSI"))
    candles_interval: str = Field(default="1m", client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Candle interval (e.g. 1m for 1 minute)"))
    candles_length: int = Field(default=60, gt=0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Number of candles used to calculate RSI (e.g. 60)"))
    rsi_low: float = Field(default=30, gt=0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "RSI lower bound to enter long position (e.g. 30)"))
    rsi_high: float = Field(default=70, gt=0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "RSI upper bound to enter short position (e.g. 70)"))
    order_amount_quote: Decimal = Field(default=30, gt=0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Order amount in quote asset"))
    leverage: int = Field(default=10, gt=0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Leverage (e.g. 10 for 10x)"))
    position_mode: PositionMode = Field(default="ONEWAY", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Position mode (HEDGE/ONEWAY)"))

    # Triple Barrier Configuration
    stop_loss: Decimal = Field(default=Decimal("0.03"), gt=0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Position stop loss (e.g. 0.03 for 3%)"))
    take_profit: Decimal = Field(default=Decimal("0.01"), gt=0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Position take profit (e.g. 0.01 for 1%)"))
    time_limit: int = Field(default=60 * 45, gt=0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Position time limit in seconds (e.g. 300 for 5 minutes)"))

    @property
    def triple_barrier_config(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            time_limit=self.time_limit,
            open_order_type=OrderType.MARKET,
            take_profit_order_type=OrderType.LIMIT,
            stop_loss_order_type=OrderType.MARKET,  # Defaulting to MARKET as per requirement
            time_limit_order_type=OrderType.MARKET  # Defaulting to MARKET as per requirement
        )

    @validator('position_mode', pre=True, allow_reuse=True)
    def validate_position_mode(cls, v: str) -> PositionMode:
        if v.upper() in PositionMode.__members__:
            return PositionMode[v.upper()]
        raise ValueError(f"Invalid position mode: {v}. Valid options are: {', '.join(PositionMode.__members__)}")


class SimpleDirectionalRSI(StrategyV2Base):
    """
    This strategy uses RSI (Relative Strength Index) to generate trading signals and execute trades based on the RSI values.
    It defines the specific parameters and configurations for the RSI strategy.
    """

    account_config_set = False

    @classmethod
    def init_markets(cls, config: SimpleDirectionalRSIConfig):
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: SimpleDirectionalRSIConfig):
        if len(config.candles_config) == 0:
            config.candles_config.append(CandlesConfig(
                connector=config.candles_exchange,
                trading_pair=config.candles_pair,
                interval=config.candles_interval,
                max_records=config.candles_length + 10
            ))
        super().__init__(connectors, config)
        self.config = config

    def start(self, clock: Clock, timestamp: float) -> None:
        """
        Start the strategy.
        :param clock: Clock to use.
        :param timestamp: Current time.
        """
        self._last_timestamp = timestamp
        self.apply_initial_setting()

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        create_actions = []
        signal = self.get_signal(self.config.candles_exchange, self.config.candles_pair)
        active_longs, active_shorts = self.get_active_executors_by_side(self.config.exchange,
                                                                        self.config.trading_pair)
        if signal is not None:
            mid_price = self.market_data_provider.get_price_by_type(self.config.exchange,
                                                                    self.config.trading_pair,
                                                                    PriceType.MidPrice)
            if signal == 1 and len(active_longs) == 0:
                create_actions.append(CreateExecutorAction(
                    executor_config=PositionExecutorConfig(
                        timestamp=self.current_timestamp,
                        connector_name=self.config.exchange,
                        trading_pair=self.config.trading_pair,
                        side=TradeType.BUY,
                        entry_price=mid_price,
                        amount=self.config.order_amount_quote / mid_price,
                        triple_barrier_config=self.config.triple_barrier_config,
                        leverage=self.config.leverage
                    )))
            elif signal == -1 and len(active_shorts) == 0:
                create_actions.append(CreateExecutorAction(
                    executor_config=PositionExecutorConfig(
                        timestamp=self.current_timestamp,
                        connector_name=self.config.exchange,
                        trading_pair=self.config.trading_pair,
                        side=TradeType.SELL,
                        entry_price=mid_price,
                        amount=self.config.order_amount_quote / mid_price,
                        triple_barrier_config=self.config.triple_barrier_config,
                        leverage=self.config.leverage
                    )))
        return create_actions

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        stop_actions = []
        signal = self.get_signal(self.config.candles_exchange, self.config.candles_pair)
        active_longs, active_shorts = self.get_active_executors_by_side(self.config.exchange,
                                                                        self.config.trading_pair)
        if signal is not None:
            if signal == -1 and len(active_longs) > 0:
                stop_actions.extend([StopExecutorAction(executor_id=e.id) for e in active_longs])
            elif signal == 1 and len(active_shorts) > 0:
                stop_actions.extend([StopExecutorAction(executor_id=e.id) for e in active_shorts])
        return stop_actions

    def get_active_executors_by_side(self, connector_name: str, trading_pair: str):
        active_executors_by_connector_pair = self.filter_executors(
            executors=self.get_all_executors(),
            filter_func=lambda e: e.connector_name == connector_name and e.trading_pair == trading_pair and e.is_active
        )
        active_longs = [e for e in active_executors_by_connector_pair if e.side == TradeType.BUY]
        active_shorts = [e for e in active_executors_by_connector_pair if e.side == TradeType.SELL]
        return active_longs, active_shorts

    def get_signal(self, connector_name: str, trading_pair: str) -> Optional[float]:
        candles = self.market_data_provider.get_candles_df(connector_name,
                                                           trading_pair,
                                                           self.config.candles_interval,
                                                           self.config.candles_length + 10)
        candles.ta.rsi(length=self.config.candles_length, append=True)
        candles["signal"] = 0
        candles.loc[candles[f"RSI_{self.config.candles_length}"] < self.config.rsi_low, "signal"] = 1
        candles.loc[candles[f"RSI_{self.config.candles_length}"] > self.config.rsi_high, "signal"] = -1
        return candles.iloc[-1]["signal"] if not candles.empty else None

    def apply_initial_setting(self):
        if not self.account_config_set:
            for connector_name, connector in self.connectors.items():
                if self.is_perpetual(connector_name):
                    connector.set_position_mode(self.config.position_mode)
                    for trading_pair in self.market_data_provider.get_trading_pairs(connector_name):
                        connector.set_leverage(trading_pair, self.config.leverage)
            self.account_config_set = True
