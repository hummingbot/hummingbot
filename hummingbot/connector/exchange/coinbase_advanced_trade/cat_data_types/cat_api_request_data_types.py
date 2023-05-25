from abc import ABC
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_enums import (
    CoinbaseAdvancedTradeOrderSide,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_order_types import (
    CoinbaseAdvancedTradeAPIOrderTypes,
)
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


@dataclass(frozen=True)
class _RequestAbstract(ABC):
    """
    Base class for all Coinbase Advanced Trade API request dataclasses.
    """

    def __post_init__(self):
        for f in fields(self):
            if f.metadata.get('required') and getattr(self, f.name) is None:
                raise ValueError(f'{f.name} is required.')

    def _apply_metadata(self) -> Dict[str, Any]:
        """
        Applies metadata to the data dictionary.
        """
        data: Dict[str, Any] = {}
        for f in fields(self):
            if not f.metadata.get('path_param', False):
                if f.metadata.get('isoformat', False):
                    data[f.name] = getattr(self, f.name).isoformat()
                else:
                    data[f.name] = getattr(self, f.name)
        return data

    @property
    def endpoint(self) -> str:
        """
        Returns the endpoint associated with the request.
        """
        raise NotImplementedError

    @property
    def method(self) -> RESTMethod:
        """
        Returns the endpoint associated with the request.
        """
        raise NotImplementedError

    def params(self) -> Dict[str, Any]:
        """
        Returns the request parameters as a dictionary.
        """
        raise NotImplementedError

    def data(self) -> Dict[str, Any]:
        """
        Returns the request data as a dictionary.
        """
        raise NotImplementedError

    @staticmethod
    def is_auth_required() -> bool:
        """
        Returns the request data as a dictionary.
        """
        return True


@dataclass(frozen=True)
class _RequestGET(_RequestAbstract):
    """
    Base class for all Coinbase Advanced Trade API request dataclasses.
    """

    @property
    def method(self) -> RESTMethod:
        """
        Returns the endpoint associated with the request.
        """
        return RESTMethod.GET

    def params(self) -> Dict[str, Any]:
        """
        Returns the request parameters as a dictionary.
        """
        return self._apply_metadata()

    def data(self) -> Dict[str, Any]:
        """
        Returns the request data as a dictionary.
        """
        return {}


@dataclass(frozen=True)
class _RequestPOST(_RequestAbstract):
    """
    Base class for all Coinbase Advanced Trade API request dataclasses.
    """

    @property
    def method(self) -> RESTMethod:
        """
        Returns the endpoint associated with the request.
        """
        return RESTMethod.POST

    def params(self) -> Dict[str, Any]:
        """
        Returns the request parameters as a dictionary.
        """
        return {}

    def data(self) -> Dict[str, Any]:
        """
        Returns the request data as a dictionary.
        """
        return self._apply_metadata()


@dataclass(frozen=True)
class CoinbaseAdvancedTradeListAccountsRequest(_RequestGET):
    """
    Dataclass representing request parameters for ListAccountsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
    """
    limit: Optional[int] = None
    cursor: Optional[str] = None

    @property
    def endpoint(self) -> str:
        return "accounts"


@dataclass(frozen=True)
class CoinbaseAdvancedTradeGetAccountRequest(_RequestGET):
    """
    Dataclass representing request parameters for GetAccountEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccount
    """
    account_uuid: str = field(default=None, metadata={'required': True, 'path_param': True})

    @property
    def endpoint(self) -> str:
        return f"accounts/{self.account_uuid}"


@dataclass(frozen=True)
class CoinbaseAdvancedTradeCreateOrderRequest(_RequestPOST):
    """
    Dataclass representing request parameters for CreateOrderEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    """
    client_order_id: str = field(default=None, metadata={'required': True})
    product_id: str = field(default=None, metadata={'required': True})
    side: CoinbaseAdvancedTradeOrderSide = field(default=None)
    order_configuration: CoinbaseAdvancedTradeAPIOrderTypes = field(default=None)

    @property
    def endpoint(self) -> str:
        return "orders"


@dataclass(frozen=True)
class CoinbaseAdvancedTradeCancelOrdersRequest(_RequestPOST):
    """
    Dataclass representing request parameters for CancelOrdersEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders
    """
    order_ids: List[str] = field(default=None, metadata={'required': True})

    @property
    def endpoint(self) -> str:
        return "orders/batch_cancel"


@dataclass(frozen=True)
class CoinbaseAdvancedTradeListOrdersRequest(_RequestGET):
    """
    Dataclass representing request parameters for ListOrdersEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorders
    """
    product_id: Optional[str] = None
    order_status: Optional[List[str]] = None
    limit: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    user_native_currency: Optional[str] = 'USD'
    order_type: Optional[str] = None
    order_side: Optional[str] = None
    cursor: Optional[str] = None
    product_type: Optional[str] = None
    order_placement_source: Optional[str] = 'RETAIL_ADVANCED'

    @property
    def endpoint(self) -> str:
        return "orders/historical/batch"


@dataclass(frozen=True)
class CoinbaseAdvancedTradeListFillsRequest(_RequestGET):
    """
    Dataclass representing request parameters for ListFillsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getfills
    """
    order_id: Optional[str] = None
    product_id: Optional[str] = None
    start_sequence_timestamp: Optional[datetime] = None
    end_sequence_timestamp: Optional[datetime] = None
    limit: Optional[int] = None
    cursor: Optional[str] = None

    @property
    def endpoint(self) -> str:
        return "orders/historical/fills"


@dataclass(frozen=True)
class CoinbaseAdvancedTradeGetOrderRequest(_RequestGET):
    """
    Dataclass representing request parameters for GetOrderEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorder
    """
    order_id: str = field(default=None, metadata={'required': True, 'path_param': True})

    # Deprecated
    client_order_id: Optional[str] = None
    user_native_currency: Optional[str] = None

    @property
    def endpoint(self) -> str:
        return f"orders/historical/{self.order_id}"


@dataclass(frozen=True)
class CoinbaseAdvancedTradeListProductsRequest(_RequestGET):
    """
    Dataclass representing request parameters for ListProductsEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproducts
    """
    limit: Optional[int] = None
    offset: Optional[int] = None
    product_type: Optional[str] = None

    @property
    def endpoint(self) -> str:
        return "products"


@dataclass(frozen=True)
class CoinbaseAdvancedTradeGetProductRequest(_RequestGET):
    """
    Dataclass representing request parameters for GetProductEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproduct
    """
    product_id: str = field(default=None, metadata={'required': True, 'path_param': True})

    @property
    def endpoint(self) -> str:
        return f"products/{self.product_id}"


@dataclass(frozen=True)
class CoinbaseAdvancedTradeGetProductCandlesRequest(_RequestGET):
    """
    Dataclass representing request parameters for GetProductCandlesEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getcandles
    """
    product_id: str = field(default=None, metadata={'required': True, 'path_param': True})
    start: datetime = field(default=None, metadata={'required': True, 'isoformat': True})
    end: datetime = field(default=None, metadata={'required': True, 'isoformat': True})
    granularity: str = field(default=None, metadata={'required': True})

    @property
    def endpoint(self) -> str:
        return f"products/{self.product_id}/candles"

    def params(self) -> Dict[str, Any]:
        """
        Returns the request parameters as a dictionary.
        """
        return {
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
            'granularity': self.granularity
        }


@dataclass(frozen=True)
class CoinbaseAdvancedTradeGetMarketTradesRequest(_RequestGET):
    """
    Dataclass representing request parameters for GetMarketTradesEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getmarkettrades
    """
    product_id: str = field(default=None, metadata={'required': True, 'path_param': True})
    limit: int = field(default=None, metadata={'required': True})

    @property
    def endpoint(self) -> str:
        return f"products/{self.product_id}/ticker"  # TODO: Check if this is correct


@dataclass(frozen=True)
class CoinbaseAdvancedTradeGetTransactionSummaryRequest(_RequestGET):
    """
    Dataclass representing request parameters for TransactionSummaryEndpoint.

    This is required for the test. It verifies that the request parameters are
    consistent with the Coinbase Advanced Trade API documentation.
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gettransactionsummary
    """
    start_date: datetime = field(default=None, metadata={'isoformat': True})
    end_date: datetime = field(default=None, metadata={'isoformat': True})
    user_native_currency: str = field(default=None,)
    product_type: str = field(default=None,)

    @property
    def endpoint(self) -> str:
        return "transaction_summary"

    def params(self) -> Dict[str, Any]:
        """
        Returns the request parameters as a dictionary.
        """
        return {
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'user_native_currency': self.user_native_currency,
            'product_type': self.product_type
        }
