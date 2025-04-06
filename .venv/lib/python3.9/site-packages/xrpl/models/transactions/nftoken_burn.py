"""Model for NFTokenBurn transaction type."""

from dataclasses import dataclass, field
from typing import Optional

from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class NFTokenBurn(Transaction):
    """
    The NFTokenBurn transaction is used to remove an NFToken object from the
    NFTokenPage in which it is being held, effectively removing the token from
    the ledger ("burning" it).

    If this operation succeeds, the corresponding NFToken is removed. If this
    operation empties the NFTokenPage holding the NFToken or results in the
    consolidation, thus removing an NFTokenPage, the owner’s reserve requirement
    is reduced by one.
    """

    account: str = REQUIRED  # type: ignore
    """
    Identifies the AccountID that submitted this transaction. The account must
    be the present owner of the token or, if the lsfBurnable flag is set
    on the NFToken, either the issuer account or an account authorized by the
    issuer (i.e. MintAccount). This field is required.

    :meta hide-value:
    """

    nftoken_id: str = REQUIRED  # type: ignore
    """
    Identifies the NFToken to be burned. This field is required.

    :meta hide-value:
    """

    owner: Optional[str] = None
    """
    Indicates which account currently owns the token if it is different than
    Account. Only used to burn tokens which have the lsfBurnable flag enabled
    and are not owned by the signing account.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.NFTOKEN_BURN,
        init=False,
    )
