"""Helper functions for parsers."""

from decimal import Decimal
from typing import Any, Dict, List, Union

from xrpl.utils.txn_parser.utils.types import (
    AccountBalance,
    AccountOfferChange,
    CurrencyAmount,
)


def get_value(balance: Union[CurrencyAmount, Dict[str, str], str]) -> Decimal:
    """
    Get a currency amount's value.

    Args:
        balance: Account's balance.

    Returns:
        The currency amount's value.
    """
    if isinstance(balance, str):
        return Decimal(balance)
    return Decimal(balance["value"])


def group_by_account(
    account_objects: Union[List[AccountBalance], List[AccountOfferChange]],
) -> Dict[str, Any]:
    """
    Groups the account objects in one list for each account.

    Args:
        account_objects: All computed objects.

    Returns:
        The grouped computed objects.
    """
    grouped_objects: Dict[str, Any] = {}
    for object in account_objects:
        if object.get("account") is not None:
            account = str(object.get("account"))
        else:
            account = str(object.get("maker_account"))
        grouped_objects.setdefault(account, []).append(object)
    return grouped_objects
