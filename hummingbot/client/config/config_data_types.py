import inspect
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional, List

import yaml
from pydantic import BaseModel, Field, validator
from pydantic.schema import default_ref_template
from yaml import SafeDumper

from hummingbot.client.config.config_helpers import strategy_config_schema_encoder
from hummingbot.client.config.config_validators import validate_strategy


class ClientConfigEnum(Enum):
    def __str__(self):
        return self.value


def decimal_representer(dumper: SafeDumper, data: Decimal):
    return dumper.represent_float(float(data))


def enum_representer(dumper: SafeDumper, data: ClientConfigEnum):
    return dumper.represent_str(str(data))


yaml.add_representer(
    data_type=Decimal, representer=decimal_representer, Dumper=SafeDumper
)
yaml.add_multi_representer(
    data_type=ClientConfigEnum, multi_representer=enum_representer, Dumper=SafeDumper
)


@dataclass()
class ClientFieldData:
    prompt: Optional[Callable[['BaseClientModel'], str]] = None
    prompt_on_new: bool = False
    is_secure: bool = False


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

    def get_client_data(self, attr_name: str) -> Optional[ClientFieldData]:
        return self.__fields__[attr_name].field_info.extra["client_data"]

    def get_description(self, attr_name: str) -> str:
        return self.__fields__[attr_name].field_info.description

    def generate_yml_output_str_with_comments(self) -> str:
        original_fragments = yaml.safe_dump(self.dict(), sort_keys=False).split("\n")
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

    def _add_model_fragments(
        self,
        model: 'BaseClientModel',
        fragments_with_comments: List[str],
        original_fragments: List[str],
        original_fragments_idx: int = 0,
        model_depth: int = 0,
    ) -> int:
        comment_prefix = f"\n{' ' * 2 * model_depth}# "
        for attr in model.__fields__.keys():
            attr_comment = model.get_description(attr)
            if attr_comment is not None:
                attr_comment = "".join(f"{comment_prefix}{c}" for c in attr_comment.split("\n"))
                if model_depth == 0:
                    attr_comment = f"\n{attr_comment}"
                fragments_with_comments.extend([attr_comment, f"\n{original_fragments[original_fragments_idx]}"])
            elif model_depth == 0:
                fragments_with_comments.append(f"\n\n{original_fragments[original_fragments_idx]}")
            else:
                fragments_with_comments.append(f"\n{original_fragments[original_fragments_idx]}")
            original_fragments_idx += 1
            value = model.__getattribute__(attr)
            if isinstance(value, BaseClientModel):
                original_fragments_idx = self._add_model_fragments(
                    value, fragments_with_comments, original_fragments, original_fragments_idx, model_depth + 1
                )
        return original_fragments_idx


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
