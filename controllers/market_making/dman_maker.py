import time
from decimal import Decimal
from typing import List, Optional

import pandas_ta as ta  # noqa: F401
from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.smart_components.executors.dca_executor.data_types import DCAExecutorConfig, DCAMode
from hummingbot.smart_components.order_level_distributions.distributions import Distributions


class DManMakerConfig(MarketMakingControllerConfigBase):
    """
    Configuration required to run the PairsTrading strategy.
    """
    controller_name: str = "dman_maker"
    candles_config: List[CandlesConfig] = []

    # DCA configuration
    dca_amount_ratio_increase: float = Field(
        default=2.0, gt=1.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the ratio of amount increase between DCA levels: ",
            prompt_on_new=True))
    dca_levels: int = Field(
        default=5, gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the number of DCA levels: ",
            prompt_on_new=True))
    top_order_start_spread: float = Field(
        default=0.001, gt=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the spread for the top order: ",
            prompt_on_new=True))
    start_spread: float = Field(
        default=0.03, gt=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the spread for the second order: ",
            prompt_on_new=True))
    spread_ratio_increase: float = Field(
        default=1.5, gt=1.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the ratio of spread increase between DCA levels: ",
            prompt_on_new=True))
    time_limit: int = Field(
        default=60 * 60 * 24 * 7, gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the time limit for each DCA level: ",
            prompt_on_new=False))
    stop_loss: Decimal = Field(
        default=Decimal("0.03"), gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the stop loss (as a decimal, e.g., 0.03 for 3%): ",
            prompt_on_new=True))

    activation_bounds: Optional[List[Decimal]] = Field(
        default=None,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the activation bounds for the orders "
                              "(e.g., 0.01 activates the next order when the price is closer than 1%): ",
            prompt_on_new=False))

    @validator("activation_bounds", pre=True, always=True)
    def parse_activation_bounds(cls, v):
        if isinstance(v, list):
            return [Decimal(val) for val in v]
        elif isinstance(v, str):
            if v == "":
                return None
            return [Decimal(val) for val in v.split(",")]
        return v


class DManMaker(MarketMakingControllerBase):
    def __init__(self, config: DManMakerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        amounts_distributed = Distributions.geometric(n_levels=self.config.dca_levels, start=1.0,
                                                      ratio=self.config.dca_amount_ratio_increase)
        self.dca_amounts_pct = [Decimal(amount) / sum(amounts_distributed) for amount in amounts_distributed]
        self.spreads = [Decimal(self.config.top_order_start_spread)] + Distributions.geometric(
            n_levels=self.config.dca_levels - 1, start=self.config.start_spread,
            ratio=self.config.spread_ratio_increase)

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        trade_type = self.get_trade_type_from_level_id(level_id)
        if trade_type == TradeType.BUY:
            prices = [price * (1 - spread) for spread in self.spreads]
        else:
            prices = [price * (1 + spread) for spread in self.spreads]
        amounts = [amount * pct for pct in self.dca_amounts_pct]
        amounts_quote = [amount * price for amount, price in zip(amounts, prices)]
        return DCAExecutorConfig(
            timestamp=time.time(),
            exchange=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            mode=DCAMode.MAKER,
            side=trade_type,
            prices=prices,
            amounts_quote=amounts_quote,
            level_id=level_id,
            time_limit=self.config.time_limit,
            stop_loss=self.config.stop_loss,
            trailing_stop=self.config.trailing_stop,
            activation_bounds=self.config.activation_bounds,
            leverage=self.config.leverage,
        )
