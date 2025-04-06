"""
This request provides a quick way to check the status of the Default Ripple field
for an account and the No Ripple flag of its trust lines, compared with the
recommended settings.

`See noripple_check <https://xrpl.org/noripple_check.html>`_
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from xrpl.models.requests.request import LookupByLedgerRequest, Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


class NoRippleCheckRole(str, Enum):
    """Represents the options for the address role in a NoRippleCheckRequest."""

    GATEWAY = "gateway"
    USER = "user"


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class NoRippleCheck(Request, LookupByLedgerRequest):
    """
    This request provides a quick way to check the status of the Default Ripple field
    for an account and the No Ripple flag of its trust lines, compared with the
    recommended settings.

    `See noripple_check <https://xrpl.org/noripple_check.html>`_
    """

    account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    method: RequestMethod = field(default=RequestMethod.NO_RIPPLE_CHECK, init=False)
    role: NoRippleCheckRole = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    transactions: bool = False
    limit: Optional[int] = 300
