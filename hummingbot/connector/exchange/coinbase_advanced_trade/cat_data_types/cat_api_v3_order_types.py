import sys
from enum import Enum, auto
from typing import Optional, Type

from bidict import bidict
from pydantic import validator

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_enums import (
    CoinbaseAdvancedTradeStopDirection,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_collect_pydantic_class_annotations import (
    collect_pydantic_class_annotations,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_dict_mockable_from_json_mixin import (
    DictMethodMockableFromJsonDocMixin,
    DictMethodMockableFromJsonOneOfManyDocMixin,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_pydantic_for_json import (
    PydanticForJsonConfig,
)
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.utils.class_registry import ClassRegistry


class CoinbaseAdvancedOrderTypeError(Exception):
    pass


class CoinbaseAdvancedTradeOrderType(
    ClassRegistry,
    DictMethodMockableFromJsonDocMixin,
):
    pass


class _PydanticForJsonAllowExtra(PydanticForJsonConfig):
    class Config:
        extra = "ignore"

    @validator("*", pre=True, always=True)
    def allowed_field_names(cls, value, field):
        if field.name not in _coinbase_advanced_trade_order_types_annotations:
            raise ValueError(f'Unknown field: {field.name}')
        return value


def get_order_type_class_by_name(class_name: str) -> Type["CoinbaseAdvancedTradeOrderType"]:
    if c := CoinbaseAdvancedTradeOrderType.find_class_by_name(class_name):
        return c
    raise CoinbaseAdvancedOrderTypeError(f"No response class found for {class_name}")


class CoinbaseAdvancedTradeMarketIOCOrderType(_PydanticForJsonAllowExtra, CoinbaseAdvancedTradeOrderType):
    """
    Market IOC Order Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
      "quote_size": "10.00",
      "base_size": "0.001"
    }
    ```
    """
    quote_size: str
    base_size: str


class CoinbaseAdvancedTradeLimitGTCOrderType(_PydanticForJsonAllowExtra, CoinbaseAdvancedTradeOrderType):
    """
    Limit GTC Order Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
      "base_size": "0.001",
      "limit_price": "10000.00",
      "post_only": false
    }
    ```
    """
    base_size: str
    limit_price: str
    post_only: bool = False


class CoinbaseAdvancedTradeLimitMakerGTCOrderType(CoinbaseAdvancedTradeLimitGTCOrderType):
    """
    Limit Maker GTC Order Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
      "base_size": "0.001",
      "limit_price": "10000.00",
      "post_only": true
    }
    ```
    """
    post_only: bool = True


class CoinbaseAdvancedTradeLimitGTDOrderType(_PydanticForJsonAllowExtra, CoinbaseAdvancedTradeOrderType):
    """
    Limit Good Till Date Order Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
      "base_size": "0.001",
      "limit_price": "10000.00",
      "end_time": "2021-05-31T09:59:59Z",
      "post_only": false
    }
    ```
    """
    base_size: str
    limit_price: str
    post_only: bool = False
    end_time: str


class CoinbaseAdvancedTradeLimitMakerGTDOrderType(CoinbaseAdvancedTradeLimitGTDOrderType):
    """
    Limit Maker Good Till Date Order Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
      "base_size": "0.001",
      "limit_price": "10000.00",
      "end_time": "2021-05-31T09:59:59Z",
      "post_only": true
    }
    ```
    """
    post_only: bool = True


class CoinbaseAdvancedTradeStopLimitGTCOrderType(_PydanticForJsonAllowExtra, CoinbaseAdvancedTradeOrderType):
    """
    Stop Limit GTC Order Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
      "base_size": "0.001",
      "limit_price": "10000.00",
      "stop_price": "20000.00",
      "stop_direction": "UNKNOWN_STOP_DIRECTION"
    }
    ```
    """
    base_size: str
    limit_price: str
    stop_price: str
    stop_direction: CoinbaseAdvancedTradeStopDirection


class CoinbaseAdvancedTradeStopLimitGTDOrderType(_PydanticForJsonAllowExtra, CoinbaseAdvancedTradeOrderType):
    """
    Stop Limit Good Till Date Order Type
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
      "base_size": "0.001",
      "limit_price": "10000.00",
      "stop_price": "20000.00",
      "end_time": "2021-05-31T09:59:59Z",
      "stop_direction": "UNKNOWN_STOP_DIRECTION"
    }
    ```
    """
    base_size: str
    limit_price: str
    stop_price: str
    stop_direction: CoinbaseAdvancedTradeStopDirection
    end_time: str


COINBASE_ADVANCED_TRADE_ORDER_TYPE_REGISTRY = {
    OrderType.MARKET: {
        "class": CoinbaseAdvancedTradeMarketIOCOrderType,
        "post_only": None,
        "field": "market_market_ioc"
    },
    OrderType.LIMIT: {
        "class": CoinbaseAdvancedTradeLimitGTCOrderType,
        "post_only": False,
        "field": "limit_limit_gtc"
    },
    OrderType.LIMIT_MAKER: {
        "class": CoinbaseAdvancedTradeLimitGTCOrderType,
        "post_only": True,
        "field": "limit_limit_gtc"
    },
    # ... and possibly more ...
}


class CoinbaseAdvancedTradeAPIOrderConfiguration(PydanticForJsonConfig, DictMethodMockableFromJsonOneOfManyDocMixin):
    """
    Coinbase Advanced Trade API Order Configuration
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
    ```json
    {
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
    ```
    """
    market_market_ioc: Optional[CoinbaseAdvancedTradeMarketIOCOrderType] = None
    limit_limit_gtc: Optional[CoinbaseAdvancedTradeLimitGTCOrderType] = None
    limit_limit_gtd: Optional[CoinbaseAdvancedTradeLimitGTDOrderType] = None
    stop_limit_stop_limit_gtc: Optional[CoinbaseAdvancedTradeStopLimitGTCOrderType] = None
    stop_limit_stop_limit_gtd: Optional[CoinbaseAdvancedTradeStopLimitGTDOrderType] = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)

        # check if at least one field is provided
        if not any([self.market_market_ioc,
                    self.limit_limit_gtc,
                    self.limit_limit_gtd,
                    self.stop_limit_stop_limit_gtc,
                    self.stop_limit_stop_limit_gtd]):
            raise ValueError("At least one of the optional fields must be provided")

    @property
    def order_type(self) -> CoinbaseAdvancedTradeOrderType:
        for f in self.__annotations__:
            if (order_type := getattr(self, f, None)) is not None:
                return order_type

    @classmethod
    def create(cls, order_type: OrderType, **data):
        try:
            order_type_info = COINBASE_ADVANCED_TRADE_ORDER_TYPE_REGISTRY[order_type]
        except KeyError:
            raise CoinbaseAdvancedOrderTypeError(f'Unsupported order type: {order_type}.')

        # Create an instance of the OrderType class.
        order_instance = order_type_info["class"](**data)
        # Return an instance of the configuration class with the proper field set.
        return cls(**{order_type_info["field"]: order_instance})


def create_coinbase_advanced_trade_order_type_members(cls: Type[Enum]) -> Type[Enum]:
    """
    Create the members of the Coinbase Advanced Trade order type enum class by
    updating the mapping of the given order type enum class with the members
    from the original OrderType enum.

    :param cls: The order type enum class to be updated.
    :type cls: Type[Enum]
    :return: The updated order type enum class.
    :rtype: Type[Enum]
    """
    # Update the member map of the given class with the members from the original OrderType
    cls._member_map_.update(OrderType._member_map_)

    def match_member_to_order_type(name: str, corresponding_name: str) -> None:
        """
        Match the member with the given name to the member with the given corresponding name
        from the original OrderType enum. If the corresponding name is not in the original
        OrderType enum, assign a new auto-generated value to the member.

        :param name: The name of the member to be matched.
        :type name: str
        :param corresponding_name: The name of the corresponding member from the original OrderType enum.
        :type corresponding_name: str
        """
        if corresponding_name in OrderType.__members__:
            if name not in OrderType.__members__:
                cls._member_map_[name] = OrderType[corresponding_name]
        else:
            cls._member_map_[name] = auto()

    # Match the given order type enum members with the corresponding members from the original OrderType enum
    match_member_to_order_type("MARKET_IOC", "MARKET")
    match_member_to_order_type("LIMIT_GTC", "LIMIT")
    match_member_to_order_type("LIMIT_MAKER_GTC", "LIMIT_MAKER")

    # Match the remaining order type enum members with their corresponding names in the original OrderType enum
    for name in ("LIMIT_GTD",
                 "STOP_LIMIT_GTC",
                 "STOP_LIMIT_GTD",
                 "LIMIT_MAKER_GTD"):
        match_member_to_order_type(name, name)

    return cls


class _OrderType(Enum):
    pass


@create_coinbase_advanced_trade_order_type_members
class CoinbaseAdvancedTradeOrderTypeEnum(_OrderType):
    pass


coinbase_advanced_trade_order_type_class_mapping = {
    # Dynamic member assignment, requires type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.MARKET: CoinbaseAdvancedTradeMarketIOCOrderType,  # type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.LIMIT: CoinbaseAdvancedTradeLimitGTCOrderType,  # type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.LIMIT_MAKER: CoinbaseAdvancedTradeLimitMakerGTCOrderType,  # type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.MARKET_IOC: CoinbaseAdvancedTradeMarketIOCOrderType,  # type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.LIMIT_GTC: CoinbaseAdvancedTradeLimitGTCOrderType,  # type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.LIMIT_MAKER_GTC: CoinbaseAdvancedTradeLimitMakerGTCOrderType,  # type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.LIMIT_GTD: CoinbaseAdvancedTradeLimitGTDOrderType,  # type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.LIMIT_MAKER_GTD: CoinbaseAdvancedTradeLimitMakerGTDOrderType,  # type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.STOP_LIMIT_GTC: CoinbaseAdvancedTradeStopLimitGTCOrderType,  # type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.STOP_LIMIT_GTD: CoinbaseAdvancedTradeStopLimitGTDOrderType,  # type: ignore
}

COINBASE_ADVANCED_TRADE_ORDER_TYPE_ENUM_MAPPING = bidict({
    CoinbaseAdvancedTradeOrderTypeEnum.MARKET_IOC: OrderType.MARKET,  # type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.LIMIT_GTC: OrderType.LIMIT,  # type: ignore
    CoinbaseAdvancedTradeOrderTypeEnum.LIMIT_MAKER: OrderType.LIMIT_MAKER  # type: ignore
})

# Collect Pydantic class annotations from the current module
_coinbase_advanced_trade_order_types_annotations = collect_pydantic_class_annotations(sys.modules[__name__],
                                                                                      CoinbaseAdvancedTradeOrderType)
