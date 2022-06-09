from async_timeout import timeout
from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.common import OrderType, TradeType


GET_GATEWAY_EX_ORDER_ID_TIMEOUT = 30  # seconds


class GatewayInFlightOrder(InFlightOrderBase):
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
    def is_done(self) -> bool:
        return self.last_state in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        retval = GatewayInFlightOrder(
            client_order_id=data["client_order_id"],
            exchange_order_id=data["exchange_order_id"],
            trading_pair=data["trading_pair"],
            order_type=getattr(OrderType, data["order_type"]),
            trade_type=getattr(TradeType, data["trade_type"]),
            price=Decimal(data["price"]),
            amount=Decimal(data["amount"]),
            initial_state=data["last_state"]
        )
        retval.executed_amount_base = Decimal(data["executed_amount_base"])
        retval.executed_amount_quote = Decimal(data["executed_amount_quote"])
        retval.fee_asset = data["fee_asset"]
        retval.fee_paid = Decimal(data["fee_paid"])
        return retval

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"REJECTED"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"CANCELED", "EXPIRED"}

    @property
    def is_cancelling(self) -> bool:
        return self.last_state == "CANCELING"

    @property
    def gas_price(self) -> Decimal:
        return self._gas_price

    @gas_price.setter
    def gas_price(self, gas_price: Decimal):
        self._gas_price = gas_price

    @property
    def cancel_tx_hash(self) -> Optional[str]:
        return self._cancel_tx_hash

    @cancel_tx_hash.setter
    def cancel_tx_hash(self, cancel_tx_hash):
        self._cancel_tx_hash = cancel_tx_hash

    async def get_exchange_order_id(self) -> Optional[str]:
        """
        Overridden from parent class because blockchain orders take more time than ones from CEX.
        """
        if self.exchange_order_id is None:
            async with timeout(GET_GATEWAY_EX_ORDER_ID_TIMEOUT):
                await self.exchange_order_id_update_event.wait()
        return self.exchange_order_id
