from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional, Dict, TypeVar, Generic

from pydantic import BaseModel, Extra, Field, validator
# from pydantic import TypeAdapter  # Comment out this import

# Add compatibility shim for TypeAdapter
T = TypeVar('T')
class TypeAdapter(Generic[T]):
    """
    Compatibility shim for Pydantic v2's TypeAdapter
    This provides a minimal implementation that can be used with Pydantic v1
    """
    def __init__(self, type_):
        self.type_ = type_
    
    def validate_python(self, obj):
        # Simple validation using pydantic's parse_obj_as if it's available
        from pydantic.tools import parse_obj_as
        return parse_obj_as(self.type_, obj)

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
        extra = Extra.forbid
        json_encoders = {
            datetime: lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    def schema_json(
        cls, *, by_alias: bool = True, ref_template: str = "#/definitions/{model}", **dumps_kwargs: Any
    ) -> str:
        schema = cls.schema(by_alias=by_alias)
        return cls.__config__.json_dumps(
            schema,
            default=strategy_config_schema_encoder,
            **dumps_kwargs
        )

    @classmethod
    def _clear_schema_cache(cls):
        pass

    def is_required(self, attr: str) -> bool:
        return attr in self.__fields_set__

    @staticmethod
    def validate_decimal(v: str, info: Dict = None):
        """Used for client-friendly error output."""
        if info is None:
            return v
        inclusive = info.get("ge") is not None or info.get("le") is not None
        min_value = info.get("gt") if info.get("gt") is not None else info.get("ge")
        min_value = Decimal(min_value) if min_value is not None else min_value
        max_value = info.get("lt") if info.get("lt") is not None else info.get("le")
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
