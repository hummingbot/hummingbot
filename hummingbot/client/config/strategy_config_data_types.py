from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.client.config.config_data_types import BaseClientModel, ClientConfigEnum
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_strategy,
)
from hummingbot.client.settings import AllConnectorSettings


class BaseStrategyConfigMap(BaseClientModel):
    strategy: str = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter the strategy name (e.g., market_making, arbitrage): ",
            "prompt_on_new": True,
        }
    )

    @field_validator("strategy", mode="before")
    @classmethod
    def validate_strategy(cls, v: str):
        ret = validate_strategy(v)
        if ret is not None:
            raise ValueError(ret)
        return v


class BaseTradingStrategyConfigMap(BaseStrategyConfigMap):
    exchange: ClientConfigEnum(  # rebuild the exchanges enum
        value="Exchanges",  # noqa: F821
        names={e: e for e in sorted(AllConnectorSettings.get_exchange_names())},
        type=str,
    ) = Field(
        default=...,
        description="The name of the exchange connector.",
        json_schema_extra={"prompt": "Input your maker spot connector", "prompt_on_new": True},
    )
    market: str = Field(
        default=...,
        description="The trading pair.",
        json_schema_extra={"prompt": lambda mi: BaseTradingStrategyConfigMap.trading_pair_prompt(mi), "prompt_on_new": True},
    )

    @classmethod
    def trading_pair_prompt(cls, model_instance: 'BaseTradingStrategyConfigMap') -> str:
        exchange = model_instance.exchange
        example = AllConnectorSettings.get_example_pairs().get(exchange)
        return (
            f"Enter the token trading pair you would like to trade on"
            f" {exchange}{f' (e.g. {example})' if example else ''}"
        )

    @field_validator("exchange", mode="before")
    @classmethod
    def validate_exchange(cls, v: str):
        """Used for client-friendly error output."""
        ret = validate_exchange(v)
        if ret is not None:
            raise ValueError(ret)

        cls.model_fields["exchange"].annotation = ClientConfigEnum(  # rebuild the exchanges enum
            value="Exchanges",  # noqa: F821
            names={e: e for e in sorted(AllConnectorSettings.get_exchange_names())},
            type=str,
        )
        cls._clear_schema_cache()

        return v

    @field_validator("market", mode="before")
    def validate_exchange_trading_pair(cls, v: str, validation_info: ValidationInfo):
        exchange = validation_info.data.get("exchange")
        ret = validate_market_trading_pair(exchange, v)
        if ret is not None:
            raise ValueError(ret)
        return v


class BaseTradingStrategyMakerTakerConfigMap(BaseStrategyConfigMap):
    maker_market: ClientConfigEnum(
        value="MakerMarkets",  # noqa: F821
        names={e: e for e in sorted(AllConnectorSettings.get_exchange_names())},
        type=str,
    ) = Field(
        default=...,
        description="The name of the maker exchange connector.",
        json_schema_extra={"prompt": "Enter your maker spot connector", "prompt_on_new": True},
    )
    taker_market: ClientConfigEnum(
        value="TakerMarkets",  # noqa: F821
        names={e: e for e in sorted(AllConnectorSettings.get_exchange_names())},
        type=str,
    ) = Field(
        default=...,
        description="The name of the taker exchange connector.",
        json_schema_extra={"prompt": "Enter your taker spot connector", "prompt_on_new": True},
    )
    maker_market_trading_pair: str = Field(
        default=...,
        description="The name of the maker trading pair.",
        json_schema_extra={"prompt": lambda mi: BaseTradingStrategyMakerTakerConfigMap.trading_pair_prompt(mi, True), "prompt_on_new": True},
    )
    taker_market_trading_pair: str = Field(
        default=...,
        description="The name of the taker trading pair.",
        json_schema_extra={"prompt": lambda mi: BaseTradingStrategyMakerTakerConfigMap.trading_pair_prompt(mi, False), "prompt_on_new": True},
    )

    @classmethod
    def trading_pair_prompt(cls, model_instance: 'BaseTradingStrategyMakerTakerConfigMap', is_maker: bool) -> str:
        if is_maker:
            exchange = model_instance.maker_market
            example = AllConnectorSettings.get_example_pairs().get(exchange)
            market_type = "maker"
        else:
            exchange = model_instance.taker_market
            example = AllConnectorSettings.get_example_pairs().get(exchange)
            market_type = "taker"
        return (
            f"Enter the token trading pair you would like to trade on {market_type} market:"
            f" {exchange}{f' (e.g. {example})' if example else ''}"
        )

    @field_validator("maker_market_trading_pair", "taker_market_trading_pair", mode="before")
    def validate_exchange_trading_pair(cls, v: str, validation_info: ValidationInfo):
        ret = None
        if validation_info.field_name == "maker_market_trading_pair":
            exchange = validation_info.data.get("maker_market")
            ret = validate_market_trading_pair(exchange, v)
        if validation_info.field_name == "taker_market_trading_pair":
            exchange = validation_info.data.get("taker_market")
            ret = validate_market_trading_pair(exchange, v)
        if ret is not None:
            raise ValueError(ret)
        return v
