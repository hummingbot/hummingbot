from dataclasses import asdict, dataclass, field, fields
from enum import Enum, auto
from functools import wraps
from typing import Any, Callable, Dict, Optional, Set, Type, Union

from hummingbot.core.data_type.common import OrderType


def ignore_dataclass_extra_kwargs(cls: Type) -> Type:
    """
    A decorator that modifies the given class so that any extra keyword arguments passed to the constructor are ignored
    instead of causing a TypeError. This is achieved by wrapping the original __init__ method of the class with a new
    method that filters out any unrecognized keyword arguments.

    :param Type cls: The class to be modified.
    :return: The modified class.
    :rtype: Type
    """

    if not hasattr(cls, '__dataclass_fields__'):
        raise TypeError("The ignore_dataclass_extra_kwargs decorator "
                        "must be applied before the dataclasses.dataclass decorator")

    original_init: Callable[..., None] = cls.__init__  # type: ignore

    @wraps(original_init)
    def wrapped_init(self: Any, *args: Any, **kwargs: Any) -> None:
        """
        The wrapped __init__ method that filters out any unrecognized keyword arguments.

        :param Any self: The instance being initialized.
        :param Any args: The positional arguments passed to the constructor.
        :param Any kwargs: The keyword arguments passed to the constructor.
        """
        accepted_args: Set[str] = set([f.name for f in fields(self)])
        filtered_kwargs: Dict[str, Any] = {k: v for k, v in kwargs.items() if k in accepted_args}
        for key, value in filtered_kwargs.items():
            object.__setattr__(self, key, value)
        original_init(self, *args, **filtered_kwargs)

    cls.__init__ = wrapped_init
    return cls


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class _LimitBase:
    base_size: str = field(init=True, repr=True)
    limit_price: str = field(init=True, repr=True)


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class _MakerBase:
    post_only: bool = field(init=True, repr=True, default=True)


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class _TakerBase:
    post_only: bool = field(init=True, repr=True, default=False)


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class _GTDBase:
    end_time: str = field(init=True, repr=True)


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class _StopBase:
    stop_price: str = field(init=True, repr=True)
    stop_direction: str = field(init=True, repr=True)


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class MarketMarketIOC:
    quote_size: str = field(init=True, repr=True)
    base_size: str = field(init=True, repr=True)


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class LimitGTC(_TakerBase, _LimitBase):
    pass


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class LimitMakerGTC(_MakerBase, _LimitBase):
    pass


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class LimitGTD(_TakerBase, _LimitBase, _GTDBase):
    pass


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class LimitMakerGTD(_MakerBase, _LimitBase, _GTDBase):
    pass


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class StopLimitGTC(_LimitBase, _StopBase):
    pass


@ignore_dataclass_extra_kwargs
@dataclass(frozen=True)
class StopLimitGTD(_LimitBase, _StopBase, _GTDBase):
    pass


@dataclass(frozen=True)
class Order:
    client_order_id: str
    product_id: str
    side: str
    order_configuration: Union[
        MarketMarketIOC,
        LimitGTC,
        LimitMakerGTC,
        LimitGTD,
        LimitMakerGTD,
        StopLimitGTC,
        StopLimitGTD] = field(init=True, repr=True)


@dataclass(frozen=True)
class CoinbaseAdvancedTradeAPIOrderTypes:
    market_market_ioc: Optional[MarketMarketIOC] = None
    limit_limit_gtc: Optional[LimitGTC] = None
    limit_limit_gtd: Optional[LimitGTD] = None
    stop_limit_stop_limit_gtc: Optional[StopLimitGTC] = None
    stop_limit_stop_limit_gtd: Optional[StopLimitGTD] = None

    order_type: Optional[Union[
        MarketMarketIOC,
        LimitGTC,
        LimitGTD,
        StopLimitGTC,
        StopLimitGTD]] = field(init=False)

    def __post_init__(self):
        for field_name, value in self.__dict__.items():
            if value is not None:
                self.__dict__["order_type"] = value
                break

    def asdict(self):
        return {k: v for k, v in asdict(self).items() if k != "order_type" and v is not None}


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


class _CoinbaseAdvancedTradeOrderType(Enum):
    pass


@create_coinbase_advanced_trade_order_type_members
class CoinbaseAdvancedTradeOrderType(_CoinbaseAdvancedTradeOrderType):
    pass


coinbase_advanced_trade_order_type_mapping = {
    CoinbaseAdvancedTradeOrderType.MARKET: MarketMarketIOC,  # type: ignore # Dynamic member assignment
    CoinbaseAdvancedTradeOrderType.LIMIT: LimitGTC,  # type: ignore # Dynamic member assignment
    CoinbaseAdvancedTradeOrderType.LIMIT_MAKER: LimitMakerGTC,  # type: ignore # Dynamic member assignment
    CoinbaseAdvancedTradeOrderType.MARKET_IOC: MarketMarketIOC,  # type: ignore # Dynamic member assignment
    CoinbaseAdvancedTradeOrderType.LIMIT_GTC: LimitGTC,  # type: ignore # Dynamic member assignment
    CoinbaseAdvancedTradeOrderType.LIMIT_MAKER_GTC: LimitMakerGTC,  # type: ignore # Dynamic member assignment
    CoinbaseAdvancedTradeOrderType.LIMIT_GTD: LimitGTD,  # type: ignore # Dynamic member assignment
    CoinbaseAdvancedTradeOrderType.LIMIT_MAKER_GTD: LimitMakerGTD,  # type: ignore # Dynamic member assignment
    CoinbaseAdvancedTradeOrderType.STOP_LIMIT_GTC: StopLimitGTC,  # type: ignore # Dynamic member assignment
    CoinbaseAdvancedTradeOrderType.STOP_LIMIT_GTD: StopLimitGTD,  # type: ignore # Dynamic member assignment
}
