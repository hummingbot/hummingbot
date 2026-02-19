from decimal import Decimal
from typing import List

from hummingbot.core.data_type.common import MarketDict, PositionMode, PriceType, TradeType
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class BuyThreeTimesExampleConfig(ControllerConfigBase):
    controller_name: str = "examples.buy_three_times_example"
    connector_name: str = "binance_perpetual"
    trading_pair: str = "WLD-USDT"
    position_mode: PositionMode = PositionMode.HEDGE
    leverage: int = 20
    amount_quote: Decimal = Decimal("10")
    order_frequency: int = 10

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class BuyThreeTimesExample(ControllerBase):
    def __init__(self, config: BuyThreeTimesExampleConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.last_timestamp = 0
        self.buy_count = 0
        self.max_buys = 3

    async def update_processed_data(self):
        mid_price = self.market_data_provider.get_price_by_type(self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        n_active_executors = len([executor for executor in self.executors_info if executor.is_active])
        self.processed_data = {
            "mid_price": mid_price,
            "n_active_executors": n_active_executors,
            "buy_count": self.buy_count,
            "max_buys_reached": self.buy_count >= self.max_buys
        }

    def determine_executor_actions(self) -> list[ExecutorAction]:
        if (self.buy_count < self.max_buys and
                self.processed_data["n_active_executors"] == 0 and
                self.market_data_provider.time() - self.last_timestamp > self.config.order_frequency):

            self.last_timestamp = self.market_data_provider.time()
            self.buy_count += 1

            config = OrderExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                side=TradeType.BUY,
                amount=self.config.amount_quote / self.processed_data["mid_price"],
                execution_strategy=ExecutionStrategy.MARKET,
                price=self.processed_data["mid_price"],
            )
            return [CreateExecutorAction(controller_id=self.config.id, executor_config=config)]
        return []

    def to_format_status(self) -> List[str]:
        lines = []
        lines.append("Buy Three Times Example Status:")
        lines.append(f"  Buys completed: {self.buy_count}/{self.max_buys}")
        lines.append(f"  Max buys reached: {self.buy_count >= self.max_buys}")
        if hasattr(self, 'processed_data') and self.processed_data:
            lines.append(f"  Mid price: {self.processed_data.get('mid_price', 'N/A')}")
            lines.append(f"  Active executors: {self.processed_data.get('n_active_executors', 'N/A')}")
        return lines
