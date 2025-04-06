"""
WebSocket API only! The path_find method searches for a
path along which a transaction can possibly be made, and
periodically sends updates when the path changes over time.
For a simpler version that is supported by JSON-RPC, see the
ripple_path_find method. For payments occurring strictly in XRP,
it is not necessary to find a path, because XRP can be sent
directly to any account.

There are three different modes, or sub-commands, of the path_find
command. Specify which one you want with the subcommand parameter:

create - Start sending pathfinding information
close - Stop sending pathfinding information
status - Get the information of the currently-open pathfinding request
Although the rippled server tries to find the cheapest path or combination
of paths for making a payment, it is not guaranteed that the paths returned
by this method are, in fact, the best paths. Due to server load,
pathfinding may not find the best results. Additionally, you should be
careful with the pathfinding results from untrusted servers. A server
could be modified to return less-than-optimal paths to earn money for its
operators. If you do not have your own server that you can trust with
pathfinding, you should compare the results of pathfinding from multiple
servers run by different parties, to minimize the risk of a single server
returning poor results. (Note: A server returning less-than-optimal
results is not necessarily proof of malicious behavior; it could also be
a symptom of heavy server load.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from xrpl.models.amounts import Amount
from xrpl.models.path import Path
from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


class PathFindSubcommand(str, Enum):
    """
    There are three different modes, or sub-commands, of the path_find
    command. Specify which one you want with the subcommand parameter:

    create - Start sending pathfinding information
    close - Stop sending pathfinding information
    status - Get the information of the currently-open pathfinding request
    """

    CREATE = "create"
    CLOSE = "close"
    STATUS = "status"


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class PathFind(Request):
    """
    WebSocket API only! The path_find method searches for a
    path along which a transaction can possibly be made, and
    periodically sends updates when the path changes over time.
    For a simpler version that is supported by JSON-RPC, see the
    ripple_path_find method. For payments occurring strictly in XRP,
    it is not necessary to find a path, because XRP can be sent
    directly to any account.

    Although the rippled server tries to find the cheapest path or combination
    of paths for making a payment, it is not guaranteed that the paths returned
    by this method are, in fact, the best paths. Due to server load,
    pathfinding may not find the best results. Additionally, you should be
    careful with the pathfinding results from untrusted servers. A server
    could be modified to return less-than-optimal paths to earn money for its
    operators. If you do not have your own server that you can trust with
    pathfinding, you should compare the results of pathfinding from multiple
    servers run by different parties, to minimize the risk of a single server
    returning poor results. (Note: A server returning less-than-optimal
    results is not necessarily proof of malicious behavior; it could also be
    a symptom of heavy server load.)
    """

    subcommand: PathFindSubcommand = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
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

    destination_amount: Amount = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    method: RequestMethod = field(default=RequestMethod.PATH_FIND, init=False)
    send_max: Optional[Amount] = None
    paths: Optional[List[Path]] = None
