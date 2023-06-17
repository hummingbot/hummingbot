from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_enums import (
    CoinbaseAdvancedTradeExchangeOrderTypeEnum,
    CoinbaseAdvancedTradeOrderSide,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_order_types import (
    CoinbaseAdvancedTradeAPIOrderConfiguration,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_endpoint_rate_limit import (
    EndpointRateLimit,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_protocols import (
    CoinbaseAdvancedTradeAPIRequestProtocol,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_dict_mockable_from_json_mixin import (
    DictMethodMockableFromJsonDocMixin,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_pydantic_for_json import (
    PydanticForJsonConfig,
)
from hummingbot.core.utils.class_registry import ClassRegistry
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class CoinbaseAdvancedTradeRequestError(Exception):
    pass


class CoinbaseAdvancedTradeRequestType(
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

    @staticmethod
    def is_auth_required() -> bool:
        """Returns True for all Coinbase Advanced Trade requests."""
        return True

    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        """Overrides the default dict method to remove Path Parameters from the request data."""
        return {
            k: v for k, v in super().dict(**kwargs).items() if
            not self.__fields__[k].field_info.extra.get('path_param', False)
        }


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
                                               CoinbaseAdvancedTradeRequestType,
                                               ):
    """
    Dataclass representing request parameters for ListAccountsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
    """
    limit: Optional[int] = Field(None, lt=250, description='A pagination limit with default of 49 and maximum of 250. '
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
                                             CoinbaseAdvancedTradeRequestType,
                                             ):
    """
    Dataclass representing request parameters for GetAccountEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccount
    """
    account_uuid: str = Field(..., extra={'path_param': True}, description="The account's UUID.")

    @property
    def endpoint(self) -> str:
        return f"accounts/{self.account_uuid}"

    def limit_id(self: CoinbaseAdvancedTradeAPIRequestProtocol) -> str:
        return "GetAccount"


class CoinbaseAdvancedTradeCreateOrderRequest(_RequestPOST,
                                              CoinbaseAdvancedTradeRequestType,
                                              ):
    """
    Dataclass representing request parameters for CreateOrderEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    """
    client_order_id: str = Field(..., description='Client set unique uuid for this order')
    product_id: str = Field(..., description="The product this order was created for e.g. 'BTC-USD'")
    side: CoinbaseAdvancedTradeOrderSide = Field(None, description='Possible values: [UNKNOWN_ORDER_SIDE, BUY, SELL]')
    order_configuration: CoinbaseAdvancedTradeAPIOrderConfiguration = Field(None, description='Order configuration')

    @property
    def endpoint(self) -> str:
        return "orders"


class CoinbaseAdvancedTradeCancelOrdersRequest(_RequestPOST,
                                               CoinbaseAdvancedTradeRequestType,
                                               ):
    """
    Dataclass representing request parameters for CancelOrdersEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders
    """
    order_ids: List[str] = Field(..., description='The IDs of orders cancel requests should be initiated for')

    @property
    def endpoint(self) -> str:
        return "orders/batch_cancel"


class CoinbaseAdvancedTradeListOrdersRequest(_RequestGET,
                                             CoinbaseAdvancedTradeRequestType,
                                             ):
    """
    Dataclass representing request parameters for ListOrdersEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorders
    """
    product_id: Optional[str] = Field(None, description='Optional string of the product ID. Defaults to null, '
                                                        'or fetch for all products.')
    order_status: Optional[List[str]] = Field(None, description='A list of order statuses.')
    limit: Optional[int] = Field(None, description='A pagination limit with no default set. If has_next is true, '
                                                   'additional orders are available to be fetched with pagination; '
                                                   'also the cursor value in the response can be passed as cursor '
                                                   'parameter in the subsequent request.')
    start_date: Optional[datetime] = Field(None, description='Start date to fetch orders from, inclusive.')
    end_date: Optional[datetime] = Field(None, description='An optional end date for the query window, exclusive. If '
                                                           'provided only orders with creation time before this date '
                                                           'will be returned.')
    user_native_currency: Optional[str] = Field(None, description='String of the users native currency. Default is USD.')
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


class CoinbaseAdvancedTradeGetOrderRequest(_RequestGET,
                                           CoinbaseAdvancedTradeRequestType,
                                           ):
    """
    Dataclass representing request parameters for GetOrderEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorder
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
                                            CoinbaseAdvancedTradeRequestType,
                                            ):
    """
    Dataclass representing request parameters for ListFillsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getfills
    """
    order_id: Optional[str] = Field(None, description='ID of order')
    product_id: Optional[str] = Field(None, description='The ID of the product this order was created for.')
    start_sequence_timestamp: Optional[datetime] = Field(None, description='Start date. Only fills with a trade time '
                                                                           'at or after this start date are returned.')
    end_sequence_timestamp: Optional[datetime] = Field(None, description='End date. Only fills with a trade time '
                                                                         'before this start date are returned.')
    limit: Optional[int] = Field(None, description='Maximum number of fills to return in response. Defaults to 100.')
    cursor: Optional[str] = Field(None, description='Cursor used for pagination. When provided, the response returns '
                                                    'responses after this cursor.')

    @property
    def endpoint(self) -> str:
        return "orders/historical/fills"


class CoinbaseAdvancedTradeListProductsRequest(_RequestGET,
                                               CoinbaseAdvancedTradeRequestType,
                                               ):
    """
    Dataclass representing request parameters for ListProductsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproducts
    """
    limit: Optional[int] = Field(None, description='A limit describing how many products to return.')
    offset: Optional[int] = Field(None, description='Number of products to offset before returning.')
    product_type: Optional[str] = Field(None, description='Type of products to return.')

    @property
    def endpoint(self) -> str:
        return "products"


class CoinbaseAdvancedTradeGetProductRequest(_RequestGET,
                                             CoinbaseAdvancedTradeRequestType,
                                             ):
    """
    Dataclass representing request parameters for GetProductEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproduct
    """
    product_id: str = Field(..., extra={'path_param': True}, description='The trading pair to get information for.')

    @property
    def endpoint(self) -> str:
        return f"products/{self.product_id}"

    def limit_id(self: CoinbaseAdvancedTradeAPIRequestProtocol) -> str:
        return "GetProduct"


class CoinbaseAdvancedTradeGetProductCandlesRequest(_RequestGET,
                                                    CoinbaseAdvancedTradeRequestType,
                                                    ):
    """
    Dataclass representing request parameters for GetProductCandlesEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getcandles
    """
    product_id: str = Field(..., extra={'path_param': True}, description='The trading pair.')
    start: datetime = Field(..., description='Timestamp for starting range of aggregations, in UNIX time.')
    end: datetime = Field(..., description='Timestamp for ending range of aggregations, in UNIX time.')
    granularity: str = Field(..., description='The time slice value for each candle.')

    @property
    def endpoint(self) -> str:
        return f"products/{self.product_id}/candles"

    def limit_id(self: CoinbaseAdvancedTradeAPIRequestProtocol) -> str:
        return "ProductCandles"


class CoinbaseAdvancedTradeGetMarketTradesRequest(_RequestGET,
                                                  CoinbaseAdvancedTradeRequestType,
                                                  ):
    """
    Dataclass representing request parameters for GetMarketTradesEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getmarkettrades
    """
    product_id: str = Field(..., extra={'path_param': True}, description="The trading pair, i.e., 'BTC-USD'.")
    limit: int = Field(..., description='Number of trades to return.')

    @property
    def endpoint(self) -> str:
        return f"products/{self.product_id}/ticker"

    def limit_id(self: CoinbaseAdvancedTradeAPIRequestProtocol) -> str:
        return "GetMarketTrades"


class CoinbaseAdvancedTradeGetTransactionSummaryRequest(_RequestGET,
                                                        CoinbaseAdvancedTradeRequestType,
                                                        ):
    """
    Dataclass representing request parameters for TransactionSummaryEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gettransactionsummary
    """
    start_date: Optional[datetime] = Field(None, description='Start date.')
    end_date: Optional[datetime] = Field(None, description='End date.')
    user_native_currency: Optional[str] = Field(None, description='String of the users native currency, default is USD')
    product_type: Optional[str] = Field(None, description='Type of product')

    @property
    def endpoint(self) -> str:
        return "transaction_summary"
