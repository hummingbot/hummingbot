from enum import Enum

from hummingbot.core.data_type.common import OrderType as HummingBotOrderType, TradeType as HummingBotOrderSide
from hummingbot.core.data_type.in_flight_order import OrderState as HummingBotOrderStatus


class OrderStatus(Enum):
    open = 'open',
    expired = 'expired',
    error = 'error',
    cancelled = 'cancelled',
    filled = 'filled',
    insufficient_funds = 'insufficient-funds',

    @staticmethod
    def from_name(name: str):
        if name == "open":
            return OrderStatus.open
        elif name == "cancelled":
            return OrderStatus.cancelled
        elif name == "expired":
            return OrderStatus.cancelled
        elif name == "insufficient-funds":
            return OrderStatus.cancelled
        elif name == "filled":
            return OrderStatus.filled
        elif name == "error":
            return OrderStatus.error
        else:
            raise ValueError(f"Unknown order status: {name}")

    @staticmethod
    def from_hummingbot(target: HummingBotOrderStatus):
        if target == HummingBotOrderStatus.PENDING_CREATE:
            return OrderStatus.open
        elif target == HummingBotOrderStatus.OPEN:
            return OrderStatus.open
        elif target == HummingBotOrderStatus.PENDING_CANCEL:
            return OrderStatus.open
        elif target == HummingBotOrderStatus.CANCELED:
            return OrderStatus.cancelled
        elif target == HummingBotOrderStatus.PARTIALLY_FILLED:
            return OrderStatus.filled
        elif target == HummingBotOrderStatus.FILLED:
            return OrderStatus.filled
        elif target == HummingBotOrderStatus.FAILED:
            return OrderStatus.error
        else:
            raise ValueError(f"Unknown order status: {target}")

    @staticmethod
    def to_hummingbot(self):
        if self == OrderStatus.open:
            return HummingBotOrderStatus.OPEN
        elif self == OrderStatus.cancelled:
            return HummingBotOrderStatus.CANCELED
        elif self == OrderStatus.expired:
            return HummingBotOrderStatus.CANCELED
        elif self == OrderStatus.filled:
            return HummingBotOrderStatus.FILLED
        elif self == OrderStatus.error:
            return HummingBotOrderStatus.FAILED
        elif self == OrderStatus.insufficient_funds:
            return HummingBotOrderStatus.FAILED
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
