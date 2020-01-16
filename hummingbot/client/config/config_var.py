from typing import (
    Optional,
    Callable,
)


class ConfigVar:
    def __init__(self,
                 key: str,
                 prompt: Optional[any],
                 is_secure: bool = False,
                 default: any = None,
                 type_str: str = "str",
                 # Whether this config will be prompted during the setup process
                 required_if: Callable = lambda: True,
                 validator: Callable = lambda *args: True,
                 on_validated: Callable = lambda *args: None,
                 # a default value for when a config is not found on an old configuration file (during migration).
                 migration_default: any = None):
        self._prompt = prompt
        self.key = key
        self.value = None
        self.is_secure = is_secure
        self.default = default
        self.type = type_str
        self._required_if = required_if
        self._validator = validator
        self._on_validated = on_validated
        self.migration_default = migration_default

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

    def validate(self, value: str) -> bool:
        assert callable(self._validator)
        assert callable(self._on_validated)
        valid = self._validator(value)
        if valid:
            self._on_validated(value)
        return valid
