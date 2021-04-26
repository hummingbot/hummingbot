from typing import (
    Optional,
    Callable
)
import inspect

RequiredIf = Callable[[str], Optional[bool]]
Validator = Callable[[str], Optional[str]]
Prompt = Callable[[str], Optional[str]]
OnValidated = Callable


class ConfigVar:
    def __init__(self,
                 key: str,
                 prompt: Prompt,
                 is_secure: bool = False,
                 default: any = None,
                 type_str: str = "str",
                 # Whether this config will be prompted during the setup process
                 required_if: RequiredIf = lambda: True,
                 validator: Validator = lambda *args: None,
                 on_validated: OnValidated = lambda *args: None,
                 # Whether to prompt a user for value when new strategy config file is created
                 prompt_on_new: bool = False,
                 # Whether this is a config var used in connect command
                 is_connect_key: bool = False,
                 printable_key: str = None):
        self.prompt = prompt
        self.key = key
        self.value = None
        self.is_secure = is_secure
        self.default = default
        self.type = type_str
        self._required_if = required_if
        self._validator = validator
        self._on_validated = on_validated
        self.prompt_on_new = prompt_on_new
        self.is_connect_key = is_connect_key
        self.printable_key = printable_key

    async def get_prompt(self):
        if inspect.iscoroutinefunction(self.prompt):
            return await self.prompt()
        elif inspect.isfunction(self.prompt):
            return self.prompt()
        else:
            return self.prompt

    @property
    def required(self) -> bool:
        assert callable(self._required_if)
        return self._required_if()

    async def validate(self, value: str) -> Optional[str]:
        assert callable(self._validator)
        assert callable(self._on_validated)
        if self.required and (value is None or value == ""):
            return "Value is required."
        err_msg = None
        if inspect.iscoroutinefunction(self._validator):
            err_msg = await self._validator(value)
        elif inspect.isfunction(self._validator):
            err_msg = self._validator(value)
        if err_msg is None and self._validator is not None:
            if inspect.iscoroutinefunction(self._on_validated):
                await self._on_validated(value)
            elif inspect.isfunction(self._on_validated):
                self._on_validated(value)
        return err_msg
