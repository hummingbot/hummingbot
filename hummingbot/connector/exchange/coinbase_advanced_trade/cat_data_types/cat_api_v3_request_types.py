from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field
from pydantic.class_validators import validator

from hummingbot.core.utils.class_registry import ClassRegistry
from hummingbot.core.web_assistant.connections.data_types import RESTMethod

from ..cat_utilities.cat_dict_mockable_from_json_mixin import DictMethodMockableFromJsonDocMixin
from ..cat_utilities.cat_pydantic_for_json import (
    PydanticConfigForJsonDatetimeToStr,
    PydanticForJsonConfig,
    PydanticMockableForJson,
)
from .cat_api_v3_enums import (
    CoinbaseAdvancedTradeExchangeOrderStatusEnum,
    CoinbaseAdvancedTradeExchangeOrderTypeEnum,
    CoinbaseAdvancedTradeOrderSide,
)
from .cat_api_v3_order_types import CoinbaseAdvancedTradeAPIOrderConfiguration
from .cat_data_types_utilities import UnixTimestampSecondFieldToDatetime, UnixTimestampSecondFieldToStr
from .cat_endpoint_rate_limit import EndpointRateLimit
from .cat_protocols import CoinbaseAdvancedTradeAPIRequestProtocol


class CoinbaseAdvancedTradeRequestError(Exception):
    pass


class CoinbaseAdvancedTradeRequest(
    ClassRegistry,
    DictMethodMockableFromJsonDocMixin,
    EndpointRateLimit,
    ABC
):
    @property
    @abstractmethod
    def endpoint(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def method(self) -> RESTMethod:
        raise NotImplementedError

    @abstractmethod
    def data(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def params(self) -> Dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def is_auth_required() -> bool:
        """
        Returns the request data as a dictionary.
        """
        raise NotImplementedError


class _RequestBase(PydanticForJsonConfig):
    """Base class for all Coinbase Advanced Trade API request dataclasses."""

    class Config(PydanticConfigForJsonDatetimeToStr):
        """Pydantic Config overrides."""
        extra = "forbid"
        allow_mutation = False

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


class _RequestGET(_RequestBase):
    """Base class for GET Coinbase Advanced Trade API request dataclasses."""

    @property
    def method(self) -> RESTMethod:
        """Sets GET method"""
        return RESTMethod.GET

    def params(self) -> Dict[str, Any]:
        """Returns the request data as a dictionary."""
        return self.dict()

    def data(self) -> Dict[str, Any]:
        """Returns an empty dictionary."""
        return {}


class _RequestPOST(_RequestBase):
    """Base class for POST Coinbase Advanced Trade API request dataclasses."""

    @property
    def method(self) -> RESTMethod:
        """Set POST method"""
        return RESTMethod.POST

    def params(self) -> Dict[str, Any]:
        """Returns an empty dictionary."""
        return {}

    def data(self) -> Dict[str, Any]:
        """Returns the request data as a dictionary."""
        return self.dict()


class CoinbaseAdvancedTradeListAccountsRequest(_RequestGET,
                                               PydanticMockableForJson,
                                               CoinbaseAdvancedTradeRequest,
                                               ):
    """
    Dataclass representing request parameters for ListAccountsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
    ```json
    {
        "limit": 0,
        "cursor": "string"
    }
    ```
    """
    # TODO: Verify that the limit is 49 by default and 250 max.
    limit: Optional[int] = Field(None, lt=251, description='A pagination limit with default of 49 and maximum of 250. '
                                                           'If has_next is true, additional orders are available to '
                                                           'be fetched with pagination and the cursor value in the '
                                                           'response can be passed as cursor parameter in the '
                                                           'subsequent request.')
    cursor: Optional[str] = Field(None, description='Cursor used for pagination. When provided, the response returns '
                                                    'responses after this cursor.')

    @property
    def endpoint(self) -> str:
        return "accounts"


class CoinbaseAdvancedTradeGetAccountRequest(_RequestGET,
                                             PydanticMockableForJson,
                                             CoinbaseAdvancedTradeRequest,
                                             ):
    """
    Dataclass representing request parameters for GetAccountEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccount
    ```json
    {
        "account_uuid": "string"
    }
    ```
    """
    account_uuid: str = Field(..., extra={'path_param': True}, description="The account's UUID.")

    @property
    def endpoint(self) -> str:
        return f"accounts/{self.account_uuid}"

    def limit_id(self: CoinbaseAdvancedTradeAPIRequestProtocol) -> str:
        return "GetAccount"


class CoinbaseAdvancedTradeCreateOrderRequest(_RequestPOST,
                                              PydanticMockableForJson,
                                              CoinbaseAdvancedTradeRequest,
                                              ):
    """
    Dataclass representing request parameters for CreateOrderEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
        "client_order_id": "string",
        "product_id": "string",
        "side": "UNKNOWN_ORDER_SIDE",
        "order_configuration": {
            "market_market_ioc": {
            "quote_size": "10.00",
            "base_size": "0.001"
          },
          "limit_limit_gtc": {
            "base_size": "0.001",
            "limit_price": "10000.00",
            "post_only": false
          },
          "limit_limit_gtd": {
            "base_size": "0.001",
            "limit_price": "10000.00",
            "end_time": "2021-05-31T09:59:59Z",
            "post_only": false
          },
          "stop_limit_stop_limit_gtc": {
            "base_size": "0.001",
            "limit_price": "10000.00",
            "stop_price": "20000.00",
            "stop_direction": "UNKNOWN_STOP_DIRECTION"
          },
          "stop_limit_stop_limit_gtd": {
            "base_size": "0.001",
            "limit_price": "10000.00",
            "stop_price": "20000.00",
            "end_time": "2021-05-31T09:59:59Z",
            "stop_direction": "UNKNOWN_STOP_DIRECTION"
          }
        }
    }
    ```
    """
    client_order_id: str = Field(..., description='Client set unique uuid for this order')
    product_id: str = Field(..., description="The product this order was created for e.g. 'BTC-USD'")
    side: CoinbaseAdvancedTradeOrderSide = Field(None, description='Possible values: [UNKNOWN_ORDER_SIDE, BUY, SELL]')
    order_configuration: CoinbaseAdvancedTradeAPIOrderConfiguration = Field(None, description='Order configuration')

    @property
    def endpoint(self) -> str:
        return "orders"


class CoinbaseAdvancedTradeCancelOrdersRequest(_RequestPOST,
                                               PydanticMockableForJson,
                                               CoinbaseAdvancedTradeRequest,
                                               ):
    """
    Dataclass representing request parameters for CancelOrdersEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders
    ```json
    {
        "order_ids": [
            "string"
        ]
    }
    ```
    """
    order_ids: List[str] = Field(..., description='The IDs of orders cancel requests should be initiated for')

    @property
    def endpoint(self) -> str:
        return "orders/batch_cancel"


class CoinbaseAdvancedTradeListOrdersRequest(_RequestGET,
                                             PydanticMockableForJson,
                                             CoinbaseAdvancedTradeRequest,
                                             ):
    """
    Dataclass representing request parameters for ListOrdersEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorders
    ```json
    {
        "product_id": "string",
        "order_status": [
            "OPEN"
        ],
        "limit": 0,
        "start_date": "2021-07-01T00:00:00.000Z",
        "end_date": "2021-07-01T00:00:00.000Z",
        "user_native_currency": "string",
        "order_type": "UNKNOWN_ORDER_TYPE",
        "order_side": "UNKNOWN_ORDER_SIDE",
        "cursor": "string",
        "product_type": "string",
        "order_placement_source": "string"
    }
    ```
    """
    product_id: Optional[str] = Field(None, description='Optional string of the product ID. Defaults to null, '
                                                        'or fetch for all products.')
    order_status: Optional[List[CoinbaseAdvancedTradeExchangeOrderStatusEnum]] = Field(None,
                                                                                       description='A list of order '
                                                                                                   'statuses.')
    limit: Optional[int] = Field(None, description='A pagination limit with no default set. If has_next is true, '
                                                   'additional orders are available to be fetched with pagination; '
                                                   'also the cursor value in the response can be passed as cursor '
                                                   'parameter in the subsequent request.')
    start_date: Optional[UnixTimestampSecondFieldToDatetime] = Field(None,
                                                                     description='Start date to fetch orders from, '
                                                                                 'inclusive.')
    end_date: Optional[UnixTimestampSecondFieldToDatetime] = Field(None,
                                                                   description='An optional end date for the query '
                                                                               'window, exclusive. If'
                                                                               'provided only orders with creation '
                                                                               'time before this date'
                                                                               'will be returned.')
    user_native_currency: Optional[str] = Field(None,
                                                description='String of the users native currency. Default is USD.')
    order_type: Optional[CoinbaseAdvancedTradeExchangeOrderTypeEnum] = Field(None, description='Type of orders to '
                                                                                               'return. Default is to'
                                                                                               ' return all order '
                                                                                               'types.')
    order_side: Optional[CoinbaseAdvancedTradeOrderSide] = Field(None, description='Only orders matching this side '
                                                                                   'are returned. Default is to '
                                                                                   'return all sides.')
    cursor: Optional[str] = Field(None, description='Cursor used for pagination. When provided, the response returns '
                                                    'responses after this cursor.')
    product_type: Optional[str] = Field(None, description='Only orders matching this product type are returned. '
                                                          'Default is to return all product types.')
    order_placement_source: Optional[str] = Field(None, description='Only orders matching this placement source are '
                                                                    'returned. Default is to return RETAIL_ADVANCED '
                                                                    'placement source.')

    @property
    def endpoint(self) -> str:
        return "orders/historical/batch"

    @validator('order_status', pre=True)
    def validate_order_status(cls, v):
        if CoinbaseAdvancedTradeExchangeOrderStatusEnum.OPEN in v and len(v) > 1:
            raise ValueError('OPEN is not allowed with other order statuses')
        return v

    class Config:
        json_encoders = {
            # TODO: Check on Coinbase Help for correct format
            datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S") + f".{v.microsecond // 1000:03d}Z",
        }


class CoinbaseAdvancedTradeGetOrderRequest(_RequestGET,
                                           PydanticMockableForJson,
                                           CoinbaseAdvancedTradeRequest,
                                           ):
    """
    Dataclass representing request parameters for GetOrderEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorder
    ```json
    {
        "order_id": "string",
        "client_order_id": "string",
        "user_native_currency": "string"
    }
    ```
    """
    order_id: str = Field(..., extra={'path_param': True}, description='The ID of the order to retrieve.')

    # Deprecated
    client_order_id: Optional[str] = Field(None, description='Deprecated: Client Order ID to fetch the order with.')
    user_native_currency: Optional[str] = Field(None, description='Deprecated: User native currency to fetch order '
                                                                  'with.')

    @property
    def endpoint(self) -> str:
        return f"orders/historical/{self.order_id}"

    def limit_id(self: CoinbaseAdvancedTradeAPIRequestProtocol) -> str:
        return "GetOrder"


class CoinbaseAdvancedTradeListFillsRequest(_RequestGET,
                                            PydanticMockableForJson,
                                            CoinbaseAdvancedTradeRequest,
                                            ):
    """
    Dataclass representing request parameters for ListFillsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getfills
    ```json
    {
        "order_id": "string",
        "product_id": "string",
        "start_sequence_timestamp": "2021-01-01T00:00:00.123Z",
        "end_sequence_timestamp": "2021-01-01T00:00:00.123Z",
        "limit": 0,
        "cursor": "string"
    }
    ```
    """
    order_id: Optional[str] = Field(None, description='ID of order')
    product_id: Optional[str] = Field(None, description='The ID of the product this order was created for.')
    start_sequence_timestamp: Optional[UnixTimestampSecondFieldToDatetime] = Field(None,
                                                                                   description='Start date. '
                                                                                               'Only fills with '
                                                                                               'a trade time'
                                                                                               'at or after this '
                                                                                               'start date are '
                                                                                               'returned.')
    end_sequence_timestamp: Optional[UnixTimestampSecondFieldToDatetime] = Field(None,
                                                                                 description='End date. Only fills '
                                                                                             'with a trade time'
                                                                                             'before this start date '
                                                                                             'are returned.')
    limit: Optional[int] = Field(None, description='Maximum number of fills to return in response. Defaults to 100.')
    cursor: Optional[str] = Field(None, description='Cursor used for pagination. When provided, the response returns '
                                                    'responses after this cursor.')

    @property
    def endpoint(self) -> str:
        return "orders/historical/fills"

    class Config:
        json_encoders = {
            # TODO: Check on Coinbase Help for correct format
            datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S") + f".{v.microsecond // 1000:03d}Z",
        }


class CoinbaseAdvancedTradeGetProductBookRequest(_RequestGET,
                                                 PydanticMockableForJson,
                                                 CoinbaseAdvancedTradeRequest,
                                                 ):
    """
    Dataclass representing request parameters for ListProductsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproducts
    ```json
    {
        "product_id": "BTC-USD",
        "limit": 0
    }
    ```
    """
    product_id: str = Field(..., description='The trading pair to get book information for.')
    limit: Optional[int] = Field(None, description='Number of products to offset before returning.')

    @property
    def endpoint(self) -> str:
        return "product_book"


class CoinbaseAdvancedTradeGetBestBidAskRequest(_RequestGET,
                                                PydanticMockableForJson,
                                                CoinbaseAdvancedTradeRequest,
                                                ):
    """
    Dataclass representing request parameters for ListProductsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproducts
    ```json
    {
        "product_ids":
        [
            "BTC-USD",
            "ETH-USD"
        ]
    }
    ```
    """
    product_ids: List[str] = Field(..., description='The trading pair to get book information for.')

    @property
    def endpoint(self) -> str:
        return "best_bid_ask"


class CoinbaseAdvancedTradeListProductsRequest(_RequestGET,
                                               PydanticMockableForJson,
                                               CoinbaseAdvancedTradeRequest,
                                               ):
    """
    Dataclass representing request parameters for ListProductsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproducts
    ```json
    {
        "limit": 100,
        "offset": 0,
        "product_type": "SPOT"
    }
    ```
    """
    limit: Optional[int] = Field(None, description='A limit describing how many products to return.')
    offset: Optional[int] = Field(None, description='Number of products to offset before returning.')
    product_type: Optional[str] = Field(None, description='Type of products to return.')

    @property
    def endpoint(self) -> str:
        return "products"


class CoinbaseAdvancedTradeGetProductRequest(_RequestGET,
                                             PydanticMockableForJson,
                                             CoinbaseAdvancedTradeRequest,
                                             ):
    """
    Dataclass representing request parameters for GetProductEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproduct
    ```json
    {
        "product_id": "BTC-USD"
    }
    ```
    """
    product_id: str = Field(..., extra={'path_param': True}, description='The trading pair to get information for.')

    @property
    def endpoint(self) -> str:
        return f"products/{self.product_id}"

    def limit_id(self: CoinbaseAdvancedTradeAPIRequestProtocol) -> str:
        return "GetProduct"


class CoinbaseAdvancedTradeGetProductCandlesRequest(_RequestGET,
                                                    PydanticMockableForJson,
                                                    CoinbaseAdvancedTradeRequest,
                                                    ):
    """
    Dataclass representing request parameters for GetProductCandlesEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getcandles
    ```json
    {
        "product_id": "BTC-USD",
        "start": "1577836800.0",
        "end": "1577923200.0",
        "granularity": "FIVE_MINUTE"
    }
    ```
    """
    product_id: str = Field(..., extra={'path_param': True}, description='The trading pair.')
    start: UnixTimestampSecondFieldToStr = Field(..., description='Timestamp for starting range of aggregations, '
                                                                  'in UNIX time.')
    end: UnixTimestampSecondFieldToStr = Field(..., description='Timestamp for ending range of aggregations, '
                                                                'in UNIX time.')
    granularity: str = Field(..., description='The time slice value for each candle.')

    class Config:
        json_encoders = {
            datetime: lambda v: str(v.timestamp()),
        }

    @property
    def endpoint(self) -> str:
        return f"products/{self.product_id}/candles"

    def limit_id(self: CoinbaseAdvancedTradeAPIRequestProtocol) -> str:
        return "ProductCandles"


class CoinbaseAdvancedTradeGetMarketTradesRequest(_RequestGET,
                                                  PydanticMockableForJson,
                                                  CoinbaseAdvancedTradeRequest,
                                                  ):
    """
    Dataclass representing request parameters for GetMarketTradesEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getmarkettrades
    ```json
    {
        "product_id": "BTC-USD",
        "limit": 100
    }
    ```
    """
    product_id: str = Field(..., extra={'path_param': True}, description="The trading pair, i.e., 'BTC-USD'.")
    limit: int = Field(..., description='Number of trades to return.')

    @property
    def endpoint(self) -> str:
        return f"products/{self.product_id}/ticker"

    def limit_id(self: CoinbaseAdvancedTradeAPIRequestProtocol) -> str:
        return "GetMarketTrades"


class CoinbaseAdvancedTradeGetTransactionSummaryRequest(_RequestGET,
                                                        PydanticMockableForJson,
                                                        CoinbaseAdvancedTradeRequest,
                                                        ):
    """
    Dataclass representing request parameters for TransactionSummaryEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gettransactionsummary
    ```json
    {
        "start_date": "2021-01-01T00:00:00.123Z",
        "end_date": "2021-01-02T00:00:00.123Z",
        "user_native_currency": "USD",
        "product_type": "SPOT"
    }
    ```
    """
    start_date: Optional[UnixTimestampSecondFieldToDatetime] = Field(None, description='Start date.')
    end_date: Optional[UnixTimestampSecondFieldToDatetime] = Field(None, description='End date.')
    user_native_currency: Optional[str] = Field(None, description='String of the users native currency, default is USD')
    product_type: Optional[str] = Field(None, description='Type of product')

    @property
    def endpoint(self) -> str:
        return "transaction_summary"

    class Config:
        json_encoders = {
            # TODO: Check on Coinbase Help for correct format
            datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S") + f".{v.microsecond // 1000:03d}Z",
        }
