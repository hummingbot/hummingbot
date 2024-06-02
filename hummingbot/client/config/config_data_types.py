from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Extra, Field, validator
from pydantic.schema import default_ref_template

from hummingbot.client.config.config_methods import strategy_config_schema_encoder
from hummingbot.client.config.config_validators import validate_connector, validate_decimal


class ClientConfigEnum(Enum):
    def __str__(self):
        return self.value


@dataclass()
class ClientFieldData:
    prompt: Optional[Callable[['BaseClientModel'], str]] = None
    prompt_on_new: bool = False
    is_secure: bool = False
    is_connect_key: bool = False
    is_updatable: bool = False


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

    @classmethod
    def _clear_schema_cache(cls):
        cls.__schema_cache__ = {}

    def is_required(self, attr: str) -> bool:
        return self.__fields__[attr].required

    def validate_decimal(v: str, field: Field):
        """Used for client-friendly error output."""
        field_info = field.field_info
        inclusive = field_info.ge is not None or field_info.le is not None
        min_value = field_info.gt if field_info.gt is not None else field_info.ge
        min_value = Decimal(min_value) if min_value is not None else min_value
        max_value = field_info.lt if field_info.lt is not None else field_info.le
        max_value = Decimal(max_value) if max_value is not None else max_value
        ret = validate_decimal(v, min_value, max_value, inclusive)
        if ret is not None:
            raise ValueError(ret)
        return v


class BaseConnectorConfigMap(BaseClientModel):
    connector: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda mi: "What is your connector?",
            prompt_on_new=True,
        ),
    )

    @validator("connector", pre=True)
    def validate_connector(cls, v: str):
        ret = validate_connector(v)
        if ret is not None:
            raise ValueError(ret)
        return v
