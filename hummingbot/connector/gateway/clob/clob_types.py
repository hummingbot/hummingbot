from enum import Enum

from hummingbot.core.data_type.common import OrderType as HummingBotOrderType, TradeType as HummingBotOrderSide


class OrderStatus(Enum):
    OPEN = 'OPEN',
    CANCELED = 'CANCELED',
    FILLED = 'FILLED',
    CREATION_PENDING = 'CREATION_PENDING',
    CANCELATION_PENDING = 'CANCELATION_PENDING',
    UNKNOWN = 'UNKNOWN'

    @staticmethod
    def from_hummingbot(target: str):
        if target == 'OPEN':
            return OrderStatus.OPEN
        elif target == 'CANCELED':
            return OrderStatus.CANCELED
        else:
            raise ValueError(f"Unknown order status: {target}")

    @staticmethod
    def to_hummingbot(self):
        if self == OrderStatus.OPEN:
            return 'OPEN'
        elif self == OrderStatus.CANCELED:
            return 'CANCELED'
        else:
            raise ValueError(f"Unknown order status: {self}")


class OrderType(Enum):
    LIMIT = 'LIMIT',
    IOC = 'IOC',  # Immediate or Cancel
    POST_ONLY = 'POST_ONLY',

    @staticmethod
    def from_hummingbot(target: HummingBotOrderType):
        if target == HummingBotOrderType.LIMIT:
            return OrderType.LIMIT
        else:
            raise ValueError(f'Unrecognized order type "{target}".')

    @staticmethod
    def to_hummingbot(self):
        if self == OrderType.LIMIT:
            return HummingBotOrderType.LIMIT
        else:
            raise ValueError(f'Unrecognized order type "{self}".')


class OrderSide(Enum):
    BUY = 'BUY',
    SELL = 'SELL',

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
