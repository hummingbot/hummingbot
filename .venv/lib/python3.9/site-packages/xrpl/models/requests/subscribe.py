"""
The subscribe method requests periodic notifications from the server
when certain events happen.

WebSocket API only.

`See subscribe <https://xrpl.org/subscribe.html>`_
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from xrpl.models.base_model import BaseModel
from xrpl.models.currencies import Currency
from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


class StreamParameter(str, Enum):
    """Represents possible values of the streams query param for subscribe."""

    CONSENSUS = "consensus"
    LEDGER = "ledger"
    MANIFESTS = "manifests"
    PEER_STATUS = "peer_status"
    TRANSACTIONS = "transactions"
    TRANSACTIONS_PROPOSED = "transactions_proposed"
    SERVER = "server"
    VALIDATIONS = "validations"


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class SubscribeBook(BaseModel):
    """Format for elements in the ``books`` array for Subscribe only."""

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

    taker: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    snapshot: bool = False
    both: bool = False


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Subscribe(Request):
    """
    The subscribe method requests periodic notifications from the server
    when certain events happen.

    WebSocket API only.

    `See subscribe <https://xrpl.org/subscribe.html>`_
    """

    method: RequestMethod = field(default=RequestMethod.SUBSCRIBE, init=False)
    streams: Optional[List[StreamParameter]] = None
    accounts: Optional[List[str]] = None
    accounts_proposed: Optional[List[str]] = None
    books: Optional[List[SubscribeBook]] = None
    url: Optional[str] = None
    url_username: Optional[str] = None
    url_password: Optional[str] = None
