"""Parse balance changes of every account involved in the given transaction."""

from decimal import Decimal
from typing import List, Optional

from xrpl.models import TransactionMetadata
from xrpl.utils.txn_parser.utils import (
    AccountBalances,
    NormalizedNode,
    derive_account_balances,
    get_value,
)


def get_balance_changes(metadata: TransactionMetadata) -> List[AccountBalances]:
    """
    Parse all balance changes from a transaction's metadata.

    Args:
        metadata: Transactions metadata.

    Returns:
        All balance changes caused by a transaction.
        The balance changes are grouped by the affected account addresses.
    """
    return derive_account_balances(metadata, _compute_balance_change)


def _compute_balance_change(node: NormalizedNode) -> Optional[Decimal]:
    """
    Get the balance change from a node.

    Args:
        node: The affected node.

    Returns:
        The balance change.
    """
    value: Optional[Decimal] = None
    new_fields = node.get("NewFields")
    previous_fields = node.get("PreviousFields")
    final_fields = node.get("FinalFields")
    if new_fields is not None:
        balance = new_fields.get("Balance")
        if balance is not None:
            value = get_value(balance)
    elif previous_fields is not None and final_fields is not None:
        previous_fields_balance = previous_fields.get("Balance")
        final_fields_balance = final_fields.get("Balance")
        if previous_fields_balance is not None and final_fields_balance is not None:
            value = get_value(final_fields_balance) - get_value(previous_fields_balance)
    if value is None or value == Decimal(0):
        return None
    return value
