"""
The server_state command asks the server for various
machine-readable information about the rippled server's
current state. The response is almost the same as the
server_info method, but uses units that are easier to
process instead of easier to read. (For example, XRP
values are given in integer drops instead of scientific
notation or decimal values, and time is given in
milliseconds instead of seconds.)
"""

from dataclasses import dataclass, field

from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class ServerState(Request):
    """
    The server_state command asks the server for various
    machine-readable information about the rippled server's
    current state. The response is almost the same as the
    server_info method, but uses units that are easier to
    process instead of easier to read. (For example, XRP
    values are given in integer drops instead of scientific
    notation or decimal values, and time is given in
    milliseconds instead of seconds.)
    """

    method: RequestMethod = field(default=RequestMethod.SERVER_STATE, init=False)
