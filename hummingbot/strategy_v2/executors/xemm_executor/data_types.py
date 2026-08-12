from decimal import Decimal
from typing import Literal

from pydantic import model_validator

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.data_types import ConnectorPair, ExecutorConfigBase
from hummingbot.strategy_v2.executors.validation import (
    require_directional_side,
    require_interchangeable_pairs,
    require_not_above,
    require_positive,
)


class XEMMExecutorConfig(ExecutorConfigBase):
    type: Literal["xemm_executor"] = "xemm_executor"
    buying_market: ConnectorPair
    selling_market: ConnectorPair
    maker_side: TradeType
    order_amount: Decimal
    min_profitability: Decimal
    target_profitability: Decimal
    max_profitability: Decimal

    @model_validator(mode="after")
    def validate_xemm(self):
        require_directional_side(self.maker_side, "maker_side")
        require_positive("order_amount", self.order_amount)
        # The maker order is repriced towards target_profitability whenever the trade
        # profitability leaves the [min, max] band, so the target has to sit inside it.
        require_not_above("min_profitability", self.min_profitability,
                          "target_profitability", self.target_profitability)
        require_not_above("target_profitability", self.target_profitability,
                          "max_profitability", self.max_profitability)
        if self.min_profitability == self.max_profitability:
            raise ValueError(f"min_profitability ({self.min_profitability}) and max_profitability "
                             f"({self.max_profitability}) must define a non empty band")
        if self.buying_market == self.selling_market:
            raise ValueError(f"buying_market and selling_market must be different markets, both are "
                             f"{self.buying_market.connector_name} {self.buying_market.trading_pair}")
        # The maker order on one venue is hedged with a taker order on the other, so both
        # markets have to trade the same underlying asset.
        require_interchangeable_pairs("buying_market.trading_pair", self.buying_market.trading_pair,
                                      "selling_market.trading_pair", self.selling_market.trading_pair)
        return self
