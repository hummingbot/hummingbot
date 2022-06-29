from decimal import Decimal
from typing import Optional

from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import OrderType, TradeType


class EVMInFlightOrder(GatewayInFlightOrder):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 creation_timestamp: float,
                 gas_price: Decimal,
                 initial_state: str = "PENDING_CREATE"):
        super().__init__(
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            creation_timestamp,
            initial_state,
        )
        self.trade_id_set = set()
        self._gas_price = gas_price
        self.nonce = 0
        self._cancel_tx_hash: Optional[str] = None

    @property
    def gas_price(self) -> Decimal:
        return self._gas_price

    @gas_price.setter
    def gas_price(self, gas_price: Decimal):
        self._gas_price = gas_price
