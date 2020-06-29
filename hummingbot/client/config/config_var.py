from typing import (
    Optional,
    Callable,
)

RequiredIf = Callable[[str], Optional[bool]]
Validator = Callable[[str], Optional[str]]
OnValidated = Callable


class ConfigVar:
    def __init__(self,
                 key: str,
                 prompt: Optional[any],
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
                 is_connect_key: bool = False):
        self._prompt = prompt
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

    @property
    def prompt(self):
        if callable(self._prompt):
            return self._prompt()
        else:
            return self._prompt

    @property
    def required(self) -> bool:
        assert callable(self._required_if)
        return self._required_if()

    def validate(self, value: str) -> Optional[str]:
        assert callable(self._validator)
        assert callable(self._on_validated)
        if self.required and (value is None or value == ""):
            return "Value is required."
        err_msg = self._validator(value)
        if err_msg is None and self._validator is not None:
            self._on_validated(value)
        return err_msg
