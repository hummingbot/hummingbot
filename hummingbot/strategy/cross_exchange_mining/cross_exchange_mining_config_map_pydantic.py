
from decimal import Decimal
from typing import Dict

from pydantic import Field, root_validator, validator

import hummingbot.client.settings as settings
from hummingbot.client.config.config_data_types import (
    BaseTradingStrategyMakerTakerConfigMap,
    ClientFieldData,
)
from hummingbot.client.config.config_validators import validate_bool


class CrossExchangeMiningConfigMap(BaseTradingStrategyMakerTakerConfigMap):
    strategy: str = Field(default="cross_exchange_mining", client_data=None)

    min_profitability: Decimal = Field(
        default=...,
        description="The minimum estimated profitability required to open a position.",
        ge=-100.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%)",
            prompt_on_new=True,
        ),
    )
    order_amount: Decimal = Field(
        default=...,
        description="The amount of base currency for the strategy to maintain over exchanges.",
        ge=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: CrossExchangeMiningConfigMap.order_amount_prompt(mi),
            prompt_on_new=True,
        )
    )

    balance_adjustment_duration: float = Field(
        default=Decimal("5"),
        description="Time interval to rebalance portfolio >>> ",
        client_data=ClientFieldData(
            prompt=lambda mi: "Time interval between subsequent portfolio rebalances ",
            prompt_on_new=True,
        ),
    )

    slippage_buffer: Decimal = Field(
        default=Decimal("5.0"),
        description="Allowed slippage to fill ensure taker orders are filled.",
        ge=0.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "How much buffer do you want to add to the price to account for slippage for taker orders "
                "Enter 1 to indicate 1%"
            ),
            prompt_on_new=True,
        ),
    )

    min_prof_tol_low: Decimal = Field(
        default=Decimal("0.1"),
        description="Tolerance below min prof to cancel order.",
        ge=0.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "What percentage below the min profitability do you want to cancel the set order"
                "Enter 0.1 to indicate 0.1%"
            ),
            prompt_on_new=True,
        ),
    )

    min_prof_tol_high: Decimal = Field(
        default=Decimal("0.1"),
        description="Tolerance above min prof to cancel order.",
        ge=0.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "What percentage above the min profitability level do you want to cancel the set order"
                "Enter 0.1 to indicate 0.1%"
            ),
            prompt_on_new=True,
        ),
    )
    volatility_buffer_size: int = Field(
        default=...,
        description="The period in seconds to calulate volatility over: ",
        client_data=ClientFieldData(
            prompt=lambda mi: "The period in seconds to calulate volatility over: ",
            prompt_on_new=True,
        ),
    )

    min_prof_adj_timer: float = Field(
        default=Decimal("3600"),
        description="Time interval to adjust min profitability over",
        client_data=ClientFieldData(
            prompt=lambda mi: "Time interval to adjust min profitability over by using results of previous trades in last 24 hrs",
            prompt_on_new=True,
        ),
    )
    min_order_amount: Decimal = Field(
        default=Decimal("0.0"),
        description="What is the minimum order amount required for bid or ask orders?: ",
        ge=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                    "What is the minimum order amount required for bid or ask orders?: >>> "
            ),
            prompt_on_new=True,
        ),
    )
    rate_curve: Decimal = Field(
        default=Decimal("1.0"),
        description="Multiplier for rate curve for the adjustment of min profitability: ",
        ge=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                    "Multiplier for rate curve for the adjustment of min profitability: >>> "
            ),
            prompt_on_new=True,
        ),
    )
    trade_fee: Decimal = Field(
        default=Decimal("1.0"),
        description="Complete trade fee covering both taker and maker trades: ",
        ge=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                    "Complete trade fee covering both taker and maker trades: >>> "
            ),
            prompt_on_new=True,
        ),
    )
    # === prompts ===

    @classmethod
    def order_amount_prompt(cls, model_instance: 'CrossExchangeMiningConfigMap') -> str:
        trading_pair = model_instance.maker_market_trading_pair
        base_asset, quote_asset = trading_pair.split("-")
        return f"The amount of {base_asset} for the strategy to maintain in wallet over exchanges (Will autobalance by buying or selling to maintain amount).?"

    # === generic validations ===

    def validate_bool(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v

    @validator(
        "min_profitability",
        "order_amount",
        "balance_adjustment_duration",
        "slippage_buffer",
        "min_prof_tol_high",
        "min_prof_tol_low",
        "volatility_buffer_size",
        "min_prof_adj_timer",
        "min_order_amount",
        "rate_curve",
        "trade_fee",
        pre=True,
    )
    def validate_decimal(cls, v: str, field: Field):
        """Used for client-friendly error output."""
        return super().validate_decimal(v, field)

    # === post-validations ===

    @root_validator()
    def post_validations(cls, values: Dict):
        cls.exchange_post_validation(values)
        cls.update_oracle_settings(values)
        return values

    @classmethod
    def exchange_post_validation(cls, values: Dict):
        if "maker_market" in values.keys():
            settings.required_exchanges.add(values["maker_market"])
        if "taker_market" in values.keys():
            settings.required_exchanges.add(values["taker_market"])

    @classmethod
    def update_oracle_settings(cls, values: str):
        if not ("use_oracle_conversion_rate" in values.keys() and
                "maker_market_trading_pair" in values.keys() and
                "taker_market_trading_pair" in values.keys()):
            return
        use_oracle = values["use_oracle_conversion_rate"]
        first_base, first_quote = values["maker_market_trading_pair"].split("-")
        second_base, second_quote = values["taker_market_trading_pair"].split("-")
        if use_oracle and (first_base != second_base or first_quote != second_quote):
            settings.required_rate_oracle = True
            settings.rate_oracle_pairs = []
            if first_base != second_base:
                settings.rate_oracle_pairs.append(f"{second_base}-{first_base}")
            if first_quote != second_quote:
                settings.rate_oracle_pairs.append(f"{second_quote}-{first_quote}")
        else:
            settings.required_rate_oracle = False
            settings.rate_oracle_pairs = []
