"""
XRPL Fill Processor

Handles trade fill extraction and processing for the XRPL connector.
Provides pure utility functions for parsing transaction data and extracting
fill amounts from various XRPL data sources (balance changes, offer changes,
transaction TakerGets/TakerPays).
"""

# =============================================================================
# Imports
# =============================================================================
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from xrpl.utils import drops_to_xrp, ripple_time_to_posix

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, TradeUpdate
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.logger import HummingbotLogger

# =============================================================================
# Module Logger
# =============================================================================
_logger: Optional[HummingbotLogger] = None


def logger() -> HummingbotLogger:
    """Get module logger instance."""
    global _logger
    if _logger is None:
        _logger = HummingbotLogger(__name__)
    return _logger


# =============================================================================
# Constants
# =============================================================================

class OfferStatus:
    """XRPL offer status values from get_order_book_changes()."""
    FILLED = "filled"
    PARTIALLY_FILLED = "partially-filled"
    CREATED = "created"
    CANCELLED = "cancelled"


class FillSource(Enum):
    """Source of fill amount extraction."""
    BALANCE_CHANGES = "balance_changes"
    OFFER_CHANGE = "offer_change"
    TRANSACTION = "transaction"


# =============================================================================
# Result Types
# =============================================================================

@dataclass
class FillExtractionResult:
    """Result of attempting to extract fill amounts."""
    base_amount: Optional[Decimal]
    quote_amount: Optional[Decimal]
    source: FillSource

    @property
    def is_valid(self) -> bool:
        """Check if extraction produced valid fill amounts."""
        return (
            self.base_amount is not None and
            self.quote_amount is not None and
            self.base_amount > Decimal("0")
        )


# =============================================================================
# Pure Extraction Functions
# =============================================================================

def extract_transaction_data(data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Extract transaction and metadata from various XRPL data formats.

    Args:
        data: Raw transaction data in various formats (from user stream, account_tx, etc.)

    Returns:
        Tuple of (transaction dict, metadata dict). Transaction may be None if extraction fails.
    """
    if "result" in data:
        data_result = data.get("result", {})
        meta = data_result.get("meta", {})
        tx = data_result.get("tx_json") or data_result.get("transaction")
        if tx is not None:
            tx["hash"] = data_result.get("hash")
        else:
            tx = data_result
    else:
        meta = data.get("meta", {})
        tx = data.get("tx") or data.get("transaction") or data.get("tx_json") or {}
        if "hash" in data:
            tx["hash"] = data.get("hash")

    if not isinstance(tx, dict):
        return None, meta

    return tx, meta


def extract_fill_from_balance_changes(
    balance_changes: List[Dict[str, Any]],
    base_currency: str,
    quote_currency: str,
    tx_fee_xrp: Optional[Decimal] = None,
) -> FillExtractionResult:
    """
    Extract fill amounts from balance changes.

    Uses balance changes as the source of truth for filled amounts.
    Filters out XRP transaction fees from the calculation.

    Args:
        balance_changes: List of balance changes for our account
        base_currency: Base currency code
        quote_currency: Quote currency code
        tx_fee_xrp: Transaction fee in XRP (to filter out from balance changes)

    Returns:
        FillExtractionResult with base_amount and quote_amount (absolute values).
    """
    base_amount = None
    quote_amount = None

    for balance_change in balance_changes:
        changes = balance_change.get("balances", [])

        for change in changes:
            currency = change.get("currency")
            value = change.get("value")

            if currency is None or value is None:
                continue

            change_value = Decimal(value)

            # Filter out XRP fee changes (negative XRP that matches fee)
            if currency == "XRP" and tx_fee_xrp is not None:
                if abs(change_value + tx_fee_xrp) < Decimal("0.000001"):
                    continue

            if currency == base_currency:
                base_amount = abs(change_value)
            elif currency == quote_currency:
                quote_amount = abs(change_value)

    return FillExtractionResult(
        base_amount=base_amount,
        quote_amount=quote_amount,
        source=FillSource.BALANCE_CHANGES,
    )


def find_offer_change_for_order(
    offer_changes: List[Dict[str, Any]],
    order_sequence: int,
    include_created: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Find the offer change that matches an order's sequence number.

    This handles both:
    1. Our order being filled/partially-filled by external transactions
    2. Our order crossing existing offers when placed
    3. Our order being created on the book (when include_created=True)

    Args:
        offer_changes: List of offer changes for our account (from get_order_book_changes)
        order_sequence: The sequence number of our order
        include_created: If True, also return changes with status "created" (used for
            detecting partial fills on order creation where the remainder goes on the book)

    Returns:
        The matching offer change dict, or None if not found
    """
    logger().debug(
        f"[FIND_OFFER_DEBUG] Searching seq={order_sequence}, include_created={include_created}, "
        f"accounts={len(offer_changes)}"
    )
    for account_changes in offer_changes:
        changes = account_changes.get("offer_changes", [])
        for change in changes:
            seq = change.get("sequence")
            status = change.get("status")
            if seq == order_sequence:
                # Return if filled or partially-filled
                if status in [OfferStatus.FILLED, OfferStatus.PARTIALLY_FILLED]:
                    logger().debug(f"[FIND_OFFER_DEBUG] Found: seq={seq}, status={status}")
                    return change
                # Optionally return "created" status (for taker fill detection on order creation)
                if include_created and status in [OfferStatus.CREATED, OfferStatus.CANCELLED]:
                    logger().debug(f"[FIND_OFFER_DEBUG] Found (created): seq={seq}, status={status}")
                    return change
                logger().debug(f"[FIND_OFFER_DEBUG] Seq matched but status={status} rejected")
    logger().debug(f"[FIND_OFFER_DEBUG] No match for seq={order_sequence}")
    return None


def extract_fill_from_offer_change(
    offer_change: Dict[str, Any],
    base_currency: str,
    quote_currency: str,
) -> FillExtractionResult:
    """
    Extract fill amounts from an offer change delta.

    The offer change from xrpl-py's get_order_book_changes contains the delta
    (amount changed) in taker_gets and taker_pays fields with negative values.

    Args:
        offer_change: Single offer change from get_order_book_changes
        base_currency: Base currency code
        quote_currency: Quote currency code

    Returns:
        FillExtractionResult with base_amount and quote_amount (absolute values).
    """
    taker_gets = offer_change.get("taker_gets", {})
    taker_pays = offer_change.get("taker_pays", {})

    # The values in offer_change are deltas (negative = consumed)
    taker_gets_currency = taker_gets.get("currency")
    taker_pays_currency = taker_pays.get("currency")
    taker_gets_value = taker_gets.get("value", "0")
    taker_pays_value = taker_pays.get("value", "0")

    base_amount = None
    quote_amount = None

    # Match currencies to base/quote
    if taker_gets_currency == base_currency:
        base_amount = abs(Decimal(taker_gets_value))
        quote_amount = abs(Decimal(taker_pays_value))
    elif taker_pays_currency == base_currency:
        base_amount = abs(Decimal(taker_pays_value))
        quote_amount = abs(Decimal(taker_gets_value))

    return FillExtractionResult(
        base_amount=base_amount,
        quote_amount=quote_amount,
        source=FillSource.OFFER_CHANGE,
    )


def extract_fill_from_transaction(
    tx: Dict[str, Any],
    base_currency: str,
    quote_currency: str,
    trade_type: TradeType,
) -> FillExtractionResult:
    """
    Extract fill amounts from transaction's TakerGets/TakerPays (fallback).

    This is used as a fallback when balance changes are incomplete (e.g., for dust orders
    where the balance change is too small to be recorded on the ledger).

    For a successful OfferCreate transaction that was immediately fully consumed (never
    created an Offer on the ledger), the TakerGets/TakerPays fields represent the exact
    amounts that were traded.

    Args:
        tx: Transaction data containing TakerGets and TakerPays
        base_currency: Base currency code
        quote_currency: Quote currency code
        trade_type: Whether this is a BUY or SELL order

    Returns:
        FillExtractionResult with base_amount and quote_amount (absolute values).
    """
    taker_gets = tx.get("TakerGets")
    taker_pays = tx.get("TakerPays")

    if taker_gets is None or taker_pays is None:
        return FillExtractionResult(
            base_amount=None,
            quote_amount=None,
            source=FillSource.TRANSACTION,
        )

    # Parse TakerGets - can be XRP (string in drops) or token (dict)
    if isinstance(taker_gets, str):
        # XRP in drops
        taker_gets_currency = "XRP"
        taker_gets_value = Decimal(str(drops_to_xrp(taker_gets)))
    else:
        taker_gets_currency = taker_gets.get("currency")
        taker_gets_value = Decimal(taker_gets.get("value", "0"))

    # Parse TakerPays - can be XRP (string in drops) or token (dict)
    if isinstance(taker_pays, str):
        # XRP in drops
        taker_pays_currency = "XRP"
        taker_pays_value = Decimal(str(drops_to_xrp(taker_pays)))
    else:
        taker_pays_currency = taker_pays.get("currency")
        taker_pays_value = Decimal(taker_pays.get("value", "0"))

    # In XRPL OfferCreate:
    # - TakerGets: What the offer creator is selling (what a taker would get)
    # - TakerPays: What the offer creator wants to receive (what a taker would pay)
    #
    # For a SELL order: We are selling base_currency, receiving quote_currency
    #   -> TakerGets should be base_currency, TakerPays should be quote_currency
    # For a BUY order: We are buying base_currency, paying quote_currency
    #   -> TakerGets should be quote_currency, TakerPays should be base_currency

    base_amount = None
    quote_amount = None

    if trade_type == TradeType.SELL:
        # Selling base, receiving quote
        if taker_gets_currency == base_currency and taker_pays_currency == quote_currency:
            base_amount = abs(taker_gets_value)
            quote_amount = abs(taker_pays_value)
    else:
        # BUY: Buying base, paying quote
        if taker_pays_currency == base_currency and taker_gets_currency == quote_currency:
            base_amount = abs(taker_pays_value)
            quote_amount = abs(taker_gets_value)

    return FillExtractionResult(
        base_amount=base_amount,
        quote_amount=quote_amount,
        source=FillSource.TRANSACTION,
    )


def create_trade_update(
    order: InFlightOrder,
    tx_hash: str,
    tx_date: int,
    fill_result: FillExtractionResult,
    fee: TradeFeeBase,
    offer_sequence: Optional[int] = None,
) -> TradeUpdate:
    """
    Create a TradeUpdate from extracted fill data.

    Args:
        order: The order being filled
        tx_hash: Transaction hash
        tx_date: Transaction date (ripple time)
        fill_result: Result from fill extraction (must be valid)
        fee: Trade fee
        offer_sequence: Optional sequence for unique trade ID when multiple fills

    Returns:
        TradeUpdate object

    Raises:
        ValueError: If fill_result is not valid
    """
    if not fill_result.is_valid:
        raise ValueError(f"Cannot create TradeUpdate from invalid fill result: {fill_result}")

    base_amount = fill_result.base_amount
    quote_amount = fill_result.quote_amount

    # Type narrowing: is_valid guarantees these are not None
    assert base_amount is not None
    assert quote_amount is not None

    # Create unique trade ID - append sequence if this is a maker fill
    trade_id = tx_hash
    if offer_sequence is not None:
        trade_id = f"{tx_hash}_{offer_sequence}"

    fill_price = quote_amount / base_amount if base_amount > 0 else Decimal("0")

    return TradeUpdate(
        trade_id=trade_id,
        client_order_id=order.client_order_id,
        exchange_order_id=str(order.exchange_order_id),
        trading_pair=order.trading_pair,
        fee=fee,
        fill_base_amount=base_amount,
        fill_quote_amount=quote_amount,
        fill_price=fill_price,
        fill_timestamp=ripple_time_to_posix(tx_date),
    )


# =============================================================================
# Legacy Compatibility Functions
# =============================================================================
# These functions return tuples instead of FillExtractionResult for backward
# compatibility with existing code during the transition period.

def extract_fill_amounts_from_balance_changes(
    balance_changes: List[Dict[str, Any]],
    base_currency: str,
    quote_currency: str,
    tx_fee_xrp: Optional[Decimal] = None,
) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """
    Legacy wrapper that returns tuple instead of FillExtractionResult.

    Args:
        balance_changes: List of balance changes for our account
        base_currency: Base currency code
        quote_currency: Quote currency code
        tx_fee_xrp: Transaction fee in XRP (to filter out from balance changes)

    Returns:
        Tuple of (base_amount, quote_amount). Values are absolute.
    """
    result = extract_fill_from_balance_changes(
        balance_changes, base_currency, quote_currency, tx_fee_xrp
    )
    return result.base_amount, result.quote_amount


def extract_fill_amounts_from_offer_change(
    offer_change: Dict[str, Any],
    base_currency: str,
    quote_currency: str,
) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """
    Legacy wrapper that returns tuple instead of FillExtractionResult.

    Args:
        offer_change: Single offer change from get_order_book_changes
        base_currency: Base currency code
        quote_currency: Quote currency code

    Returns:
        Tuple of (base_amount, quote_amount). Values are absolute.
    """
    result = extract_fill_from_offer_change(offer_change, base_currency, quote_currency)
    return result.base_amount, result.quote_amount


def extract_fill_amounts_from_transaction(
    tx: Dict[str, Any],
    base_currency: str,
    quote_currency: str,
    trade_type: TradeType,
) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """
    Legacy wrapper that returns tuple instead of FillExtractionResult.

    Args:
        tx: Transaction data containing TakerGets and TakerPays
        base_currency: Base currency code
        quote_currency: Quote currency code
        trade_type: Whether this is a BUY or SELL order

    Returns:
        Tuple of (base_amount, quote_amount). Values are absolute.
    """
    result = extract_fill_from_transaction(tx, base_currency, quote_currency, trade_type)
    return result.base_amount, result.quote_amount
