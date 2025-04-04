from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hummingbot.client.config.config_validators import validate_connector


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
    model_config = ConfigDict(validate_assignment=True, title=None, extra="forbid", json_encoders={
        datetime: lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"),
    })

    @classmethod
    def _clear_schema_cache(cls):
        cls.__schema_cache__ = {}

    def is_required(self, attr: str) -> bool:
        default = self.model_fields[attr].default
        if (hasattr(self.model_fields[attr].annotation, "_name") and
                self.model_fields[attr].annotation._name != "Optional" and (default is None or default == Ellipsis)):
            return True
        else:
            return False


class BaseConnectorConfigMap(BaseClientModel):
    connector: str = Field(
        default=...,
        json_schema_extra={
            "prompt": "What is your connector?",
            "prompt_on_new": True,
        },
    )

    @field_validator("connector", mode="before")
    @classmethod
    def validate_connector(cls, v: str):
        ret = validate_connector(v)
        if ret is not None:
            raise ValueError(ret)
        return v
