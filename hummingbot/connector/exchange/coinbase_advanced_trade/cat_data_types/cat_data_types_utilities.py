from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from pprint import pprint
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Type, TypeVar, Union, cast

from pydantic.class_validators import validator
from pydantic.fields import Field
from pydantic.generics import Generic, GenericModel

_max_timestamp = datetime(year=3000, month=1, day=1).timestamp()  # Corresponds to 6AM UTC
_min_timestamp = datetime(year=2000, month=1, day=1).timestamp()  # Corresponds to 6AM UTC

U = TypeVar("U", float, str, datetime)

_TimeInput = Union[int, float, datetime, str, "UnixTimestampSecondField", Decimal]


class UnixTimestampSecondFieldError(Exception):
    pass


class UnixTimestampSecondField(Generic[U]):
    _type: Type = U

    __slots__ = ()

    def __init__(self, *args, **kwargs):
        raise UnixTimestampSecondFieldError("UnixTimestampSecondField cannot be instantiated.")

    def __call__(self, *args, **kwargs):
        raise UnixTimestampSecondFieldError("UnixTimestampSecondField cannot be called.")

    def __repr__(self):
        return f"{self.__class__.__name__}()"

    @classmethod
    def __get_validators__(cls) -> Iterable[Callable[[Any, Any], U]]:
        yield cls.validate

    @classmethod
    def validate(cls, date_or_time: Optional[_TimeInput]) -> Optional[U]:
        """
        Validate and convert the value to a float representing the Unix timestamp in seconds.

        This validator method is called before assigning the value to the `value` attribute.
        It accepts various input types such as int, float, datetime, str, and other instances of
        `UnixTimestampSecondField`. It validates the input and converts it to a float representing
        the Unix timestamp in seconds.

        :param date_or_time: The date or time to validate and convert.
        :return: The converted float value representing the Unix timestamp in seconds.
        :raises ValueError: If the input value is not a valid float.
        :raises TypeError: If the input value is not of a supported type.
        """

        def _convert_to_float(value: _TimeInput) -> Optional[U]:
            if isinstance(value, (int, float, Decimal)):
                return float(value)
            if isinstance(value, str):
                return cls._date_or_time_from_string(value)
            if isinstance(value, datetime):
                return value.replace(tzinfo=timezone.utc).timestamp()
            if value is None:
                return None
            raise TypeError("Unsupported value type. Expected int, float, str, or datetime.")

        timestamp_s: Optional[float] = _convert_to_float(date_or_time)
        if timestamp_s is None:
            return None

        timestamp_s: float = cls._timestamp_fuzzy_verification(timestamp_s)

        if cls._type == datetime:
            return datetime.fromtimestamp(timestamp_s, tz=timezone.utc)

        return cls._type(timestamp_s)

    @classmethod
    def _date_or_time_from_string(cls, date_or_time: str) -> float:
        """
        Transform a str representing a date or time to a float
        representing the Unix timestamp in seconds.

        :param date_or_time: The timestamp to verify.
        :return: The converted float value representing the Unix timestamp in seconds.
        """
        try:
            timestamp_s: float = float(date_or_time)
            return timestamp_s
        except ValueError:
            try:
                date_or_time = date_or_time.replace("Z", "+00:00")
                if len(date_or_time) >= 33:
                    date_or_time = date_or_time[:26] + date_or_time[-6:]
                timestamp_s: float = datetime.fromisoformat(date_or_time).timestamp()
                return timestamp_s
            except ValueError as e:
                raise ValueError(f"Invalid float value: {date_or_time}") from e

    @classmethod
    def _timestamp_fuzzy_verification(cls, timestamp_s: float) -> float:
        """
        Verify that the timestamp is a reasonable representation of .

        :param timestamp_s: The timestamp to verify.
        :return: True if the value is a valid datetime object, False otherwise.
        """
        if timestamp_s > _max_timestamp:
            raise ValueError(f"Timestamp {timestamp_s} corresponds to a date in year 3000!.")

        if timestamp_s < _min_timestamp:
            raise ValueError(f"Timestamp {timestamp_s} is older than 2000/1/1")

        return timestamp_s


class UnixTimestampSecondFieldToStr(UnixTimestampSecondField[str]):
    _type: Type = str


class UnixTimestampSecondFieldToFloat(UnixTimestampSecondField[float]):
    _type: Type = float


class UnixTimestampSecondFieldToDatetime(UnixTimestampSecondField[datetime]):
    _type: Type = datetime


class _UnixTimestampSecondField(GenericModel, Generic[U]):
    """
    Model field for representing a Unix timestamp in seconds.

    This field accepts various input types such as int, float, datetime, str, and other instances of
    `UnixTimestampSecondField`. It validates the input and converts it to a float value representing
    the Unix timestamp in seconds.

    Example usage:
    ```python
    class MyModel(BaseModel):
        timestamp: UnixTimestampSecondField
    ```

    Attributes:
    - `value`: The value of the Unix timestamp in seconds.
    """
    value: Optional[U] = Field(None, description="Unix timestamp in seconds.")

    class Config:
        arbitrary_types_allowed = True

    def __setattr__(self, name: str, value: U):
        """
        Set the attribute value after validating it as a float.

        This method overrides the base class's `__setattr__` method to validate the value as a float
        before setting the attribute.

        :param name: The name of the attribute.
        :param value: The value to set for the attribute.
        """
        new_value: U = cast(U, self.validate(value))
        super().__setattr__(name, new_value)

    @validator("value", pre=True)
    def validate(cls, date_or_time: Optional[_TimeInput]) -> Optional[U]:
        """
        Validate and convert the value to a float representing the Unix timestamp in seconds.

        This validator method is called before assigning the value to the `value` attribute.
        It accepts various input types such as int, float, datetime, str, and other instances of
        `UnixTimestampSecondField`. It validates the input and converts it to a float representing
        the Unix timestamp in seconds.

        :param date_or_time: The date or time to validate and convert.
        :return: The converted float value representing the Unix timestamp in seconds.
        :raises ValueError: If the input value is not a valid float.
        :raises TypeError: If the input value is not of a supported type.
        """

        def _convert_to_float(value: _TimeInput) -> Optional[U]:
            if isinstance(value, UnixTimestampSecondField):
                return float(value.value)
            if isinstance(value, (int, float, Decimal)):
                return float(value)
            if isinstance(value, str):
                return cls._date_or_time_from_string(value)
            if isinstance(value, datetime):
                return value.replace(tzinfo=timezone.utc).timestamp()
            if value is None:
                return None
            raise TypeError("Unsupported value type. Expected int, float, str, or datetime.")

        timestamp_s: Optional[float] = _convert_to_float(date_or_time)
        if timestamp_s is None:
            return None
        pprint((cls.__annotations__.get("value").type))
        pprint((cls.__fields__.get("value")))
        pprint(vars(cls))
        timestamp_s: Optional[U] = cls._timestamp_fuzzy_verification(timestamp_s, cls)

        return cast(U, timestamp_s)

    # @classmethod
    # def __concrete_name__(cls: Type[Any], params: Tuple[Type[Any], ...]) -> str:
    #     return f'{params[0].__name__.title()}UnixTimestampSecondField'

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]):
        """
        Modify the JSON schema for the field.

        This method modifies the JSON schema for the field by updating the type to "float".

        :param field_schema: The JSON schema for the field.
        """
        if U is float:
            field_schema.update(type="float")
        elif U is str:
            field_schema.update(type="str")

    @classmethod
    def _date_or_time_from_string(cls, date_or_time: str) -> float:
        """
        Transform a str representing a date or time to a float
        representing the Unix timestamp in seconds.

        :param date_or_time: The timestamp to verify.
        :return: The converted float value representing the Unix timestamp in seconds.
        """
        try:
            timestamp_s: float = float(date_or_time)
            return timestamp_s
        except ValueError:
            try:
                date_or_time = date_or_time.replace("Z", "+00:00")
                if len(date_or_time) >= 33:
                    date_or_time = date_or_time[:26] + date_or_time[-6:]
                timestamp_s: float = datetime.fromisoformat(date_or_time).timestamp()
                return timestamp_s
            except ValueError as e:
                raise ValueError(f"Invalid float value: {date_or_time}") from e

    @classmethod
    def _timestamp_fuzzy_verification(cls, timestamp_s: float, type_: Type[U]) -> U:
        """
        Verify that the timestamp is a reasonable representation of .

        :param timestamp_s: The timestamp to verify.
        :return: True if the value is a valid datetime object, False otherwise.
        """
        if timestamp_s > _max_timestamp:
            raise ValueError(f"Timestamp {timestamp_s} corresponds to a date in year 3000!.")

        if timestamp_s < _min_timestamp:
            raise ValueError(f"Timestamp {timestamp_s} is older than 2000/1/1")

        print(type_)
        return timestamp_s


T = TypeVar('T')
V = TypeVar('V')


class DataIterableMixin(Generic[T], ABC):
    @property
    @abstractmethod
    def iter_field_name(self) -> str:
        """
        This method should be overridden to provide the name of the field to be iterated over.
        """
        pass

    def iter(self) -> Iterable[T]:
        """
        Iterate over the field specified by `iter_field_name`.

        :return: An iterable of items from the specified field.
        """
        field = self.__getattribute__(self.iter_field_name)
        for item in field:
            yield item


class NestedDataIterableMixin(DataIterableMixin[T], Generic[T, V], ABC):
    def iter_nested(self) -> Iterable[V]:
        """
        Iterate over nested items in the field specified by `iter_field_name`.

        :return: An iterable of nested items from the specified field.
        """
        nested_iterable = self.__getattribute__(self.iter_field_name)
        for item in nested_iterable:
            if hasattr(item, 'iter_nested'):
                yield from item.iter_nested()
            elif hasattr(item, 'iter'):
                yield from item.iter()
            elif isinstance(item, (List, Tuple, Set)):
                yield from item
