import os
from decimal import Decimal
from typing import Dict, List, Optional

import pandas_ta as ta  # noqa: F401
from pydantic import Field, field_validator

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionMode, PriceType, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction


class MACDBBRSIConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    markets: Dict[str, List[str]] = {}
    candles_config: List[CandlesConfig] = []
    controllers_config: List[str] = []
    exchange: str = Field(default="hyperliquid_perpetual")
    trading_pair: str = Field(default="ETH-USD")
    candles_exchange: str = Field(default="binance_perpetual")
    candles_pair: str = Field(default="ETH-USDT")
    candles_interval: str = Field(default="5m")
    candles_length: int = Field(default=60, gt=0)

    # RSI Configuration
    rsi_low: float = Field(default=20, gt=0)
    rsi_high: float = Field(default=80, gt=0)
    rsi_length: int = Field(default=14, gt=0)

    # MACD Configuration
    macd_fast: int = Field(default=6, gt=0)
    macd_slow: int = Field(default=13, gt=0)
    macd_signal: int = Field(default=4, gt=0)

    # Bollinger Bands Configuration
    bb_length: int = Field(default=100, gt=0)
    bb_std: float = Field(default=2.5, gt=0)

    # Bollinger Bands Threshold Configuration
    bb_long_threshold: float = Field(default=0.0)
    bb_short_threshold: float = Field(default=1.0)

    # Order Configuration
    order_amount_quote: Decimal = Field(default=30, gt=0)
    leverage: int = Field(default=10, gt=0)
    position_mode: PositionMode = Field(default="ONEWAY")

    # Triple Barrier Configuration
    stop_loss: Decimal = Field(default=Decimal("0.03"), gt=0)
    take_profit: Decimal = Field(default=Decimal("0.01"), gt=0)
    time_limit: int = Field(default=60 * 15, gt=0)

    @property
    def triple_barrier_config(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            time_limit=self.time_limit,
            open_order_type=OrderType.MARKET,
            take_profit_order_type=OrderType.LIMIT,
            stop_loss_order_type=OrderType.MARKET,
            time_limit_order_type=OrderType.MARKET
        )

    @field_validator('position_mode', mode="before")
    @classmethod
    def validate_position_mode(cls, v: str) -> PositionMode:
        if v.upper() in PositionMode.__members__:
            return PositionMode[v.upper()]
        raise ValueError(f"Invalid position mode: {v}. Valid options are: {', '.join(PositionMode.__members__)}")


class MACDBBRSIStrategy(StrategyV2Base):
    """
    This strategy uses a combination of RSI, MACD, and Bollinger Bands to generate trading signals.
    It combines multiple technical indicators for more robust signal generation.
    """

    account_config_set = False

    @classmethod
    def init_markets(cls, config: MACDBBRSIConfig):
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: MACDBBRSIConfig):
        self.max_records = max(config.macd_slow, config.macd_fast, config.macd_signal, config.bb_length, config.candles_length) + 20
        if len(config.candles_config) == 0:
            config.candles_config.append(CandlesConfig(
                connector=config.candles_exchange,
                trading_pair=config.candles_pair,
                interval=config.candles_interval,
                max_records=self.max_records
            ))
        super().__init__(connectors, config)
        self.config = config
        self.current_rsi = None
        self.current_macd = None
        self.current_macd_histogram = None
        self.current_bbp = None
        self.current_signal = None

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
                                                           self.max_records)

        # Calculate indicators
        candles.ta.rsi(length=self.config.rsi_length, append=True)
        candles.ta.bbands(length=self.config.bb_length, std=self.config.bb_std, append=True)
        candles.ta.macd(fast=self.config.macd_fast, slow=self.config.macd_slow, signal=self.config.macd_signal, append=True)

        # Get current indicator values
        self.current_rsi = candles.iloc[-1][f"RSI_{self.config.rsi_length}"]
        self.current_bbp = candles.iloc[-1][f"BBP_{self.config.bb_length}_{self.config.bb_std}"]
        self.current_macd = candles.iloc[-1][f"MACD_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"]
        self.current_macd_histogram = candles.iloc[-1][f"MACDh_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"]

        # Define combined signal conditions
        rsi_condition = candles[f"RSI_{self.config.rsi_length}"]
        bbp_condition = candles[f"BBP_{self.config.bb_length}_{self.config.bb_std}"]
        macd_condition = candles[f"MACD_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"]
        macdh_condition = candles[f"MACDh_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"]

        # Generate combined signals
        long_condition = (rsi_condition < self.config.rsi_low) & (bbp_condition < self.config.bb_long_threshold) & (macdh_condition > 0) & (macd_condition < 0)
        short_condition = (rsi_condition > self.config.rsi_high) & (bbp_condition > self.config.bb_short_threshold) & (macdh_condition < 0) & (macd_condition > 0)

        candles["signal"] = 0
        candles.loc[long_condition, "signal"] = 1
        candles.loc[short_condition, "signal"] = -1

        self.current_signal = candles.iloc[-1]["signal"] if not candles.empty else None
        return self.current_signal

    def apply_initial_setting(self):
        if not self.account_config_set:
            for connector_name, connector in self.connectors.items():
                if self.is_perpetual(connector_name):
                    connector.set_position_mode(self.config.position_mode)
        if self.is_perpetual(connector_name):
            connector.set_position_mode(self.config.position_mode)
            connector.set_leverage(self.config.trading_pair, self.config.leverage)
            self.account_config_set = True

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        # Create RSI progress bar
        if self.current_rsi is not None:
            bar_length = 50
            rsi_position = int((self.current_rsi / 100) * bar_length)
            progress_bar = ["─"] * bar_length

            # Add threshold markers
            low_threshold_pos = int((self.config.rsi_low / 100) * bar_length)
            high_threshold_pos = int((self.config.rsi_high / 100) * bar_length)
            progress_bar[low_threshold_pos] = "L"
            progress_bar[high_threshold_pos] = "H"

            # Add current position marker
            if 0 <= rsi_position < bar_length:
                progress_bar[rsi_position] = "●"

            progress_bar = "".join(progress_bar)
            lines.extend([
                "",
                f"  RSI: {self.current_rsi:.2f}  (Long ≤ {self.config.rsi_low}, Short ≥ {self.config.rsi_high})",
                f"  0 {progress_bar} 100",
            ])

        # Display MACD and BB values
        if self.current_macd is not None:
            lines.extend([
                "",
                f"  MACD: {self.current_macd:.4f}  |  MACD Histogram: {self.current_macd_histogram:.4f}",
                f"  BBP: {self.current_bbp:.4f}  (Long ≤ {self.config.bb_long_threshold}, Short ≥ {self.config.bb_short_threshold})",
            ])

        try:
            orders_df = self.active_orders_df()
            lines.extend(["", "  Active Orders:"] + ["    " + line for line in orders_df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        return "\n".join(lines)
