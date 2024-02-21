from enum import Enum

from hummingbot.core.data_type.common import OrderType as HummingBotOrderType, TradeType as HummingBotOrderSide
from hummingbot.core.data_type.in_flight_order import OrderState as HummingBotOrderStatus


class OrderStatus(Enum):
    OPEN = "OPEN",
    CANCELLED = "CANCELLED",
    PARTIALLY_FILLED = "PARTIALLY_FILLED",
    FILLED = "FILLED",
    CREATION_PENDING = "CREATION_PENDING",
    CANCELLATION_PENDING = "CANCELLATION_PENDING",
    UNKNOWN = "UNKNOWN"

    @staticmethod
    def from_name(name: str):
        if name == "OPEN":
            return OrderStatus.OPEN
        elif name == "CANCELLED":
            return OrderStatus.CANCELLED
        elif name == "PARTIALLY_FILLED":
            return OrderStatus.PARTIALLY_FILLED
        elif name == "FILLED":
            return OrderStatus.FILLED
        elif name == "CREATION_PENDING":
            return OrderStatus.CREATION_PENDING
        elif name == "CANCELLATION_PENDING":
            return OrderStatus.CANCELLATION_PENDING
        else:
            raise ValueError(f"Unknown order status: {name}")

    @staticmethod
    def from_hummingbot(target: HummingBotOrderStatus):
        if target == HummingBotOrderStatus.PENDING_CREATE:
            return OrderStatus.CREATION_PENDING
        elif target == HummingBotOrderStatus.OPEN:
            return OrderStatus.OPEN
        elif target == HummingBotOrderStatus.PENDING_CANCEL:
            return OrderStatus.CANCELLATION_PENDING
        elif target == HummingBotOrderStatus.CANCELED:
            return OrderStatus.CANCELLED
        elif target == HummingBotOrderStatus.PARTIALLY_FILLED:
            return OrderStatus.PARTIALLY_FILLED
        elif target == HummingBotOrderStatus.FILLED:
            return OrderStatus.FILLED
        else:
            raise ValueError(f"Unknown order status: {target}")

    @staticmethod
    def to_hummingbot(self):
        if self == OrderStatus.OPEN:
            return HummingBotOrderStatus.OPEN
        elif self == OrderStatus.CANCELLED:
            return HummingBotOrderStatus.CANCELED
        elif self == OrderStatus.PARTIALLY_FILLED:
            return HummingBotOrderStatus.PARTIALLY_FILLED
        elif self == OrderStatus.FILLED:
            return HummingBotOrderStatus.FILLED
        elif self == OrderStatus.CREATION_PENDING:
            return HummingBotOrderStatus.PENDING_CREATE
        elif self == OrderStatus.CANCELLATION_PENDING:
            return HummingBotOrderStatus.PENDING_CANCEL
        else:
            raise ValueError(f"Unknown order status: {self}")


class OrderType(Enum):
    MARKET = 'MARKET',
    LIMIT = 'LIMIT',

    @staticmethod
    def from_name(name: str):
        if name == "MARKET":
            return OrderType.MARKET
        elif name == "LIMIT":
            return OrderType.LIMIT
        else:
            raise ValueError(f"Unknown order type: {name}")

    @staticmethod
    def from_hummingbot(target: HummingBotOrderType):
        if target == HummingBotOrderType.LIMIT:
            return OrderType.LIMIT
        if target == HummingBotOrderType.MARKET:
            return OrderType.MARKET
        else:
            raise ValueError(f'Unrecognized order type "{target}".')

    @staticmethod
    def to_hummingbot(self):
        if self == OrderType.LIMIT:
            return HummingBotOrderType.LIMIT
        if self == OrderType.MARKET:
            return HummingBotOrderType.MARKET
        else:
            raise ValueError(f'Unrecognized order type "{self}".')


class OrderSide(Enum):
    BUY = 'BUY',
    SELL = 'SELL',

    @staticmethod
    def from_name(name: str):
        if name == "BUY":
            return OrderSide.BUY
        elif name == "SELL":
            return OrderSide.SELL
        else:
            raise ValueError(f"Unknown order side: {name}")

    @staticmethod
    def from_hummingbot(target: HummingBotOrderSide):
        if target == HummingBotOrderSide.BUY:
            return OrderSide.BUY
        elif target == HummingBotOrderSide.SELL:
            return OrderSide.SELL
        else:
            raise ValueError(f'Unrecognized order side "{target}".')

    def to_hummingbot(self):
        if self == OrderSide.BUY:
            return HummingBotOrderSide.BUY
        elif self == OrderSide.SELL:
            return HummingBotOrderSide.SELL
        else:
            raise ValueError(f'Unrecognized order side "{self}".')


class TickerSource(Enum):
    ORDER_BOOK_SAP = "orderBookSimpleAveragePrice",
    ORDER_BOOK_WAP = "orderBookWeightedAveragePrice",
    ORDER_BOOK_VWAP = "orderBookVolumeWeightedAveragePrice",
    LAST_FILLED_ORDER = "lastFilledOrder",
    NOMICS = "nomics",
