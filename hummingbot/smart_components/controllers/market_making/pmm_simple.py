import time
from decimal import Decimal

from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.core.data_type.common import OrderType
from hummingbot.smart_components.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.smart_components.executors.position_executor.data_types import (
    PositionExecutorConfig,
    TripleBarrierConfig,
)


class PMMSimpleConfig(MarketMakingControllerConfigBase):
    # Triple Barrier Configuration
    stop_loss: Decimal = Field(
        default=Decimal("0.03"), gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the stop loss (as a decimal, e.g., 0.03 for 3%): ",
            prompt_on_new=True))
    take_profit: Decimal = Field(
        default=Decimal("0.01"), gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the take profit (as a decimal, e.g., 0.01 for 1%): ",
            prompt_on_new=True))
    time_limit: int = Field(
        default=60 * 45, gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the time limit in seconds (e.g., 2700 for 45 minutes): ",
            prompt_on_new=True))
    take_profit_order_type: OrderType = Field(
        default="LIMIT",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the order type for taking profit (LIMIT/MARKET): ",
            prompt_on_new=True))

    @property
    def triple_barrier_config(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            time_limit=self.time_limit,
            open_order_type=OrderType.LIMIT,
            take_profit_order_type=self.take_profit_order_type,
            stop_loss_order_type=OrderType.MARKET,  # Defaulting to MARKET as per requirement
            time_limit_order_type=OrderType.MARKET  # Defaulting to MARKET as per requirement
        )


class PMMSimpleController(MarketMakingControllerBase):
    def __init__(self, config: PMMSimpleConfig):
        super().__init__(config)
        self.config = config

    def get_executor_config(self, level_id: str, price: Decimal, amount_in_quote: Decimal):
        amount = amount_in_quote / price
        trade_type = self.get_trade_type_from_level_id(level_id)
        return PositionExecutorConfig(
            timestamp=time.time(),
            level_id=level_id,
            exchange=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            entry_price=price,
            amount=amount,
            triple_barrier_config=self.config.triple_barrier_config,
            leverage=self.config.leverage,
            side=trade_type
        )
