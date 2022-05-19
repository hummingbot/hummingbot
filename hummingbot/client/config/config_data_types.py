from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Extra, Field, validator
from pydantic.schema import default_ref_template

from hummingbot.client.config.config_methods import strategy_config_schema_encoder
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_strategy,
)
from hummingbot.client.settings import AllConnectorSettings


class ClientConfigEnum(Enum):
    def __str__(self):
        return self.value


@dataclass()
class ClientFieldData:
    prompt: Optional[Callable[['BaseClientModel'], str]] = None
    prompt_on_new: bool = False
    is_secure: bool = False


class BaseClientModel(BaseModel):
    class Config:
        validate_assignment = True
        title = None
        smart_union = True
        extra = Extra.forbid
        json_encoders = {
            datetime: lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    def schema_json(
        cls, *, by_alias: bool = True, ref_template: str = default_ref_template, **dumps_kwargs: Any
    ) -> str:
        # todo: make it ignore `client_data` all together
        return cls.__config__.json_dumps(
            cls.schema(by_alias=by_alias, ref_template=ref_template),
            default=strategy_config_schema_encoder,
            **dumps_kwargs
        )

    def is_required(self, attr: str) -> bool:
        return self.__fields__[attr].required


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
    exchange: ClientConfigEnum(
        value="Exchanges",  # noqa: F821
        names={e: e for e in AllConnectorSettings.get_connector_settings().keys()},
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
            names={e: e for e in AllConnectorSettings.get_connector_settings().keys()},
            type=str,
        )
        return v

    @validator("market", pre=True)
    def validate_exchange_trading_pair(cls, v: str, values: Dict):
        exchange = values.get("exchange")
        ret = validate_market_trading_pair(exchange, v)
        if ret is not None:
            raise ValueError(ret)
        return v


class BaseTradingStrategyMakerTakerConfigMap(BaseStrategyConfigMap):
    maker_market: str = Field(
        default=...,
        description="The name of the maker exchange connector.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter your maker spot connector",
            prompt_on_new=True,
        ),
    )
    taker_market: str = Field(
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
    def validate_exchange(cls, v: str, values: Dict, config: BaseModel.Config, field: Field):
        """Used for client-friendly error output."""
        ret = validate_exchange(v)
        if ret is not None:
            raise ValueError(ret)
        if field.name == "maker_market_trading_pair":
            cls.__fields__["maker_market"].type_ = ClientConfigEnum(  # rebuild the exchanges enum
                value="Exchanges",  # noqa: F821
                names={e: e for e in AllConnectorSettings.get_connector_settings().keys()},
                type=str,
            )
        if field.name == "taker_market_trading_pair":
            cls.__fields__["taker_market"].type_ = ClientConfigEnum(  # rebuild the exchanges enum
                value="Exchanges",  # noqa: F821
                names={e: e for e in AllConnectorSettings.get_connector_settings().keys()},
                type=str,
            )
        return v

    @validator(
        "maker_market_trading_pair",
        "taker_market_trading_pair",
        pre=True,
    )
    def validate_exchange_trading_pair(cls, v: str, values: Dict, config: BaseModel.Config, field: Field):
        if field.name == "maker_market_trading_pair":
            exchange = values.get("maker_market")
            ret = validate_market_trading_pair(exchange, v)
        if field.name == "taker_market_trading_pair":
            exchange = values.get("taker_market")
            ret = validate_market_trading_pair(exchange, v)
        if ret is not None:
            raise ValueError(ret)
        return v
