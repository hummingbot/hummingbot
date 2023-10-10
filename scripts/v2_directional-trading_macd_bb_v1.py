from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase, TradeType
from hummingbot.core.data_type.common import OrderType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.macd_bb_v1 import MACDBBV1, MACDBBV1Config
from hummingbot.smart_components.strategy_frameworks.data_types import (
    ExecutorHandlerStatus,
    OrderLevel,
    TripleBarrierConf,
)
from hummingbot.smart_components.strategy_frameworks.directional_trading.directional_trading_executor_handler import (
    DirectionalTradingExecutorHandler,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MarketMakingDmanComposed(ScriptStrategyBase):
    trading_pairs = ["HBAR-USDT", "CYBER-USDT", "ETH-USDT", "LPT-USDT", "UNFI-USDT"]
    leverage_by_trading_pair = {
        "HBAR-USDT": 25,
        "CYBER-USDT": 20,
        "ETH-USDT": 100,
        "LPT-USDT": 10,
        "UNFI-USDT": 20,
    }
    triple_barrier_conf = TripleBarrierConf(
        stop_loss=Decimal("0.01"), take_profit=Decimal("0.03"),
        time_limit=60 * 60 * 6,
        trailing_stop_activation_price_delta=Decimal("0.008"),
        trailing_stop_trailing_delta=Decimal("0.004"),
        open_order_type=OrderType.MARKET
    )

    order_levels = [
        OrderLevel(level=0, side=TradeType.BUY, order_amount_usd=Decimal("15"),
                   spread_factor=Decimal(0.5), order_refresh_time=60 * 5,
                   cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
        OrderLevel(level=0, side=TradeType.SELL, order_amount_usd=Decimal("15"),
                   spread_factor=Decimal(0.5), order_refresh_time=60 * 5,
                   cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
    ]
    controllers = {}
    markets = {}
    executor_handlers = {}

    for trading_pair in trading_pairs:
        config = MACDBBV1Config(
            exchange="binance_perpetual",
            trading_pair=trading_pair,
            order_levels=order_levels,
            candles_config=[
                CandlesConfig(connector="binance_perpetual", trading_pair=trading_pair, interval="3m", max_records=100),
            ],
            leverage=leverage_by_trading_pair[trading_pair],
            macd_fast=21, macd_slow=42, macd_signal=9,
            bb_length=100, bb_std=2.0, bb_long_threshold=0.3, bb_short_threshold=0.7,
        )
        controller = MACDBBV1(config=config)
        markets = controller.update_strategy_markets_dict(markets)
        controllers[trading_pair] = controller

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        for trading_pair, controller in self.controllers.items():
            self.executor_handlers[trading_pair] = DirectionalTradingExecutorHandler(strategy=self, controller=controller)

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
            if executor_handler.controller.all_candles_ready:
                lines.extend(
                    [f"Strategy: {executor_handler.controller.config.strategy_name} | Trading Pair: {trading_pair}",
                     executor_handler.to_format_status()])
        return "\n".join(lines)
