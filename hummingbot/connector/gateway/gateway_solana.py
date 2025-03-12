from decimal import Decimal
from typing import Any, Dict, Optional

from hummingbot.connector.gateway.gateway_base import GatewayBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder


class GatewaySolana(GatewayBase):
    """
    Defines Solana-specific functions for interacting with DEX protocols via Gateway.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _get_transaction_receipt_from_details(self, tx_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction receipt from tx_details for Solana."""
        return tx_details.get("txData")

    def _is_transaction_successful(self, tx_status: int, tx_receipt: Optional[Dict[str, Any]]) -> bool:
        """Determine if a Solana transaction is successful."""
        return tx_status == 1 and tx_receipt is not None

    def _is_transaction_pending(self, tx_status: int) -> bool:
        """Determine if a Solana transaction is still pending."""
        return tx_status == 0  # fulfilled but not yet confirmed

    def _is_transaction_failed(self, tx_status: int, tx_receipt: Optional[Dict[str, Any]]) -> bool:
        """Determine if a Solana transaction has failed."""
        return tx_status == -1  # confirmed but failed

    def _calculate_transaction_fee(self, tracked_order: GatewayInFlightOrder, tx_receipt: Dict[str, Any]) -> Decimal:
        """Calculate the transaction fee for Solana."""
        return Decimal(tx_receipt["meta"]["fee"] / 1000000000)
