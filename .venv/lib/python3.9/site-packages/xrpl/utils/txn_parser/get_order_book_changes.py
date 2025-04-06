"""Parse offer changes of every offer object involved in the given transaction."""

from typing import List

from xrpl.models import TransactionMetadata
from xrpl.utils.txn_parser.utils import AccountOfferChanges, compute_order_book_changes


def get_order_book_changes(metadata: TransactionMetadata) -> List[AccountOfferChanges]:
    """
    Parse all order book changes from a transaction's metadata.

    Args:
        metadata: Transactions metadata.

    Returns:
        All offer changes caused by the transaction.
        The offer changes are grouped by their owner accounts.
    """
    return compute_order_book_changes(metadata)
