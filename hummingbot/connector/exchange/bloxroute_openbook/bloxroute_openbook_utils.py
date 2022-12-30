
import bxsolana_trader_proto.api as api

from hummingbot.core.data_type.common import OrderType, TradeType


def TradeTypeToSide(type: TradeType) -> api.Side:
    if type.value == type.BUY:
        return api.Side.S_BID
    elif type.value == type.SELL:
        return api.Side.S_ASK
    else:
        return api.Side.S_UNKNOWN

def OrderTypeToBlxrOrderType(orderType: OrderType) -> api.OrderType:
    if orderType.value == orderType.MARKET:
        return api.OrderType.OT_MARKET
    elif orderType.value == orderType.LIMIT:
        return api.OrderType.OT_LIMIT
    else:
        raise Exception(f"unknown order type ${orderType.value}") # TODO need unknown value
