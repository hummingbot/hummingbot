from typing import List

from hummingbot.connector.gateway.clob.clob_types import OrderSide, OrderType
from hummingbot.core.event.events import OrderType as HummingbotOrderType, TradeType as HummingbotOrderSide


def convert_trading_pair(hummingbot_trading_pair: str) -> str:
    return '/'.join(hummingbot_trading_pair.split('-'))


def convert_trading_pairs(hummingbot_trading_pairs: List[str]) -> List[str]:
    return [convert_trading_pair(trading_pair) for trading_pair in hummingbot_trading_pairs]


def convert_order_side(hummingbot_order_side: HummingbotOrderSide) -> OrderSide:
    raise NotImplementedError


def convert_order_type(hummingbot_order_type: HummingbotOrderType) -> OrderType:
    raise NotImplementedError
