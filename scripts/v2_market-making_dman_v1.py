from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase, TradeType
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.dman_v1 import DManV1, DManV1Config
from hummingbot.smart_components.strategy_frameworks.data_types import (
    ExecutorHandlerStatus,
    OrderLevel,
    TripleBarrierConf,
)
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_executor_handler import (
    MarketMakingExecutorHandler,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MarketMakingDmanV1(ScriptStrategyBase):
    trading_pair = "HBAR-USDT"
    triple_barrier_conf = TripleBarrierConf(
        stop_loss=Decimal("0.03"), take_profit=Decimal("0.02"),
        time_limit=60 * 60 * 24,
        trailing_stop_activation_price_delta=Decimal("0.002"),
        trailing_stop_trailing_delta=Decimal("0.0005")
    )

    config_v1 = DManV1Config(
        exchange="binance_perpetual",
        trading_pair=trading_pair,
        order_levels=[
            OrderLevel(level=0, side=TradeType.BUY, order_amount_usd=Decimal(20),
                       spread_factor=Decimal(1.0), order_refresh_time=60 * 5,
                       cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=1, side=TradeType.BUY, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(2.5), order_refresh_time=60 * 5,
                       cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=0, side=TradeType.SELL, order_amount_usd=Decimal(20),
                       spread_factor=Decimal(1.0), order_refresh_time=60 * 5,
                       cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=1, side=TradeType.SELL, order_amount_usd=Decimal(50),
                       spread_factor=Decimal(2.5), order_refresh_time=60 * 5,
                       cooldown_time=15, triple_barrier_conf=triple_barrier_conf),
        ],
        candles_config=[
            CandlesConfig(connector="binance_perpetual", trading_pair=trading_pair, interval="3m", max_records=1000),
        ],
        leverage=10,
        natr_length=21
    )

    dman_v1 = DManV1(config=config_v1)

    empty_markets = {}
    markets = dman_v1.update_strategy_markets_dict(empty_markets)

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.dman_v1_executor = MarketMakingExecutorHandler(strategy=self, controller=self.dman_v1)

    def on_stop(self):
        self.close_open_positions()

    def on_tick(self):
        """
        This shows you how you can start meta controllers. You can run more than one at the same time and based on the
        market conditions, you can orchestrate from this script when to stop or start them.
        """
        if self.dman_v1_executor.status == ExecutorHandlerStatus.NOT_STARTED:
            self.dman_v1_executor.start()

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        lines.extend(["DMAN V1", self.dman_v1_executor.to_format_status()])
        lines.extend(["\n-----------------------------------------\n"])
        return "\n".join(lines)

    def close_open_positions(self):
        # we are going to close all the open positions when the bot stops
        for connector_name, connector in self.connectors.items():
            for trading_pair, position in connector.account_positions.items():
                if trading_pair in self.markets[connector_name]:
                    if position.position_side == PositionSide.LONG:
                        self.sell(connector_name=connector_name,
                                  trading_pair=position.trading_pair,
                                  amount=abs(position.amount),
                                  order_type=OrderType.MARKET,
                                  price=connector.get_mid_price(position.trading_pair),
                                  position_action=PositionAction.CLOSE)
                    elif position.position_side == PositionSide.SHORT:
                        self.buy(connector_name=connector_name,
                                 trading_pair=position.trading_pair,
                                 amount=abs(position.amount),
                                 order_type=OrderType.MARKET,
                                 price=connector.get_mid_price(position.trading_pair),
                                 position_action=PositionAction.CLOSE)
