"""
The server_info command asks the server for a
human-readable version of various information
about the rippled server being queried.
"""

from dataclasses import dataclass, field
from typing import Optional

from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class ServerDefinitions(Request):
    """
    The definitions command asks the server for a
    human-readable version of various information
    about the rippled server being queried.
    """

    method: RequestMethod = field(default=RequestMethod.SERVER_DEFINITIONS, init=False)

    hash: Optional[str] = None
