"""
The unsubscribe command tells the server to stop sending
messages for a particular subscription or set of subscriptions.

WebSocket API only.

`See unsubscribe <https://xrpl.org/unsubscribe.html>`_
"""

from dataclasses import dataclass, field
from typing import List, Optional

from xrpl.models.base_model import BaseModel
from xrpl.models.currencies import Currency
from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.requests.subscribe import StreamParameter
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class UnsubscribeBook(BaseModel):
    """Format for elements in the ``books`` array for Unsubscribe only."""

    taker_gets: Currency = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    taker_pays: Currency = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    both: bool = False


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Unsubscribe(Request):
    """
    The unsubscribe command tells the server to stop sending
    messages for a particular subscription or set of subscriptions.

    WebSocket API only.

    `See unsubscribe <https://xrpl.org/unsubscribe.html>`_
    """

    method: RequestMethod = field(default=RequestMethod.UNSUBSCRIBE, init=False)
    streams: Optional[List[StreamParameter]] = None
    accounts: Optional[List[str]] = None
    accounts_proposed: Optional[List[str]] = None
    books: Optional[List[UnsubscribeBook]] = None
