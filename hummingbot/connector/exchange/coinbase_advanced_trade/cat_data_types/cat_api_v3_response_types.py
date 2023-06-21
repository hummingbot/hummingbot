from typing import Optional, Tuple

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_enums import (
    CoinbaseAdvancedTradeCancelFailureReason,
    CoinbaseAdvancedTradeCreateOrderFailureReason,
    CoinbaseAdvancedTradeExchangeAccountTypeEnum,
    CoinbaseAdvancedTradeExchangeOrderStatusEnum,
    CoinbaseAdvancedTradeExchangeOrderTypeEnum,
    CoinbaseAdvancedTradeExchangeTimeInForceEnum,
    CoinbaseAdvancedTradeExchangeTradeTypeEnum,
    CoinbaseAdvancedTradeGoodsAndServicesTaxType,
    CoinbaseAdvancedTradeLiquidityIndicator,
    CoinbaseAdvancedTradeNewOrderFailureReason,
    CoinbaseAdvancedTradeOrderSide,
    CoinbaseAdvancedTradePreviewFailureReason,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_order_types import (
    CoinbaseAdvancedTradeAPIOrderConfiguration,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_data_types_utilities import (
    UnixTimestampSecondFieldToFloat,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_dict_mockable_from_json_mixin import (
    DictMethodMockableFromJsonDocMixin,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_pydantic_for_json import (
    PydanticForJsonConfig,
    PydanticMockableForJson,
)
from hummingbot.core.utils.class_registry import ClassRegistry


class CoinbaseAdvancedTradeResponseError(Exception):
    pass


class CoinbaseAdvancedTradeResponse(
    ClassRegistry,
    DictMethodMockableFromJsonDocMixin,
):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class _Balance(PydanticForJsonConfig):
    """
    Balance Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
    ```json
    {
      "value": "1.23",
      "currency": "BTC"
    }
    """
    value: str
    currency: str


class CoinbaseAdvancedTradeAccount(PydanticForJsonConfig):
    """
    Account Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
    ```json
    {
      "uuid": "8bfc20d7-f7c6-4422-bf07-8243ca4169fe",
      "name": "BTC Wallet",
      "currency": "BTC",
      "available_balance": {...},
      "default": false,
      "active": true,
      "created_at": "2021-05-31T09:59:59Z",
      "updated_at": "2021-05-31T09:59:59Z",
      "deleted_at": "2021-05-31T09:59:59Z",
      "type": "ACCOUNT_TYPE_UNSPECIFIED",
      "ready": true,
      "hold": {...}
    }
    ```
    """
    uuid: str
    name: str
    currency: str
    available_balance: _Balance
    default: bool
    active: bool
    created_at: str
    updated_at: str
    deleted_at: str
    type: CoinbaseAdvancedTradeExchangeAccountTypeEnum
    ready: bool
    hold: _Balance


class CoinbaseAdvancedTradeGetAccountResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    GetAccount Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
    ```json
    {
      "account": {
        "uuid": "8bfc20d7-f7c6-4422-bf07-8243ca4169fe",
        "name": "BTC Wallet",
        "currency": "BTC",
        "available_balance": {
          "value": "1.23",
          "currency": "BTC"
        },
        "default": false,
        "active": true,
        "created_at": "2021-05-31T09:59:59Z",
        "updated_at": "2021-05-31T09:59:59Z",
        "deleted_at": "2021-05-31T09:59:59Z",
        "type": "ACCOUNT_TYPE_UNSPECIFIED",
        "ready": true,
        "hold": {
          "value": "1.23",
          "currency": "BTC"
        }
      }
    }
    ```
    """
    account: CoinbaseAdvancedTradeAccount


class CoinbaseAdvancedTradeListAccountsResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    ListAccounts Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
    ```json
    {
      "accounts":
      [
        {
          "uuid": "8bfc20d7-f7c6-4422-bf07-8243ca4169fe",
          "name": "BTC Wallet",
          "currency": "BTC",
          "available_balance": {
            "value": "1.23",
            "currency": "BTC"
          },
          "default": false,
          "active": true,
          "created_at": "2021-05-31T09:59:59Z",
          "updated_at": "2021-05-31T09:59:59Z",
          "deleted_at": "2021-05-31T09:59:59Z",
          "type": "ACCOUNT_TYPE_UNSPECIFIED",
          "ready": true,
          "hold": {
            "value": "1.23",
            "currency": "BTC"
          }
        }
      ],
      "has_next": true,
      "cursor": "789100",
      "size": 10
    }
    ```
    """
    accounts: Tuple[CoinbaseAdvancedTradeAccount, ...]
    has_next: bool
    cursor: Optional[str]
    size: int


# --- Orders ---


class _SuccessResponse(PydanticForJsonConfig):
    """
    Success Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
      "order_id": "11111-00000-000000",
      "product_id": "BTC-USD",
      "side": "UNKNOWN_ORDER_SIDE",
      "client_order_id": "0000-00000-000000"
    }
    ```
    """
    order_id: str
    product_id: str
    side: CoinbaseAdvancedTradeOrderSide
    client_order_id: str


class CoinbaseAdvancedTradeCreateOrderFailureResponse(PydanticForJsonConfig):
    """
    CreateOrder Failure Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
      "error": "UNKNOWN_FAILURE_REASON",
      "message": "The order configuration was invalid",
      "error_details": "Market orders cannot be placed with empty order sizes",
      "preview_failure_reason": "UNKNOWN_PREVIEW_FAILURE_REASON",
      "new_order_failure_reason": "UNKNOWN_FAILURE_REASON"
    }
    ```
    """
    error: CoinbaseAdvancedTradeCreateOrderFailureReason
    message: str
    error_details: str
    preview_failure_reason: CoinbaseAdvancedTradePreviewFailureReason
    new_order_failure_reason: CoinbaseAdvancedTradeNewOrderFailureReason


class CoinbaseAdvancedTradeCreateOrderResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    CreateOrder Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
      "success": true,
      "failure_reason": "UNKNOWN_FAILURE_REASON",
      "order_id": "string",
      "success_response": {
        "order_id": "11111-00000-000000",
        "product_id": "BTC-USD",
        "side": "UNKNOWN_ORDER_SIDE",
        "client_order_id": "0000-00000-000000"
      },
      "error_response": {
        "error": "UNKNOWN_FAILURE_REASON",
        "message": "The order configuration was invalid",
        "error_details": "Market orders cannot be placed with empty order sizes",
        "preview_failure_reason": "UNKNOWN_PREVIEW_FAILURE_REASON",
        "new_order_failure_reason": "UNKNOWN_FAILURE_REASON"
      },
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
    success: bool
    failure_reason: Optional[CoinbaseAdvancedTradeCreateOrderFailureReason] = None
    order_id: Optional[str] = None
    success_response: Optional[_SuccessResponse] = None
    error_response: Optional[CoinbaseAdvancedTradeCreateOrderFailureResponse] = None
    order_configuration: Optional[CoinbaseAdvancedTradeAPIOrderConfiguration] = None


class _CancelOrderResult(PydanticForJsonConfig):
    """
    CancelOrder Result Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders
    ```json
    {
      "success": true,
      "failure_reason": "UNKNOWN_CANCEL_FAILURE_REASON",
      "order_id": "0000-00000"
    }
    ```
    """
    success: bool
    failure_reason: CoinbaseAdvancedTradeCancelFailureReason
    order_id: str


class CoinbaseAdvancedTradeCancelOrdersResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    CancelOrders Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders
    ```json
    {
      "results":
      [
        {
          "success": true,
          "failure_reason": "UNKNOWN_CANCEL_FAILURE_REASON",
          "order_id": "0000-00000"
        }
      ]
    }
    ```
    """
    results: Tuple[_CancelOrderResult, ...]


class _OrderDetails(PydanticForJsonConfig):
    """
    OrderDetails Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getorder
    ```json
    {
      "order_id": "0000-000000-000000",
      "product_id": "BTC-USD",
      "user_id": "2222-000000-000000",
      "order_configuration": {...},
      "side": "UNKNOWN_ORDER_SIDE",
      "client_order_id": "11111-000000-000000",
      "status": "OPEN",
      "time_in_force": "UNKNOWN_TIME_IN_FORCE",
      "created_time": "2021-05-31T09:59:59Z",
      "completion_percentage": "50",
      "filled_size": "0.001",
      "average_filled_price": "50",
      "fee": "string",
      "number_of_fills": "2",
      "filled_value": "10000",
      "pending_cancel": true,
      "size_in_quote": false,
      "total_fees": "5.00",
      "size_inclusive_of_fees": false,
      "total_value_after_fees": "string",
      "trigger_status": "UNKNOWN_TRIGGER_STATUS",
      "order_type": "UNKNOWN_ORDER_TYPE",
      "reject_reason": "REJECT_REASON_UNSPECIFIED",
      "settled": true,
      "product_type": "SPOT",
      "reject_message": "string",
      "cancel_message": "string",
      "order_placement_source": "RETAIL_ADVANCED"
    }
    ```
    """
    order_id: str
    product_id: str
    user_id: str
    order_configuration: CoinbaseAdvancedTradeAPIOrderConfiguration
    side: CoinbaseAdvancedTradeOrderSide
    client_order_id: str
    status: CoinbaseAdvancedTradeExchangeOrderStatusEnum
    time_in_force: CoinbaseAdvancedTradeExchangeTimeInForceEnum
    created_time: str
    completion_percentage: str
    filled_size: str
    average_filled_price: str
    fee: str
    number_of_fills: str
    filled_value: str
    pending_cancel: bool
    size_in_quote: bool
    total_fees: str
    size_inclusive_of_fees: bool
    total_value_after_fees: str
    trigger_status: str
    order_type: CoinbaseAdvancedTradeExchangeOrderTypeEnum
    reject_reason: str
    settled: bool
    product_type: str
    reject_message: str
    cancel_message: str
    order_placement_source: str


class CoinbaseAdvancedTradeListOrdersResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    ListOrders Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorders
    ```json
    {
      "orders":
      [
        {
          "order_id": "0000-000000-000000",
          "product_id": "BTC-USD",
          "user_id": "2222-000000-000000",
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
          },
          "side": "UNKNOWN_ORDER_SIDE",
          "client_order_id": "11111-000000-000000",
          "status": "OPEN",
          "time_in_force": "UNKNOWN_TIME_IN_FORCE",
          "created_time": "2021-05-31T09:59:59Z",
          "completion_percentage": "50",
          "filled_size": "0.001",
          "average_filled_price": "50",
          "fee": "string",
          "number_of_fills": "2",
          "filled_value": "10000",
          "pending_cancel": true,
          "size_in_quote": false,
          "total_fees": "5.00",
          "size_inclusive_of_fees": false,
          "total_value_after_fees": "string",
          "trigger_status": "UNKNOWN_TRIGGER_STATUS",
          "order_type": "UNKNOWN_ORDER_TYPE",
          "reject_reason": "REJECT_REASON_UNSPECIFIED",
          "settled": true,
          "product_type": "SPOT",
          "reject_message": "string",
          "cancel_message": "string",
          "order_placement_source": "RETAIL_ADVANCED"
        }
      ],
      "sequence": "string",
      "has_next": true,
      "cursor": "789100"
    }
    ```
    """
    orders: Tuple[_OrderDetails, ...]
    sequence: str
    has_next: bool
    cursor: str


class _FillDetails(PydanticForJsonConfig):
    entry_id: str
    trade_id: str
    order_id: str
    trade_time: str
    trade_type: CoinbaseAdvancedTradeExchangeTradeTypeEnum
    price: str
    size: str
    commission: str
    product_id: str
    sequence_timestamp: str
    liquidity_indicator: CoinbaseAdvancedTradeLiquidityIndicator
    size_in_quote: bool
    user_id: str
    side: CoinbaseAdvancedTradeOrderSide


class CoinbaseAdvancedTradeListFillsResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    ListFills Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getfills
    ```json
    {
      "fills":
        [
          {
            "entry_id": "22222-2222222-22222222",
            "trade_id": "1111-11111-111111",
            "order_id": "0000-000000-000000",
            "trade_time": "2021-05-31T09:59:59Z",
            "trade_type": "FILL",
            "price": "10000.00",
            "size": "0.001",
            "commission": "1.25",
            "product_id": "BTC-USD",
            "sequence_timestamp": "2021-05-31T09:58:59Z",
            "liquidity_indicator": "UNKNOWN_LIQUIDITY_INDICATOR",
            "size_in_quote": false,
            "user_id": "3333-333333-3333333",
            "side": "UNKNOWN_ORDER_SIDE"
          }
        ],
      "cursor": "789100"
    }
    ```
    """
    fills: Tuple[_FillDetails, ...]
    cursor: str


class CoinbaseAdvancedTradeGetOrderResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    GetOrder Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorder
    ```json
    {
      "order": {
        "order_id": "0000-000000-000000",
        "product_id": "BTC-USD",
        "user_id": "2222-000000-000000",
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
        },
        "side": "UNKNOWN_ORDER_SIDE",
        "client_order_id": "11111-000000-000000",
        "status": "OPEN",
        "time_in_force": "UNKNOWN_TIME_IN_FORCE",
        "created_time": "2021-05-31T09:59:59Z",
        "completion_percentage": "50",
        "filled_size": "0.001",
        "average_filled_price": "50",
        "fee": "string",
        "number_of_fills": "2",
        "filled_value": "10000",
        "pending_cancel": true,
        "size_in_quote": false,
        "total_fees": "5.00",
        "size_inclusive_of_fees": false,
        "total_value_after_fees": "string",
        "trigger_status": "UNKNOWN_TRIGGER_STATUS",
        "order_type": "UNKNOWN_ORDER_TYPE",
        "reject_reason": "REJECT_REASON_UNSPECIFIED",
        "settled": true,
        "product_type": "SPOT",
        "reject_message": "string",
        "cancel_message": "string",
        "order_placement_source": "RETAIL_ADVANCED"
      }
    }
    ```
    """
    order: _OrderDetails


# --- Products ---

class _PriceBookEntry(PydanticForJsonConfig):
    """
    PriceBookEntry Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproductbook
    ```json
    {
      "price": "string",
      "size": "string"
    }
    ```
    """
    price: str
    size: str


class _PriceBook(PydanticForJsonConfig):
    """
    PriceBook Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproductbook
    ```json
    {
      "product_id": "string",
      "bids": [...],
      "asks": [...],
      "time": "1609459200.123"
    }
    ```
    """
    product_id: str
    bids: Tuple[_PriceBookEntry, ...]
    asks: Tuple[_PriceBookEntry, ...]
    time: UnixTimestampSecondFieldToFloat


class CoinbaseAdvancedTradeGetProductBookResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    GetProductBook Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproductbook

    One caveat: The time is immediately changed from a string to a float, thus
    the time field is not a string as in the documentation.
    ```json
    {
      "pricebooks":
      [
        {
          "product_id": "string",
          "bids": [
            {
              "price": "string",
              "size": "string"
            }
          ],
          "asks": [
            {
              "price": "string",
              "size": "string"
            }
          ],
          "time": 1609459200.123
        }
      ]
    }
    ```
    """
    pricebooks: Tuple[_PriceBook, ...]


class CoinbaseAdvancedTradeGetBestBidAskResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    GetProductBook Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getbestbidask

    One caveat: The time is immediately changed from a string to a float, thus
    the time field is not a string as in the documentation.
    ```json
    {
      "pricebooks":
      [
        {
          "product_id": "string",
          "bids": [
            {
              "price": "string",
              "size": "string"
            }
          ],
          "asks": [
            {
              "price": "string",
              "size": "string"
            }
          ],
          "time": 1609459200.123
        }
      ]
    }
    ```
    """
    pricebooks: Tuple[_PriceBook, ...]


class CoinbaseAdvancedTradeGetProductResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    GetProduct Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproduct
    ```json
    {
      "product_id": "BTC-USD",
      "price": "140.21",
      "price_percentage_change_24h": "9.43%",
      "volume_24h": "1908432",
      "volume_percentage_change_24h": "9.43%",
      "base_increment": "0.00000001",
      "quote_increment": "0.00000001",
      "quote_min_size": "0.00000001",
      "quote_max_size": "1000",
      "base_min_size": "0.00000001",
      "base_max_size": "1000",
      "base_name": "Bitcoin",
      "quote_name": "US Dollar",
      "watched": true,
      "is_disabled": false,
      "new": true,
      "status": "string",
      "cancel_only": false,
      "limit_only": false,
      "post_only": false,
      "trading_disabled": false,
      "auction_mode": false,
      "product_type": "string",
      "quote_currency_id": "USD",
      "base_currency_id": "BTC",
      "mid_market_price": "140.22",
      "base_display_symbol": "BTC",
      "quote_display_symbol": "USD"
    }
    ```
    """
    product_id: str
    price: str
    price_percentage_change_24h: str
    volume_24h: str
    volume_percentage_change_24h: str
    base_increment: str
    quote_increment: str
    quote_min_size: str
    quote_max_size: str
    base_min_size: str
    base_max_size: str
    base_name: str
    quote_name: str
    watched: bool
    is_disabled: bool
    new: bool
    status: str
    cancel_only: bool
    limit_only: bool
    post_only: bool
    trading_disabled: bool
    auction_mode: bool
    product_type: str
    quote_currency_id: str
    base_currency_id: str
    mid_market_price: str
    base_display_symbol: str
    quote_display_symbol: str

    # Convenient properties definitions commonly used with HB
    @property
    def supports_market_orders(self) -> bool:
        return all((self.is_tradable is True,
                    self.limit_only is False,
                    self.post_only is False,
                    ))

    @property
    def supports_limit_orders(self) -> bool:
        return all((self.is_tradable is True,
                    self.limit_only is True,
                    ))

    @property
    def is_tradable(self) -> bool:
        is_valid = all((self.product_type == "SPOT",
                        self.trading_disabled is False,
                        self.is_disabled is False,
                        self.cancel_only is False,
                        self.auction_mode is False))
        return is_valid

    @staticmethod
    def is_product_tradable(product: "CoinbaseAdvancedTradeGetProductResponse") -> bool:
        return product.is_tradable


class CoinbaseAdvancedTradeListProductsResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    ListProducts Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproducts
    ```json
    {
      "products":
      [
        {
          "product_id": "BTC-USD",
          "price": "140.21",
          "price_percentage_change_24h": "9.43%",
          "volume_24h": "1908432",
          "volume_percentage_change_24h": "9.43%",
          "base_increment": "0.00000001",
          "quote_increment": "0.00000001",
          "quote_min_size": "0.00000001",
          "quote_max_size": "1000",
          "base_min_size": "0.00000001",
          "base_max_size": "1000",
          "base_name": "Bitcoin",
          "quote_name": "US Dollar",
          "watched": true,
          "is_disabled": false,
          "new": true,
          "status": "string",
          "cancel_only": false,
          "limit_only": false,
          "post_only": false,
          "trading_disabled": false,
          "auction_mode": false,
          "product_type": "SPOT",
          "quote_currency_id": "USD",
          "base_currency_id": "BTC",
          "mid_market_price": "140.22",
          "base_display_symbol": "BTC",
          "quote_display_symbol": "USD"
        }
      ],
      "num_products": 100
    }
    ```
    """
    products: Tuple[CoinbaseAdvancedTradeGetProductResponse, ...]
    num_products: int

    @property
    def tradable_products(self) -> Tuple[CoinbaseAdvancedTradeGetProductResponse]:
        return tuple(filter(is_product_tradable, self.products))


class _CandleDetails(PydanticForJsonConfig):
    start: str
    low: str
    high: str
    open: str
    close: str
    volume: str


class CoinbaseAdvancedTradeGetProductCandlesResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    GetProductCandles Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getcandles
    ```json
    {
      "candles":
      [
        {
          "start": "1639508050",
          "low": "140.21",
          "high": "140.21",
          "open": "140.21",
          "close": "140.21",
          "volume": "56437345"
        }
      ]
    }
    ```
    """
    candles: Tuple[_CandleDetails, ...]


# --- Market Data ---

class _TradeDetails(PydanticForJsonConfig):
    trade_id: str
    product_id: str
    price: str
    size: str
    time: str
    side: str
    bid: str
    ask: str


class CoinbaseAdvancedTradeGetMarketTradesResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    GetMarketTrades Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getmarkettrades
    ```json
    {
      "trades":
      [
        {
          "trade_id": "34b080bf-fc5d-445a-832b-46b5ddc65601",
          "product_id": "BTC-USD",
          "price": "140.91",
          "size": "4",
          "time": "2021-05-31T09:59:59Z",
          "side": "UNKNOWN_ORDER_SIDE",
          "bid": "291.13",
          "ask": "292.40"
        }
      ],
      "best_bid": "291.13",
      "best_ask": "292.40"
    }
    ```
    """
    trades: Tuple[_TradeDetails, ...]
    best_bid: str
    best_ask: str


# --- Reports ---

class _FeeTierDetails(PydanticForJsonConfig):
    pricing_tier: str
    usd_from: str
    usd_to: str
    taker_fee_rate: str
    maker_fee_rate: str


class _MarginRateDetails(PydanticForJsonConfig):
    value: str


class _GoodsAndServicesTaxDetails(PydanticForJsonConfig):
    rate: str
    type: CoinbaseAdvancedTradeGoodsAndServicesTaxType


class CoinbaseAdvancedTradeGetTransactionSummaryResponse(PydanticMockableForJson, CoinbaseAdvancedTradeResponse):
    """
    GetTransactionSummary Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gettransactionsummary
    ```json
    {
      "total_volume": 1000.0,
      "total_fees": 25.0,
      "fee_tier": {
        "pricing_tier": "<$10k",
        "usd_from": "0",
        "usd_to": "10,000",
        "taker_fee_rate": "0.0010",
        "maker_fee_rate": "0.0020"
      },
      "margin_rate": {
        "value": "string"
      },
      "goods_and_services_tax": {
        "rate": "string",
        "type": "INCLUSIVE"
      },
      "advanced_trade_only_volume": 1000.0,
      "advanced_trade_only_fees": 25.0,
      "coinbase_pro_volume": 1000.0,
      "coinbase_pro_fees": 25.0
    }
    ```
    """
    total_volume: float
    total_fees: float
    fee_tier: _FeeTierDetails
    margin_rate: _MarginRateDetails
    goods_and_services_tax: _GoodsAndServicesTaxDetails
    advanced_trade_only_volume: float
    advanced_trade_only_fees: float
    coinbase_pro_volume: float
    coinbase_pro_fees: float


class _ErrorDetail(PydanticForJsonConfig):
    type_url: str
    value: str


class CoinbaseAdvancedTradeErrorResponse(PydanticMockableForJson):
    """
    Error Response Data Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gettransactionsummary
    ```json
    {
      "error": "string",
      "code": "integer",
      "message": "string",
      "details":
      [
        {
          "type_url": "string",
          "value": "string"
        }
      ]
    }
    ```
    """
    error: str
    code: str
    message: str
    details: Tuple[_ErrorDetail, ...]


def is_product_tradable(product: CoinbaseAdvancedTradeGetProductResponse) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param product: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return product.is_tradable


def is_valid_account(account_info: CoinbaseAdvancedTradeGetAccountResponse) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param account_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled
False otherwise
    """
    is_valid = all((account_info.account.active,
                    account_info.account.type in (CoinbaseAdvancedTradeExchangeAccountTypeEnum.ACCOUNT_TYPE_CRYPTO,
                                                  CoinbaseAdvancedTradeExchangeAccountTypeEnum.ACCOUNT_TYPE_FIAT),
                    account_info.account.ready))
    return is_valid
