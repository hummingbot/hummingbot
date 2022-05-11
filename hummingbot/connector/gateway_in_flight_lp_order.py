from async_timeout import timeout
from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)

from hummingbot.connector.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import OrderType, TradeType, LPType    


class GatewayInFlightLPOrder(GatewayInFlightOrder):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 lp_type: LPType,
                 lower_price: Decimal,
                 upper_price: Decimal,
                 amount: Decimal,
                 token_id: Optional[int],
                 creation_timestamp: float,
                 gas_price: Decimal,
                 initial_state: str = "PENDING_CREATE"):
        super().__init__(
            client_order_id,
            exchange_order_id,
            trading_pair,
            OrderType.LIMIT_MAKER,
            TradeType.RANGE,
            s_decimal_0,
            amount,
            creation_timestamp,
            initial_state,
        )
        self.lp_type = lp_type
        self.lower_price = lower_price
        self.upper_price = upper_price
        self.token_id = token_id
        self.adjusted_lower_price = s_decimal_0
        self.adjusted_upper_price = s_decimal_0
        self.unclaimed_fee_0 = s_decimal_0
        self.unclaimed_fee_1 = s_decimal_0
        self.trade_id_set = set()
        self._gas_price = gas_price
        self.nonce = 0
        self._cancel_tx_hash: Optional[str] = None

    @property
    def is_done(self) -> bool:
        return self.last_state in {"CREATED", "COMPLETED", "CANCELED", "REJECTED", "EXPIRED"}

    @property
    def is_nft(self) -> bool:
        return self.last_state == "CREATED"

    def to_json(self) -> Dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "trading_pair": self.trading_pair,
            "order_type": self.order_type.name,
            "lower_price": str(self.lower_price),
            "upper_price": str(self.upper_price),
            "amount": str(self.amount),
            "token_id": self.token_id,
            "adjusted_lower_price": str(self.adjusted_lower_price),
            "adjusted_upper_price": str(self.adjusted_upper_price),
            "fee_asset": self.fee_asset,
            "fee_paid": str(self.fee_paid),
            "creation_timestamp": self.creation_timestamp,
            "last_state": self.last_state,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        retval = GatewayInFlightLPOrder(
            client_order_id=data["client_order_id"],
            exchange_order_id=data["exchange_order_id"],
            trading_pair=data["trading_pair"],
            order_type=getattr(OrderType, data["order_type"]),
            lower_price=Decimal(data["lower_price"]),
            upper_rice=Decimal(data["upper_price"]),
            amount=Decimal(data["amount"]),
            token_id=data["token_id"],
            initial_state=data["last_state"]
        )
        retval.adjusted_lower_price = data["adjusted_lower_price"]
        retval.adjusted_upper_price = data["adjusted_upper_price"]
        retval.fee_asset = data["fee_asset"]
        retval.fee_paid = Decimal(data["fee_paid"])
        return retval

