"""Model for AMMDelete transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field

from xrpl.models.currencies import Currency
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AMMDelete(Transaction):
    """
    Delete an empty Automated Market Maker (AMM) instance that could not be fully
    deleted automatically.

    Tip: The AMMWithdraw transaction automatically tries to delete an AMM, along with
    associated ledger entries such as empty trust lines, if it withdrew all the assets
    from the AMM's pool. However, if there are too many trust lines to the AMM account
    to remove in one transaction, it may stop before fully removing the AMM. Similarly,
    an AMMDelete transaction removes up to a maximum number of trust lines; in extreme
    cases, it may take several AMMDelete transactions to fully delete the trust lines
    and the associated AMM. In all cases, the AMM ledger entry and AMM account are
    deleted by the last such transaction.
    """

    asset: Currency = REQUIRED  # type: ignore
    """
    The definition for one of the assets in the AMM's pool. This field is required.
    """

    asset2: Currency = REQUIRED  # type: ignore
    """
    The definition for the other asset in the AMM's pool. This field is required.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.AMM_DELETE,
        init=False,
    )
