import json
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_dict_mockable_from_json_mixin import (
    DictMethodMockableFromJsonDocMixin,
)


class PydanticConfigForJson:
    use_enum_values = False
    json_encoders = {
        Enum: lambda v: v.value,
        tuple: lambda v: list(v),
    }


class PydanticConfigForJsonDatetimeToStr(PydanticConfigForJson):
    json_encoders = {
        # TODO: Check on Coinbase Help for correct format
        #  datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S") + f".{v.microsecond // 1000:03d}Z",
        datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


class PydanticForJsonConfig(BaseModel):
    """
    This class is used to configure the Pydantic models for json serialization
    of classes that use Enums and Tuples.

    """

    class Config(PydanticConfigForJson):
        pass

    def to_dict_for_json(self,
                         *,
                         by_alias: bool = False,
                         skip_defaults: bool = None,
                         exclude_unset: bool = False,
                         exclude_defaults: bool = False,
                         exclude_none: bool = True,
                         encoder: Optional[Callable[[Any], Any]] = None,
                         models_as_dict: bool = True
                         ) -> Dict[str, Any]:
        """
        This method is used to convert the Pydantic model to a dictionary
        that can be serialized to json.
        """
        json_string: str = self.json(
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            encoder=encoder,
            models_as_dict=models_as_dict,
        )

        d = json.loads(json_string)
        return d


class PydanticMockableForJson(PydanticForJsonConfig, DictMethodMockableFromJsonDocMixin):
    pass
