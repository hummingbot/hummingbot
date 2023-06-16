from bidict import bidict

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_enums import (
    CoinbaseAdvancedTradeWSSOrderStatus,
)
from hummingbot.core.data_type.in_flight_order import OrderState

COINBASE_ADVANCED_TRADE_WSS_ORDER_STATE_MAPPING = bidict({
    CoinbaseAdvancedTradeWSSOrderStatus.PENDING: OrderState.PENDING_CREATE,
    CoinbaseAdvancedTradeWSSOrderStatus.OPEN: OrderState.OPEN,
    CoinbaseAdvancedTradeWSSOrderStatus.FILLED: OrderState.FILLED,
    CoinbaseAdvancedTradeWSSOrderStatus.CANCELLED: OrderState.CANCELED,
    CoinbaseAdvancedTradeWSSOrderStatus.FAILED: OrderState.FAILED
})
