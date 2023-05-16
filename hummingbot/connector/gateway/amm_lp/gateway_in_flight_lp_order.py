from decimal import Decimal
from typing import Any, Dict, Optional

from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import LPType, OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

s_decimal_0 = Decimal("0")


class GatewayInFlightLPOrder(GatewayInFlightOrder):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 lp_type: LPType,
                 lower_price: Decimal,
                 upper_price: Decimal,
                 amount_0: Decimal,
                 amount_1: Decimal,
                 token_id: Optional[int],
                 creation_timestamp: float,
                 gas_price: Decimal,
                 initial_state: OrderState = OrderState.PENDING_CREATE):
        super().__init__(
            client_order_id=client_order_id,
            trading_pair=trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=TradeType.RANGE,
            creation_timestamp=creation_timestamp,
            price=s_decimal_0,
            amount=s_decimal_0,
            exchange_order_id=exchange_order_id,
            initial_state=initial_state,
        )
        self.lp_type = lp_type
        self.lower_price = lower_price
        self.upper_price = upper_price
        self.token_id = token_id
        self.amount_0 = amount_0
        self.amount_1 = amount_1
        self.adjusted_lower_price = s_decimal_0
        self.adjusted_upper_price = s_decimal_0
        self.unclaimed_fee_0 = s_decimal_0
        self.unclaimed_fee_1 = s_decimal_0
        self.fee_tier = ""
        self.fee_paid = s_decimal_0
        self.trade_id_set = set()
        self._gas_price = gas_price
        self.nonce = 0
        self._cancel_tx_hash: Optional[str] = None

    @property
    def is_done(self) -> bool:
        return self.current_state in {OrderState.CANCELED, OrderState.COMPLETED, OrderState.FAILED, OrderState.REJECTED, OrderState.EXPIRED}

    @property
    def is_nft(self) -> bool:
        return self.current_state in {OrderState.CREATED, OrderState.OPEN} and self.lp_type == LPType.ADD

    @property
    def last_state(self) -> OrderState:
        return self.current_state

    def to_json(self) -> Dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "trading_pair": self.trading_pair,
            "lp_type": self.lp_type.name,
            "lower_price": str(self.lower_price),
            "upper_price": str(self.upper_price),
            "amount_0": str(self.amount_0),
            "amount_1": str(self.amount_1),
            "token_id": self.token_id,
            "adjusted_lower_price": str(self.adjusted_lower_price),
            "adjusted_upper_price": str(self.adjusted_upper_price),
            "unclaimed_fee_0": str(self.unclaimed_fee_0),
            "unclaimed_fee_1": str(self.unclaimed_fee_1),
            "fee_tier": self.fee_tier,
            "fee_asset": self.fee_asset,
            "fee_paid": str(self.fee_paid),
            "creation_timestamp": self.creation_timestamp,
            "last_state": str(self.last_state.value),
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "GatewayInFlightLPOrder":
        retval = GatewayInFlightLPOrder(
            client_order_id=data["client_order_id"],
            exchange_order_id=data["exchange_order_id"],
            trading_pair=data["trading_pair"],
            lp_type=getattr(LPType, data["lp_type"]),
            lower_price=Decimal(data["lower_price"]),
            upper_price=Decimal(data["upper_price"]),
            amount_0=Decimal(data["amount_0"]),
            amount_1=Decimal(data["amount_1"]),
            token_id=data["token_id"],
            creation_timestamp=data["creation_timestamp"],
            gas_price=s_decimal_0,
            initial_state=OrderState(int(data["last_state"]))
        )
        retval.adjusted_lower_price = Decimal(data["adjusted_lower_price"])
        retval.adjusted_upper_price = Decimal(data["adjusted_upper_price"])
        retval.unclaimed_fee_0 = Decimal(data["unclaimed_fee_0"])
        retval.unclaimed_fee_1 = Decimal(data["unclaimed_fee_1"])
        retval.fee_tier = data["fee_tier"]
        retval.fee_asset = data["fee_asset"]
        retval.fee_paid = Decimal(data["fee_paid"])
        return retval

    def _creation_timestamp_from_order_id(self) -> int:
        timestamp = -1
        if len(self.client_order_id.split("-")) > 3:
            timestamp = float(self.client_order_id[-1])
        return timestamp
