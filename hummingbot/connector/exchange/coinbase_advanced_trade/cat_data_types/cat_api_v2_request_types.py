from abc import ABC
from datetime import datetime
from typing import Optional

from pydantic import Field

from hummingbot.core.utils.class_registry import ClassRegistry

from ..cat_utilities.cat_pydantic_for_json import PydanticMockableForJson
from .cat_api_request_bases import _RequestGET, _RequestProtocolAbstract
from .cat_api_v3_enums import CoinbaseAdvancedTradeRateLimitType as _RateLimitType
from .cat_data_types_utilities import UnixTimestampSecondFieldToDatetime
from .cat_endpoint_rate_limit import CoinbaseAdvancedTradeEndpointRateLimit


class CoinbaseAdvancedTradeV2RequestException(Exception):
    pass


class CoinbaseAdvancedTradeV2Request(
    ClassRegistry,
    _RequestProtocolAbstract,
    ABC,  # Defines the method that the subclasses must implement to match the Protocol
):
    BASE_ENDPOINT: str = "/v2"  # "/" is added between the base URI and the endpoint

    # This definition allows CoinbaseAdvancedTradeV2Request to be used as a Protocol that
    # receives arguments in the constructor. The main purpose of this class is to be
    # used as a Base class for similar subclasses
    def __init__(self, *args, **kwargs):
        if super().__class__ != object:
            # This check is needed to avoid calling the base class constructor
            # when creating the base class itself.
            super().__init__(*args, **kwargs)

    @classmethod
    def short_class_name(cls) -> str:
        # This method helps clarify that a subclass of this ClassRegistry will
        # have a method called `short_class_name` that returns a string of the
        # class name without the base class (CoinbaseAdvancedTradeV2Request) name.
        raise CoinbaseAdvancedTradeV2RequestException(
            "The method short_class_name should have been dynamically created by ClassRegistry.\n"
            "This exception indicates that the class hierarchy is not correctly implemented and"
            "the CoinbaseAdvancedTradeV2Request.short_class_name() was called instead.\n"
        )

    @classmethod
    def linked_limit(cls) -> _RateLimitType:
        return _RateLimitType.SIGNIN  # This is either REST, WSS or SIGNIN, as Rate Limit categories


class CoinbaseAdvancedTradeTimeV2Request(
    _RequestGET,  # GET method settings
    PydanticMockableForJson,  # Generate samples from docstring JSON
    CoinbaseAdvancedTradeV2Request,  # Sets the base type, registers the class
    CoinbaseAdvancedTradeEndpointRateLimit,  # Rate limit (Must be after CoinbaseAdvancedTradeV2Request)
):
    """
    Dataclass representing request parameters for ListAccountsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/sign-in-with-coinbase/docs/api-time
    ```json
    {
    }
    ```
    """

    def endpoint(self) -> str:
        return "time"

    @staticmethod
    def is_auth_required() -> bool:
        return False


class CoinbaseAdvancedTradeGetSpotPriceV2Request(
    _RequestGET,  # GET method settings
    PydanticMockableForJson,  # Generate samples from docstring JSON
    CoinbaseAdvancedTradeV2Request,  # Sets the base type, registers the class
    CoinbaseAdvancedTradeEndpointRateLimit,  # Rate limit (Must be after CoinbaseAdvancedTradeV2Request)
):
    """
    Dataclass representing request parameters for ListAccountsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/sign-in-with-coinbase/docs/api-time
    ```json
    {
    }
    ```
    """
    currency_pair: str = Field(description="Get the current market price for bitcoin. This is usually somewhere in "
                                           "between the buy and sell price.")
    date: Optional[UnixTimestampSecondFieldToDatetime] = Field(None,
                                                               description="The date for which the price should be "
                                                                           "returned. Defaults to the current time. "
                                                                           "ISO 8601 format (YYYY-MM-DD).",
                                                               )

    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d"),
        }

    def endpoint(self) -> str:
        return f"prices/{self.currency_pair}/spot"

    @staticmethod
    def is_auth_required() -> bool:
        return False
