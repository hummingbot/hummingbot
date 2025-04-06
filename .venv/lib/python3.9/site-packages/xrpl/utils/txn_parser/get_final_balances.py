"""Parse final balances of every account involved in the given transaction."""

from decimal import Decimal
from typing import List, Optional

from xrpl.models import TransactionMetadata
from xrpl.utils.txn_parser.utils import (
    AccountBalances,
    NormalizedNode,
    derive_account_balances,
    get_value,
)


def get_final_balances(metadata: TransactionMetadata) -> List[AccountBalances]:
    """
    Parse all final balances from a transaction's metadata.

    Args:
        metadata: Transactions metadata.

    Returns:
        All final balances caused by a transaction.
        The final balances are grouped by the affected account addresses.
    """
    return derive_account_balances(metadata, _compute_final_balance)


def _compute_final_balance(node: NormalizedNode) -> Optional[Decimal]:
    """
    Get the final balance from a node.

    Args:
        node: The affected node.

    Returns:
        The final balance.
    """
    value: Optional[Decimal] = None
    new_fields = node.get("NewFields")
    final_fields = node.get("FinalFields")
    if new_fields is not None:
        balance = new_fields.get("Balance")
        if balance is not None:
            value = get_value(balance)
    elif final_fields is not None:
        balance = final_fields.get("Balance")
        if balance is not None:
            value = get_value(balance)
    if value is None or value == Decimal(0):
        return None
    return value
