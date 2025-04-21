from decimal import Decimal
from typing import Dict, Set

from hummingbot.core.data_type.common import PositionMode, PriceType, TradeType
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class BasicOrderExampleConfig(ControllerConfigBase):
    controller_name: str = "basic_order_example"
    controller_type: str = "generic"
    connector_name: str = "binance_perpetual"
    trading_pair: str = "WLD-USDT"
    side: TradeType = TradeType.BUY
    position_mode: PositionMode = PositionMode.HEDGE
    leverage: int = 50
    amount_quote: Decimal = Decimal("10")
    order_frequency: int = 10

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        if self.connector_name not in markets:
            markets[self.connector_name] = set()
        markets[self.connector_name].add(self.trading_pair)
        return markets


class BasicOrderExample(ControllerBase):
    def __init__(self, config: BasicOrderExampleConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.last_timestamp = 0

    def determine_executor_actions(self) -> list[ExecutorAction]:
        if (self.processed_data["n_active_executors"] == 0 and
                self.market_data_provider.time() - self.last_timestamp > self.config.order_frequency):
            self.last_timestamp = self.market_data_provider.time()
            config = OrderExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                side=self.config.side,
                amount=self.config.amount_quote / self.processed_data["mid_price"],
                execution_strategy=ExecutionStrategy.MARKET,
                price=self.processed_data["mid_price"],
            )
            return [CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=config)]
        return []

    async def update_processed_data(self):
        mid_price = self.market_data_provider.get_price_by_type(self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        n_active_executors = len([executor for executor in self.executors_info if executor.is_active])
        self.processed_data = {"mid_price": mid_price, "n_active_executors": n_active_executors}
