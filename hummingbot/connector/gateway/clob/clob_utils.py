from typing import List

from hummingbot.connector.gateway.clob.clob_types import OrderSide, OrderType
from hummingbot.core.event.events import OrderType as HummingbotOrderType, TradeType as HummingbotOrderSide


def convert_trading_pair(hummingbot_trading_pair: str) -> str:
    return '/'.join(hummingbot_trading_pair.split('-'))


def convert_trading_pairs(hummingbot_trading_pairs: List[str]) -> List[str]:
    return [convert_trading_pair(trading_pair) for trading_pair in hummingbot_trading_pairs]


def convert_order_side(hummingbot_order_side: HummingbotOrderSide) -> OrderSide:
    if hummingbot_order_side == HummingbotOrderSide.BUY:
        return OrderSide.BUY
    elif hummingbot_order_side == HummingbotOrderSide.SELL:
        return OrderSide.SELL
    else:
        raise ValueError(f'Unrecognized order side "{hummingbot_order_side}".')


def convert_order_type(hummingbot_order_type: HummingbotOrderType) -> OrderType:
    if hummingbot_order_type == HummingbotOrderType.LIMIT:
        return OrderType.LIMIT
    elif hummingbot_order_type == HummingbotOrderType.LIMIT_MAKER:
        return OrderType.POST_ONLY
    elif hummingbot_order_type == HummingbotOrderType.MARKET:
        return OrderType.IOC
    else:
        raise ValueError(f'Order type "{hummingbot_order_type}" incompatible with CLOB connector.')
