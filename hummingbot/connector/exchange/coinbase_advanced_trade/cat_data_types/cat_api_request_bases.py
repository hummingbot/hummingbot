from abc import ABC, abstractmethod
from typing import Any, Dict, Protocol

from hummingbot.core.utils.class_registry import RegisteredClassProtocol
from hummingbot.core.web_assistant.connections.data_types import RESTMethod

from ..cat_utilities.cat_dict_mockable_from_json_mixin import DictMethodMockableFromJsonDocMixin
from ..cat_utilities.cat_pydantic_for_json import PydanticConfigForJsonDatetimeToStr, PydanticForJsonConfig
from .cat_api_v3_enums import CoinbaseAdvancedTradeRateLimitType as _RateLimitType


class _RequestProtocolAbstractException(Exception):
    pass


class _EndpointPcl(Protocol):
    BASE_ENDPOINT: str

    def endpoint(self) -> str:
        ...


class _RequestProtocolAbstract(
    ABC,  # Defines the method that the subclasses must implement to match the Protocol
):

    # --- Coinbase Advanced Trade API request Protocol ---
    def base_endpoint(self: _EndpointPcl) -> str:
        return f"{self.BASE_ENDPOINT}/{self.endpoint()}"

    # Must implement, but this is not part of the required Protocol
    @abstractmethod
    def endpoint(self) -> str:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def method(cls) -> RESTMethod:
        raise _RequestProtocolAbstractException(
            "The method method() must be implemented by subclasses.\n"
        )

    @abstractmethod
    def data(self) -> Dict[str, Any]:
        raise _RequestProtocolAbstractException(
            "The method data() must be implemented by subclasses.\n"
        )

    @abstractmethod
    def params(self) -> Dict[str, Any]:
        raise _RequestProtocolAbstractException(
            "The method params() must be implemented by subclasses.\n"
        )

    @classmethod
    @abstractmethod
    def limit_id(cls: RegisteredClassProtocol) -> str:
        raise _RequestProtocolAbstractException(
            "The method limit_id() must be implemented by subclasses.\n"
        )

    @staticmethod
    @abstractmethod
    def is_auth_required() -> bool:
        raise _RequestProtocolAbstractException(
            "The method limit_id must be implemented by subclasses.\n"
        )

    @classmethod
    @abstractmethod
    def linked_limit(cls) -> _RateLimitType:
        raise _RequestProtocolAbstractException(
            "The method linked_limit must be implemented by subclasses.\n"
        )


class _RegisteredWithLinkedLimitProtocol(RegisteredClassProtocol):
    @classmethod
    def linked_limit(cls) -> _RateLimitType:
        ...


class _RequestBase(
    PydanticForJsonConfig,  # Pydantic base class for all Request
    DictMethodMockableFromJsonDocMixin,  # Pydantic base class dict mockable from json doc
):
    """Base class for all Coinbase Advanced Trade API request dataclasses."""

    class Config(PydanticConfigForJsonDatetimeToStr):
        """Pydantic Config overrides."""
        extra = "forbid"
        allow_mutation = False

    @classmethod
    def limit_id(cls: _RegisteredWithLinkedLimitProtocol) -> str:
        # The limit_id is automatically set to the class nickname.
        # It should not be changed because the RateLimit class gets initialized
        # with the limit_id at class creation, not at instantiation
        return cls.short_class_name() + cls.linked_limit().value

    @staticmethod
    def is_auth_required() -> bool:
        """Returns True for all Coinbase Advanced Trade requests."""
        return True

    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Overrides the default dict method to:
            - exclude unset fields from the request data.
            - exclude None fields from the request data.
            - remove Path Parameters from the request data.
        """
        kwargs['exclude_unset'] = True
        kwargs['exclude_none'] = True
        _dict: Dict[str, Any] = super().dict(*args, **kwargs)
        _dict: Dict[str, Any] = self._exclude_path_params(_dict)
        return _dict

    def _exclude_path_params(self, _dict: Dict[str, Any]) -> Dict[str, Any]:
        """Removes non-path parameters from the request data."""
        return {k: v for k, v in _dict.items()
                if not self.__fields__[k].field_info.extra.get('path_param', False)}


class _RequestPOST(_RequestBase, ABC):
    """Base class for POST Coinbase Advanced Trade API request dataclasses."""

    @classmethod
    def method(cls) -> RESTMethod:
        """Set POST method"""
        return RESTMethod.POST

    def params(self) -> Dict[str, Any]:
        """Returns an empty dictionary."""
        return {}

    def data(self) -> Dict[str, Any]:
        """Returns the request data as a dictionary."""
        return self.dict()


class _RequestGET(_RequestBase, ABC):
    """Base class for GET Coinbase Advanced Trade API request dataclasses."""

    @classmethod
    def method(cls) -> RESTMethod:
        """Sets GET method"""
        return RESTMethod.GET

    def params(self) -> Dict[str, Any]:
        """Returns the request data as a dictionary."""
        return self.dict()

    def data(self) -> Dict[str, Any]:
        """Returns an empty dictionary."""
        return {}
