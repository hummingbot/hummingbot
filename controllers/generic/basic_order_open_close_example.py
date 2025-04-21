from decimal import Decimal
from typing import Dict, Set

from hummingbot.core.data_type.common import PositionAction, PositionMode, PriceType, TradeType
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class BasicOrderOpenCloseExampleConfig(ControllerConfigBase):
    controller_name: str = "basic_order_open_close_example"
    controller_type: str = "generic"
    connector_name: str = "binance_perpetual"
    trading_pair: str = "WLD-USDT"
    side: TradeType = TradeType.BUY
    position_mode: PositionMode = PositionMode.HEDGE
    leverage: int = 50
    close_order_delay: int = 10
    open_short_to_close_long: bool = False
    close_partial_position: bool = False
    amount_quote: Decimal = Decimal("20")

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        if self.connector_name not in markets:
            markets[self.connector_name] = set()
        markets[self.connector_name].add(self.trading_pair)
        return markets


class BasicOrderOpenClose(ControllerBase):
    def __init__(self, config: BasicOrderOpenCloseExampleConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.open_order_placed = False
        self.closed_order_placed = False
        self.last_timestamp = 0
        self.open_side = self.config.side
        self.close_side = TradeType.SELL if self.config.side == TradeType.BUY else TradeType.BUY

    def get_position(self, connector_name, trading_pair):
        for position in self.positions_held:
            if position.connector_name == connector_name and position.trading_pair == trading_pair:
                return position

    def determine_executor_actions(self) -> list[ExecutorAction]:
        mid_price = self.market_data_provider.get_price_by_type(self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        if not self.open_order_placed:
            config = OrderExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                side=self.config.side,
                amount=self.config.amount_quote / mid_price,
                execution_strategy=ExecutionStrategy.MARKET,
                position_action=PositionAction.OPEN,
                price=mid_price,
            )
            self.open_order_placed = True
            self.last_timestamp = self.market_data_provider.time()
            return [CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=config)]
        else:
            if self.market_data_provider.time() - self.last_timestamp > self.config.close_order_delay and not self.closed_order_placed:
                current_position = self.get_position(self.config.connector_name, self.config.trading_pair)
                if current_position is None:
                    self.logger().info("The original position is not found, can close the position")
                else:
                    amount = current_position.amount / 2 if self.config.close_partial_position else current_position.amount
                    config = OrderExecutorConfig(
                        timestamp=self.market_data_provider.time(),
                        connector_name=self.config.connector_name,
                        trading_pair=self.config.trading_pair,
                        side=self.close_side,
                        amount=amount,
                        execution_strategy=ExecutionStrategy.MARKET,
                        position_action=PositionAction.OPEN if self.config.open_short_to_close_long else PositionAction.CLOSE,
                        price=mid_price,
                    )
                    self.closed_order_placed = True
                    return [CreateExecutorAction(
                        controller_id=self.config.id,
                        executor_config=config)]
        return []

    async def update_processed_data(self):
        pass
