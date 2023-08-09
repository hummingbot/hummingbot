from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.meta_strategies.data_types import OrderLevel, TripleBarrierConf
from hummingbot.smart_components.meta_strategies.market_making.market_making_executor import MarketMakingExecutor
from hummingbot.smart_components.meta_strategies.market_making.strategies.dman_v1 import DMan, DManConfig
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MarketMakingDman(ScriptStrategyBase):
    triple_barrier_conf = TripleBarrierConf(
        stop_loss=Decimal("0.02"), take_profit=Decimal("0.02"),
        time_limit=60 * 60 * 24,
        trailing_stop_activation_price_delta=Decimal("0.08"),
        trailing_stop_trailing_delta=Decimal("0.02")
    )

    config = DManConfig(
        exchange="binance_perpetual",
        trading_pair="BTC-USDT",
        order_refresh_time=60,
        cooldown_time=15,
        order_levels=[
            OrderLevel(level=0, side=TradeType.BUY, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(1), triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=0, side=TradeType.SELL, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(1), triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=1, side=TradeType.SELL, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(1.5), triple_barrier_conf=triple_barrier_conf),
        ],
        candles_config=[
            CandlesConfig(connector="binance_perpetual", trading_pair="BTC-USDT", interval="3m", max_records=1000),
        ],
        leverage=20
    )
    meta_strategy = DMan(config=config)
    empty_markets = {}
    markets = meta_strategy.update_strategy_markets_dict(empty_markets)

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.mm_executor = MarketMakingExecutor(strategy=self, meta_strategy=self.meta_strategy)
        self.mm_executor.start()

    def on_stop(self):
        self.mm_executor.terminate_control_loop()

    def on_tick(self):
        pass

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        return self.mm_executor.to_format_status()
