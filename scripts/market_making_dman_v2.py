from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.meta_strategies.data_types import MetaExecutorStatus, OrderLevel, TripleBarrierConf
from hummingbot.smart_components.meta_strategies.market_making.market_making_executor import MarketMakingExecutor
from hummingbot.smart_components.meta_strategies.market_making.strategies.dman_v2 import DManV2, DManV2Config
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MarketMakingDman(ScriptStrategyBase):
    triple_barrier_conf = TripleBarrierConf(
        stop_loss=Decimal("0.03"), take_profit=Decimal("0.02"),
        time_limit=60 * 60 * 24,
        trailing_stop_activation_price_delta=Decimal("0.002"),
        trailing_stop_trailing_delta=Decimal("0.0005")
    )
    config_v2 = DManV2Config(
        exchange="binance_perpetual",
        trading_pair="ETH-USDT",
        order_levels=[
            OrderLevel(level=0, side=TradeType.BUY, order_amount_usd=Decimal(15),
                       spread_factor=Decimal(0.5), order_refresh_time=60 * 5,
                       cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=1, side=TradeType.BUY, order_amount_usd=Decimal(30),
                       spread_factor=Decimal(1.0), order_refresh_time=60 * 5,
                       cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=2, side=TradeType.BUY, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(2.0), order_refresh_time=60 * 5,
                       cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=0, side=TradeType.SELL, order_amount_usd=Decimal(15),
                       spread_factor=Decimal(0.5), order_refresh_time=60 * 5,
                       cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=1, side=TradeType.SELL, order_amount_usd=Decimal(30),
                       spread_factor=Decimal(1.0), order_refresh_time=60 * 5,
                       cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=2, side=TradeType.SELL, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(2.0), order_refresh_time=60 * 5,
                       cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
        ],
        candles_config=[
            CandlesConfig(connector="binance_perpetual", trading_pair="ETH-USDT", interval="3m", max_records=1000),
        ],
        leverage=10,
        natr_length=21, macd_fast=12, macd_slow=26, macd_signal=9
    )
    dman_v2 = DManV2(config=config_v2)

    empty_markets = {}
    markets = dman_v2.update_strategy_markets_dict(empty_markets)

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.dman_v2_executor = MarketMakingExecutor(strategy=self, meta_strategy=self.dman_v2)

    def on_stop(self):
        self.dman_v2_executor.terminate_control_loop()

    def on_tick(self):
        """
        This shows you how you can start meta strategies. You can run more than one at the same time and based on the
        market conditions, you can orchestrate from this script when to stop or start them.
        """
        if self.dman_v2_executor.status == MetaExecutorStatus.NOT_STARTED:
            self.dman_v2_executor.start()

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        lines.extend(["DMAN V2", self.dman_v2_executor.to_format_status()])
        lines.extend(["\n-----------------------------------------\n"])
        return "\n".join(lines)
