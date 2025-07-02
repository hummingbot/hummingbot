"""
Order and position tracking models for Gateway connectors.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

from hummingbot.core.data_type.common import PositionAction
from hummingbot.core.data_type.in_flight_order import InFlightOrder


@dataclass
class GatewayInFlightOrder(InFlightOrder):
    """
    Extended InFlightOrder for Gateway connectors.
    Adds Gateway-specific fields like compute units and priority fees.
    """
    compute_units: Optional[int] = None
    priority_fee_per_cu: Optional[int] = None
    connector_name: Optional[str] = None
    method: Optional[str] = None

    def to_gateway_params(self) -> Dict[str, Any]:
        """Convert order to Gateway API parameters."""
        params = {
            "orderId": self.client_order_id,
            "address": self.exchange_order_id,  # Wallet address
            "baseToken": self.base_asset,
            "quoteToken": self.quote_asset,
            "amount": float(self.amount),
            "side": self.trade_type.name,
        }

        if self.price:
            params["limitPrice"] = float(self.price)

        return params


@dataclass
class GatewayInFlightPosition:
    """
    In-flight liquidity position for AMM/CLMM.
    """
    client_position_id: str
    exchange_position_id: Optional[str] = None
    trading_pair: str = ""
    position_action: PositionAction = PositionAction.OPEN
    base_asset: str = ""
    quote_asset: str = ""
    base_amount: Decimal = Decimal("0")
    quote_amount: Decimal = Decimal("0")
    liquidity: Optional[Decimal] = None
    fee_tier: Optional[Decimal] = None
    tick_lower: Optional[int] = None
    tick_upper: Optional[int] = None
    pool_address: Optional[str] = None
    creation_timestamp: float = 0
    last_update_timestamp: float = 0
    tx_hash: Optional[str] = None

    def to_gateway_params(self) -> Dict[str, Any]:
        """Convert position to Gateway API parameters."""
        params = {
            "positionId": self.client_position_id,
            "poolAddress": self.pool_address,
            "baseToken": self.base_asset,
            "quoteToken": self.quote_asset,
        }

        if self.position_action == PositionAction.OPEN:
            params.update({
                "baseAmount": float(self.base_amount),
                "quoteAmount": float(self.quote_amount),
            })
            if self.tick_lower is not None:
                params["tickLower"] = self.tick_lower
            if self.tick_upper is not None:
                params["tickUpper"] = self.tick_upper
            if self.fee_tier is not None:
                params["feeTier"] = float(self.fee_tier)

        return params
