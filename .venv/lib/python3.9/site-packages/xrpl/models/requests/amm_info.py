"""This request gets information about an Automated Market Maker (AMM) instance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from xrpl.models.currencies import Currency
from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AMMInfo(Request):
    """
    The `amm_info` method gets information about an Automated Market Maker
    (AMM) instance.
    """

    amm_account: Optional[str] = None
    """
    The address of the AMM pool to look up.
    """

    asset: Optional[Currency] = None
    """
    One of the assets of the AMM pool to look up.
    """

    asset2: Optional[Currency] = None
    """
    The other asset of the AMM pool.
    """

    method: RequestMethod = field(default=RequestMethod.AMM_INFO, init=False)
