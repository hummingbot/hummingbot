import inspect
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional

import yaml
from pydantic import BaseModel, Field, validator
from pydantic.fields import FieldInfo
from pydantic.schema import default_ref_template
from yaml import SafeDumper

from hummingbot.client.config.config_helpers import strategy_config_schema_encoder
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_strategy,
)
from hummingbot.client.settings import AllConnectorSettings


class ClientConfigEnum(Enum):
    def __str__(self):
        return self.value


def decimal_representer(dumper: SafeDumper, data: Decimal):
    return dumper.represent_float(float(data))


def enum_representer(dumper: SafeDumper, data: ClientConfigEnum):
    return dumper.represent_str(str(data))


def date_representer(dumper: SafeDumper, data: date):
    return dumper.represent_date(data)


def time_representer(dumper: SafeDumper, data: time):
    return dumper.represent_str(data.strftime("%H:%M:%S"))


def datetime_representer(dumper: SafeDumper, data: datetime):
    return dumper.represent_datetime(data)


yaml.add_representer(
    data_type=Decimal, representer=decimal_representer, Dumper=SafeDumper
)
yaml.add_multi_representer(
    data_type=ClientConfigEnum, multi_representer=enum_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=date, representer=date_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=time, representer=time_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=datetime, representer=datetime_representer, Dumper=SafeDumper
)


@dataclass()
class ClientFieldData:
    prompt: Optional[Callable[['BaseClientModel'], str]] = None
    prompt_on_new: bool = False
    is_secure: bool = False


@dataclass()
class TraversalItem:
    depth: int
    config_path: str
    attr: str
    value: Any
    printable_value: str
    client_field_data: Optional[ClientFieldData]
    field_info: FieldInfo


class BaseClientModel(BaseModel):
    class Config:
        validate_assignment = True
        title = None

    """
    Notes on configs:
    - In nested models, be weary that pydantic will take the first model that fits
      (see https://pydantic-docs.helpmanual.io/usage/model_config/#smart-union).
    """
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

    def traverse(self) -> Generator[TraversalItem, None, None]:
        """The intended use for this function is to simplify (validated) config map traversals in the client code."""
        depth = 0
        for attr, field in self.__fields__.items():
            value = self.__getattribute__(attr)
            printable_value = str(value) if not isinstance(value, BaseClientModel) else value.Config.title
            field_info = field.field_info
            client_field_data = field_info.extra.get("client_data")
            yield TraversalItem(
                depth, attr, attr, value, printable_value, client_field_data, field_info
            )
            if isinstance(value, BaseClientModel):
                for traversal_item in value.traverse():
                    traversal_item.depth += 1
                    config_path = f"{attr}.{traversal_item.config_path}"
                    traversal_item.config_path = config_path
                    yield traversal_item

    def dict_in_conf_order(self) -> Dict[str, Any]:
        d = {}
        for attr in self.__fields__.keys():
            value = self.__getattribute__(attr)
            if isinstance(value, BaseClientModel):
                value = value.dict_in_conf_order()
            d[attr] = value
        return d

    async def get_client_prompt(self, attr_name: str) -> Optional[str]:
        prompt = None
        client_data = self.get_client_data(attr_name)
        if client_data is not None:
            prompt = client_data.prompt
            if inspect.iscoroutinefunction(prompt):
                prompt = await prompt(self)
            else:
                prompt = prompt(self)
        return prompt

    def is_secure(self, attr_name: str) -> bool:
        client_data = self.get_client_data(attr_name)
        secure = client_data is not None and client_data.is_secure
        return secure

    def get_client_data(self, attr_name: str) -> Optional[ClientFieldData]:
        return self.__fields__[attr_name].field_info.extra.get("client_data")

    def get_description(self, attr_name: str) -> str:
        return self.__fields__[attr_name].field_info.description

    def generate_yml_output_str_with_comments(self) -> str:
        original_fragments = yaml.safe_dump(self.dict_in_conf_order(), sort_keys=False).split("\n")
        fragments_with_comments = [self._generate_title()]
        self._add_model_fragments(self, fragments_with_comments, original_fragments)
        fragments_with_comments.append("\n")  # EOF empty line
        yml_str = "".join(fragments_with_comments)
        return yml_str

    def _generate_title(self) -> str:
        title = f"{self.Config.title}"
        title = self._adorn_title(title)
        return title

    @staticmethod
    def _adorn_title(title: str) -> str:
        if title:
            title = f"###   {title} config   ###"
            title_len = len(title)
            title = f"{'#' * title_len}\n{title}\n{'#' * title_len}"
        return title

    @staticmethod
    def _add_model_fragments(
        model: 'BaseClientModel',
        fragments_with_comments: List[str],
        original_fragments: List[str],
    ):
        for i, traversal_item in enumerate(model.traverse()):
            attr_comment = traversal_item.field_info.description
            if attr_comment is not None:
                comment_prefix = f"\n{' ' * 2 * traversal_item.depth}# "
                attr_comment = "".join(f"{comment_prefix}{c}" for c in attr_comment.split("\n"))
                if traversal_item.depth == 0:
                    attr_comment = f"\n{attr_comment}"
                fragments_with_comments.extend([attr_comment, f"\n{original_fragments[i]}"])
            elif traversal_item.depth == 0:
                fragments_with_comments.append(f"\n\n{original_fragments[i]}")
            else:
                fragments_with_comments.append(f"\n{original_fragments[i]}")


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

    def _generate_title(self) -> str:
        title = " ".join([w.capitalize() for w in f"{self.strategy}".split("_")])
        title = f"{title} Strategy"
        title = self._adorn_title(title)
        return title


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
            prompt=lambda mi: BaseTradingStrategyConfigMap.maker_trading_pair_prompt(mi),
            prompt_on_new=True,
        ),
    )

    @classmethod
    def maker_trading_pair_prompt(cls, model_instance: 'BaseTradingStrategyConfigMap') -> str:
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
