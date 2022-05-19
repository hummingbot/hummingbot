from decimal import Decimal
from typing import Dict

from pydantic import BaseModel, Field, root_validator, validator

import hummingbot.client.settings as settings
from hummingbot.client.config.config_data_types import BaseTradingStrategyMakerTakerConfigMap, ClientFieldData
from hummingbot.client.config.config_validators import validate_bool, validate_decimal


class CrossExchangeMarketMakingConfigMap(BaseTradingStrategyMakerTakerConfigMap):
    strategy: str = Field(default="cross_exchange_market_making", client_data=None)

    min_profitability: Decimal = Field(
        default=...,
        description="",
        ge=-100.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%)",
            prompt_on_new=True,
        ),
    )
    order_amount: Decimal = Field(
        default=...,
        description="The strategy order amount.",
        ge=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: CrossExchangeMarketMakingConfigMap.order_amount_prompt(mi),
            prompt_on_new=True,
        )
    )
    adjust_order_enabled: bool = Field(
        default=True,
        description="",
        client_data=ClientFieldData(
            prompt=lambda mi: "Do you want to enable adjust order? (Yes/No)"
        ),
    )
    active_order_canceling: bool = Field(
        default=True,
        description="",
        client_data=ClientFieldData(
            prompt=lambda mi: "Do you want to enable active order canceling? (Yes/No)"
        ),
    )
    cancel_order_threshold: Decimal = Field(
        default=Decimal("5.0"),
        description="",
        gt=-100.0,
        lt=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "What is the threshold of profitability to cancel a trade? (Enter 1 to indicate 1%)",
        ),
    )
    limit_order_min_expiration: float = Field(
        default=130.0,
        description="",
        gt=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "How often do you want limit orders to expire (in seconds)?",
        ),
    )
    top_depth_tolerance: Decimal = Field(
        default=Decimal("0.0"),
        description="",
        ge=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: CrossExchangeMarketMakingConfigMap.top_depth_tolerance_prompt(mi),
        ),
    )
    anti_hysteresis_duration: float = Field(
        default=60.0,
        description="",
        gt=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "What is the minimum time interval you want limit orders to be adjusted? (in seconds)",
        ),
    )
    order_size_taker_volume_factor: Decimal = Field(
        default=Decimal("25.0"),
        description="",
        ge=0.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "What percentage of hedge-able volume would you like to be traded on the taker market? "
                "(Enter 1 to indicate 1%)"
            ),
        ),
    )
    order_size_taker_balance_factor: Decimal = Field(
        default=Decimal("99.5"),
        description="",
        ge=0.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "What percentage of asset balance would you like to use for hedging trades on the taker market? "
                "(Enter 1 to indicate 1%)"
            ),
        ),
    )
    order_size_portfolio_ratio_limit: Decimal = Field(
        default=Decimal("16.67"),
        description="",
        ge=0.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "What ratio of your total portfolio value would you like to trade on the maker and taker markets? "
                "Enter 50 for 50%"
            ),
        ),
    )
    use_oracle_conversion_rate: bool = Field(
        default=True,
        description="",
        client_data=ClientFieldData(
            prompt=lambda mi: "Do you want to use rate oracle on unmatched trading pairs? (Yes/No)",
            prompt_on_new=True,
        ),
    )
    taker_to_maker_base_conversion_rate: Decimal = Field(
        default=Decimal("1.0"),
        description="",
        gt=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "Enter conversion rate for taker base asset value to maker base asset value, e.g. "
                "if maker base asset is USD and the taker is DAI, 1 DAI is valued at 1.25 USD, "
                "the conversion rate is 1.25"
            ),
        ),
    )
    taker_to_maker_quote_conversion_rate: Decimal = Field(
        default=Decimal("1.0"),
        description="",
        gt=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "Enter conversion rate for taker quote asset value to maker quote asset value, e.g. "
                "if maker quote asset is USD and the taker is DAI, 1 DAI is valued at 1.25 USD, "
                "the conversion rate is 1.25"
            ),
        ),
    )
    slippage_buffer: Decimal = Field(
        default=Decimal("5.0"),
        description="",
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

    # === prompts ===

    @classmethod
    def top_depth_tolerance_prompt(cls, model_instance: 'CrossExchangeMarketMakingConfigMap') -> str:
        maker_market = model_instance.maker_market_trading_pair
        base_asset, quote_asset = maker_market.split("-")
        return f"What is your top depth tolerance? (in {base_asset})"

    @classmethod
    def order_amount_prompt(cls, model_instance: 'CrossExchangeMarketMakingConfigMap') -> str:
        trading_pair = model_instance.maker_market_trading_pair
        base_asset, quote_asset = trading_pair.split("-")
        return f"What is the amount of {base_asset} per order?"

    # === generic validations ===

    @validator(
        "adjust_order_enabled",
        "active_order_canceling",
        "use_oracle_conversion_rate",
        pre=True,
    )
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
        "cancel_order_threshold",
        "limit_order_min_expiration",
        "top_depth_tolerance",
        "anti_hysteresis_duration",
        "order_size_taker_volume_factor",
        "order_size_taker_balance_factor",
        "order_size_portfolio_ratio_limit",
        "taker_to_maker_base_conversion_rate",
        "taker_to_maker_quote_conversion_rate",
        "slippage_buffer",
        pre=True,
    )
    def validate_decimal(cls, v: str, values: Dict, config: BaseModel.Config, field: Field):
        """Used for client-friendly error output."""
        range_min = None
        range_max = None
        range_inclusive = None

        field = field.field_info

        if field.gt is not None:
            range_min = field.gt
            range_inclusive = False
        elif field.ge is not None:
            range_min = field.ge
            range_inclusive = True
        if field.lt is not None:
            range_max = field.lt
            range_inclusive = False
        elif field.le is not None:
            range_max = field.le
            range_inclusive = True

        if range_min is not None and range_max is not None:
            ret = validate_decimal(v,
                                   min_value=Decimal(str(range_min)),
                                   max_value=Decimal(str(range_max)),
                                   inclusive=str(range_inclusive))
        elif range_min is not None:
            ret = validate_decimal(v,
                                   min_value=Decimal(str(range_min)),
                                   inclusive=str(range_inclusive))
        elif range_max is not None:
            ret = validate_decimal(v,
                                   max_value=Decimal(str(range_max)),
                                   inclusive=str(range_inclusive))
        if ret is not None:
            raise ValueError(ret)
        return v

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
