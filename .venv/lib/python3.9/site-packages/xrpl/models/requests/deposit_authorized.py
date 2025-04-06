"""
The deposit_authorized command indicates whether one account
is authorized to send payments directly to another. See
Deposit Authorization for information on how to require
authorization to deliver money to your account.
"""

from dataclasses import dataclass, field

from xrpl.models.requests.request import LookupByLedgerRequest, Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class DepositAuthorized(Request, LookupByLedgerRequest):
    """
    The deposit_authorized command indicates whether one account
    is authorized to send payments directly to another. See
    Deposit Authorization for information on how to require
    authorization to deliver money to your account.
    """

    source_account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    destination_account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    method: RequestMethod = field(default=RequestMethod.DEPOSIT_AUTHORIZED, init=False)
