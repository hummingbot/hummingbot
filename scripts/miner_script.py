from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase, TradeType
from hummingbot.core.data_type.common import OrderType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.dman_v3 import DManV3, DManV3Config
from hummingbot.smart_components.strategy_frameworks.data_types import (
    ExecutorHandlerStatus,
    OrderLevel,
    TripleBarrierConf,
)
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_executor_handler import (
    MarketMakingExecutorHandler,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MinerScriptV1(ScriptStrategyBase):
    trading_pairs = ["RLC-USDT"]
    exchange = "binance"

    leverage_by_trading_pair = {
        "HBAR-USDT": 25,
        "CYBER-USDT": 20,
        "ETH-USDT": 100,
        "LPT-USDT": 10,
        "UNFI-USDT": 20,
        "BAKE-USDT": 20,
        "YGG-USDT": 20,
        "SUI-USDT": 50,
        "TOMO-USDT": 25,
        "RUNE-USDT": 25,
        "STX-USDT": 25,
        "API3-USDT": 20,
        "LIT-USDT": 20,
        "PERP-USDT": 16,
        "HOOK-USDT": 20,
        "AMB-USDT": 20,
        "ARKM-USDT": 20,
        "TRB-USDT": 10,
    }

    triple_barrier_conf = TripleBarrierConf(
        stop_loss=Decimal("0.15"), take_profit=Decimal("0.005"),
        time_limit=60 * 60 * 12,
        take_profit_order_type=OrderType.LIMIT
    )

    order_levels = [
        OrderLevel(level=0, side=TradeType.BUY, order_amount_usd=Decimal("20"),
                   spread_factor=Decimal(0.5), order_refresh_time=60 * 30,
                   cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
        OrderLevel(level=1, side=TradeType.BUY, order_amount_usd=Decimal("20"),
                   spread_factor=Decimal(2.0), order_refresh_time=60 * 30,
                   cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
        OrderLevel(level=2, side=TradeType.BUY, order_amount_usd=Decimal("20"),
                   spread_factor=Decimal(3.5), order_refresh_time=60 * 30,
                   cooldown_time=15, triple_barrier_conf=triple_barrier_conf),

        OrderLevel(level=0, side=TradeType.SELL, order_amount_usd=Decimal("20"),
                   spread_factor=Decimal(0.5), order_refresh_time=60 * 30,
                   cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
        OrderLevel(level=1, side=TradeType.SELL, order_amount_usd=Decimal("20"),
                   spread_factor=Decimal(1.0), order_refresh_time=60 * 30,
                   cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
        OrderLevel(level=2, side=TradeType.SELL, order_amount_usd=Decimal("20"),
                   spread_factor=Decimal(2.5), order_refresh_time=60 * 30,
                   cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
    ]
    controllers = {}
    markets = {}
    executor_handlers = {}

    for trading_pair in trading_pairs:
        config = DManV3Config(
            exchange=exchange,
            trading_pair=trading_pair,
            order_levels=order_levels,
            candles_config=[
                CandlesConfig(connector=exchange, trading_pair=trading_pair, interval="1h", max_records=300),
            ],
            bb_length=200,
        )
        controller = DManV3(config=config)
        markets = controller.update_strategy_markets_dict(markets)
        controllers[trading_pair] = controller

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        for trading_pair, controller in self.controllers.items():
            self.executor_handlers[trading_pair] = MarketMakingExecutorHandler(strategy=self, controller=controller)

    def on_stop(self):
        for executor_handler in self.executor_handlers.values():
            executor_handler.stop()

    def on_tick(self):
        """
        This shows you how you can start meta controllers. You can run more than one at the same time and based on the
        market conditions, you can orchestrate from this script when to stop or start them.
        """
        for executor_handler in self.executor_handlers.values():
            if executor_handler.status == ExecutorHandlerStatus.NOT_STARTED:
                executor_handler.start()

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        for trading_pair, executor_handler in self.executor_handlers.items():
            lines.extend(
                [f"Strategy: {executor_handler.controller.config.strategy_name} | Trading Pair: {trading_pair}",
                 executor_handler.to_format_status()])
        return "\n".join(lines)
