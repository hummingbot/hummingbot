"""Helper functions for balance parser."""

from decimal import Decimal
from typing import Callable, List, Optional

from xrpl.models.transactions.metadata import TransactionMetadata
from xrpl.utils.txn_parser.utils.nodes import NormalizedNode, normalize_nodes
from xrpl.utils.txn_parser.utils.parser import group_by_account
from xrpl.utils.txn_parser.utils.types import AccountBalance, AccountBalances, Balance
from xrpl.utils.xrp_conversions import drops_to_xrp


def _get_xrp_quantity(
    node: NormalizedNode,
    value: Optional[Decimal],
) -> Optional[AccountBalance]:
    if value is None:
        return None
    absolute_value = value.copy_abs()
    xrp_value = (
        drops_to_xrp(str(absolute_value)).copy_negate()
        if value.is_signed()
        else drops_to_xrp(str(absolute_value))
    )
    final_fields = node.get("FinalFields")
    if final_fields is not None:
        account = final_fields.get("Account")
        if account is not None:
            return AccountBalance(
                account=account,
                balance=Balance(
                    currency="XRP",
                    value=f"{xrp_value.normalize():f}",
                ),
            )
    new_fields = node.get("NewFields")
    if new_fields is not None:
        account = new_fields.get("Account")
        if account is not None:
            return AccountBalance(
                account=account,
                balance=Balance(
                    currency="XRP",
                    value=f"{xrp_value.normalize():f}",
                ),
            )
    return None


def _flip_trustline_perspective(account_balance: AccountBalance) -> AccountBalance:
    balance = account_balance["balance"]
    negated_value = Decimal(balance["value"]).copy_negate()
    issuer = balance["issuer"]
    return AccountBalance(
        account=issuer,
        balance=Balance(
            currency=balance["currency"],
            issuer=account_balance["account"],
            value=f"{negated_value.normalize():f}",
        ),
    )


def _get_trustline_quantity(
    node: NormalizedNode,
    value: Optional[Decimal],
) -> List[AccountBalance]:
    """
    Computes the complete list of every balance affected by the transaction.

    Args:
        node: The affected node.
        value: The currency amount value.

    Returns:
        A list of computed balances.
    """
    if value is None:
        return []
    fields = (
        node["NewFields"] if node.get("NewFields") is not None else node["FinalFields"]
    )
    assert fields is not None
    low_limit = fields.get("LowLimit")
    balance = fields.get("Balance")
    high_limit = fields.get("HighLimit")
    if low_limit is not None and balance is not None and high_limit is not None:
        low_limit_issuer = low_limit.get("issuer")
        assert isinstance(balance, dict)
        balance_currency = balance.get("currency")
        high_limit_issuer = high_limit.get("issuer")
        if (
            low_limit_issuer is not None
            and balance_currency is not None
            and high_limit_issuer is not None
        ):
            result = AccountBalance(
                account=low_limit_issuer,
                balance=Balance(
                    currency=balance_currency,
                    issuer=high_limit_issuer,
                    value=f"{value.normalize():f}",
                ),
            )
            return [result, _flip_trustline_perspective(result)]
    return []


def _get_node_balances(
    node: NormalizedNode,
    value: Optional[Decimal],
) -> List[AccountBalance]:
    """
    Retrieve the balance from a node.

    Args:
        node: The affected node.
        value: The currency amount's value

    Returns:
        A list of balances.
    """
    if node["LedgerEntryType"] == "AccountRoot":
        xrp_quantity = _get_xrp_quantity(node, value)
        if xrp_quantity is None:
            return []
        return [xrp_quantity]
    if node["LedgerEntryType"] == "RippleState":
        trustline_quantity = _get_trustline_quantity(node, value)
        return trustline_quantity
    return []


def _group_balances_by_account(
    account_balances: List[AccountBalance],
) -> List[AccountBalances]:
    grouped_balances = group_by_account(account_balances)
    result = []
    for account, account_obj in grouped_balances.items():
        balances: List[Balance] = [balance["balance"] for balance in account_obj]
        result.append(
            AccountBalances(
                account=account,
                balances=balances,
            )
        )
    return result


def derive_account_balances(
    metadata: TransactionMetadata,
    parser: Callable[[NormalizedNode], Optional[Decimal]],
) -> List[AccountBalances]:
    """
    Derives the account balances from a node.

    Args:
        metadata: Transactions metadata.
        parser: The balance parser.

    Returns:
        All balances affected by the transaction.
        The balances are grouped by their accounts.
    """
    quantities = [
        quantity
        for node in normalize_nodes(metadata)
        for quantity in _get_node_balances(node, parser(node))
    ]
    return _group_balances_by_account(quantities)
