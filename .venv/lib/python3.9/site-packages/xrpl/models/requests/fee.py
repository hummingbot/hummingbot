"""
The fee command reports the current state of the open-ledger requirements
for the transaction cost. This requires the FeeEscalation amendment to be
enabled.

This is a public command available to unprivileged users.
"""

from dataclasses import dataclass, field

from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Fee(Request):
    """
    The fee command reports the current state of the open-ledger requirements
    for the transaction cost. This requires the FeeEscalation amendment to be
    enabled.

    This is a public command available to unprivileged users.
    """

    method: RequestMethod = field(default=RequestMethod.FEE, init=False)
