from typing import Dict

from pydantic import Field, validator

from hummingbot.client.config.config_data_types import BaseClientModel, ClientConfigEnum, ClientFieldData
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_strategy,
)
from hummingbot.client.settings import AllConnectorSettings


class BaseStrategyConfigMap(BaseClientModel):
    strategy: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda mi: "What is your market making strategy?",
            prompt_on_new=True,
        ),
    )

    @validator("strategy", pre=True)
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
        client_data=ClientFieldData(
            prompt=lambda mi: "Input your maker spot connector",
            prompt_on_new=True,
        ),
    )
    market: str = Field(
        default=...,
        description="The trading pair.",
        client_data=ClientFieldData(
            prompt=lambda mi: BaseTradingStrategyConfigMap.trading_pair_prompt(mi),
            prompt_on_new=True,
        ),
    )

    @classmethod
    def trading_pair_prompt(cls, model_instance: 'BaseTradingStrategyConfigMap') -> str:
        exchange = model_instance.exchange
        example = AllConnectorSettings.get_example_pairs().get(exchange)
        return (
            f"Enter the token trading pair you would like to trade on"
            f" {exchange}{f' (e.g. {example})' if example else ''}"
        )

    @validator("exchange", pre=True)
    def validate_exchange(cls, v: str):
        """Used for client-friendly error output."""
        ret = validate_exchange(v)
        if ret is not None:
            raise ValueError(ret)

        cls.__fields__["exchange"].type_ = ClientConfigEnum(  # rebuild the exchanges enum
            value="Exchanges",  # noqa: F821
            names={e: e for e in sorted(AllConnectorSettings.get_exchange_names())},
            type=str,
        )
        cls._clear_schema_cache()

        return v

    @validator("market", pre=True)
    def validate_exchange_trading_pair(cls, v: str, values: Dict):
        exchange = values.get("exchange")
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
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter your maker spot connector",
            prompt_on_new=True,
        ),
    )
    taker_market: ClientConfigEnum(
        value="TakerMarkets",  # noqa: F821
        names={e: e for e in sorted(AllConnectorSettings.get_exchange_names())},
        type=str,
    ) = Field(
        default=...,
        description="The name of the taker exchange connector.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter your taker spot connector",
            prompt_on_new=True,
        ),
    )
    maker_market_trading_pair: str = Field(
        default=...,
        description="The name of the maker trading pair.",
        client_data=ClientFieldData(
            prompt=lambda mi: BaseTradingStrategyMakerTakerConfigMap.trading_pair_prompt(mi, True),
            prompt_on_new=True,
        ),
    )
    taker_market_trading_pair: str = Field(
        default=...,
        description="The name of the taker trading pair.",
        client_data=ClientFieldData(
            prompt=lambda mi: BaseTradingStrategyMakerTakerConfigMap.trading_pair_prompt(mi, False),
            prompt_on_new=True,
        ),
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

    @validator(
        "maker_market",
        "taker_market",
        pre=True
    )
    def validate_exchange(cls, v: str, field: Field):
        """Used for client-friendly error output."""
        ret = validate_exchange(v)
        if ret is not None:
            raise ValueError(ret)

        enum_name = "MakerMarkets" if field.alias == "maker_market" else "TakerMarkets"

        field.type_ = ClientConfigEnum(  # rebuild the exchanges enum
            value=enum_name,
            names={e: e for e in sorted(AllConnectorSettings.get_exchange_names())},
            type=str,
        )
        cls._clear_schema_cache()

        return v

    @validator(
        "maker_market_trading_pair",
        "taker_market_trading_pair",
        pre=True,
    )
    def validate_exchange_trading_pair(cls, v: str, values: Dict, field: Field):
        ret = None
        if field.name == "maker_market_trading_pair":
            exchange = values.get("maker_market")
            ret = validate_market_trading_pair(exchange, v)
        if field.name == "taker_market_trading_pair":
            exchange = values.get("taker_market")
            ret = validate_market_trading_pair(exchange, v)
        if ret is not None:
            raise ValueError(ret)
        return v
