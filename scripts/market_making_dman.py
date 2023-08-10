from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.meta_strategies.data_types import MetaExecutorStatus, OrderLevel, TripleBarrierConf
from hummingbot.smart_components.meta_strategies.market_making.market_making_executor import MarketMakingExecutor
from hummingbot.smart_components.meta_strategies.market_making.strategies.dman_v1 import DManV1, DManV1Config
from hummingbot.smart_components.meta_strategies.market_making.strategies.dman_v2 import DManV2, DManV2Config
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MarketMakingDman(ScriptStrategyBase):
    triple_barrier_conf = TripleBarrierConf(
        stop_loss=Decimal("0.02"), take_profit=Decimal("0.02"),
        time_limit=60 * 60 * 24,
        trailing_stop_activation_price_delta=Decimal("0.08"),
        trailing_stop_trailing_delta=Decimal("0.02")
    )

    config_v1 = DManV1Config(
        exchange="binance_perpetual",
        trading_pair="LPT-USDT",
        order_refresh_time=60 * 5,
        cooldown_time=15,
        order_levels=[
            OrderLevel(level=0, side=TradeType.BUY, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(1.0), triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=1, side=TradeType.BUY, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(2.0), triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=0, side=TradeType.SELL, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(1.0), triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=1, side=TradeType.SELL, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(2.0), triple_barrier_conf=triple_barrier_conf),
        ],
        candles_config=[
            CandlesConfig(connector="binance_perpetual", trading_pair="LPT-USDT", interval="3m", max_records=1000),
        ],
        leverage=10,
        natr_length=21
    )
    config_v2 = DManV2Config(
        exchange="binance_perpetual",
        trading_pair="LPT-USDT",
        order_refresh_time=60 * 5,
        cooldown_time=15,
        order_levels=[
            OrderLevel(level=0, side=TradeType.BUY, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(1.0), triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=1, side=TradeType.BUY, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(2.0), triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=0, side=TradeType.SELL, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(1.0), triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=1, side=TradeType.SELL, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(2.0), triple_barrier_conf=triple_barrier_conf),
        ],
        candles_config=[
            CandlesConfig(connector="binance_perpetual", trading_pair="LPT-USDT", interval="3m", max_records=1000),
        ],
        leverage=10,
        natr_length=21, macd_fast=12, macd_slow=26, macd_signal=9
    )
    dman_v1 = DManV1(config=config_v1)
    dman_v2 = DManV2(config=config_v2)

    empty_markets = {}
    markets = dman_v1.update_strategy_markets_dict(empty_markets)

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.dman_v1_executor = MarketMakingExecutor(strategy=self, meta_strategy=self.dman_v1)
        self.dman_v2_executor = MarketMakingExecutor(strategy=self, meta_strategy=self.dman_v2)

    def on_stop(self):
        self.dman_v1_executor.terminate_control_loop()
        self.dman_v2_executor.terminate_control_loop()

    def on_tick(self):
        """
        This shows you how you can start meta strategies. You can run more than one at the same time and based on the
        market conditions, you can orchestrate from this script when to stop or start them.
        """
        if self.dman_v1_executor.status == MetaExecutorStatus.NOT_STARTED:
            self.dman_v1_executor.start()
        if self.dman_v2_executor.status == MetaExecutorStatus.NOT_STARTED:
            self.dman_v2_executor.start()

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        lines.extend(["DMAN V1", self.dman_v1_executor.to_format_status()])
        lines.extend(["DMAN V2", self.dman_v2_executor.to_format_status()])
        return "\n".join(lines)
