from enum import Enum


class CoinbaseAdvancedTradeOrderSide(Enum):
    UNKNOWN_ORDER_SIDE = "UNKNOWN_ORDER_SIDE"
    BUY = "BUY"
    SELL = "SELL"


class CoinbaseAdvancedTradeStopDirection(Enum):
    UNKNOWN_STOP_DIRECTION = "UNKNOWN_STOP_DIRECTION"
    STOP_DIRECTION_STOP_UP = "STOP_DIRECTION_STOP_UP"
    STOP_DIRECTION_STOP_DOWN = "STOP_DIRECTION_STOP_DOWN"
