from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Callable

from pydantic import BaseModel
from pydantic.schema import default_ref_template

from hummingbot.client.config.config_helpers import strategy_config_schema_encoder


class ClientConfigEnum(Enum):
    def __str__(self):
        return self.value


@dataclass()
class ClientFieldData:
    prompt: Optional[Callable[['BaseClientModel'], str]] = None
    prompt_on_new: bool = False


class BaseClientModel(BaseModel):
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

    def get_client_prompt(self, attr_name: str) -> Optional[str]:
        prompt = None
        client_data = self.get_client_data(attr_name)
        if client_data is not None:
            prompt = client_data.prompt(self)
        return prompt

    def get_client_data(self, attr_name: str) -> Optional[ClientFieldData]:
        return self.__fields__[attr_name].field_info.extra["client_data"]
