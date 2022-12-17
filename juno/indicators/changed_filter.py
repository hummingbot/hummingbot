from typing import Generic, Optional, TypeVar

T = TypeVar("T")


class ChangedFilter(Generic[T]):
    """Pass a value only if it differs from previous value."""

    _value: Optional[T] = None
    _value_changed: bool = False

    @property
    def value(self) -> Optional[T]:
        return self._value if self._value_changed else None

    @property
    def prevailing_value(self) -> Optional[T]:
        return self._value

    def update(self, value: T) -> Optional[T]:
        self._value_changed = value != self._value
        self._value = value
        return self.value
