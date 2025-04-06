"""
The random command provides a random number to be
used as a source of entropy for random number generation by clients.
"""

from dataclasses import dataclass, field

from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Random(Request):
    """
    The random command provides a random number to be
    used as a source of entropy for random number generation by clients.
    """

    method: RequestMethod = field(default=RequestMethod.RANDOM, init=False)
