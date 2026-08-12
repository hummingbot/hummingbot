from decimal import Decimal
from typing import Literal, Optional

from pydantic import model_validator

from hummingbot.strategy_v2.executors.data_types import ConnectorPair, ExecutorConfigBase
from hummingbot.strategy_v2.executors.validation import require_interchangeable_pairs, require_positive


class ArbitrageExecutorConfig(ExecutorConfigBase):
    type: Literal["arbitrage_executor"] = "arbitrage_executor"
    buying_market: ConnectorPair
    selling_market: ConnectorPair
    order_amount: Decimal
    min_profitability: Decimal
    gas_conversion_price: Optional[Decimal] = None

    @model_validator(mode="after")
    def validate_arbitrage(self):
        require_positive("order_amount", self.order_amount)
        require_positive("gas_conversion_price", self.gas_conversion_price)
        if self.buying_market == self.selling_market:
            raise ValueError(f"buying_market and selling_market must be different markets, both are "
                             f"{self.buying_market.connector_name} {self.buying_market.trading_pair}")
        # The asset bought on one venue is the one sold on the other, so both markets have
        # to trade the same underlying asset.
        require_interchangeable_pairs("buying_market.trading_pair", self.buying_market.trading_pair,
                                      "selling_market.trading_pair", self.selling_market.trading_pair)
        return self
