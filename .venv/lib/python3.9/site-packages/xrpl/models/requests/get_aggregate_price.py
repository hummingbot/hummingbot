"""
This module defines the GetAggregatePrice request API. It is used to fetch aggregate
statistics about the specified PriceOracles
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from typing_extensions import Self

from xrpl.models.requests.ledger_entry import Oracle
from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True)
class GetAggregatePrice(Request):
    """
    The get_aggregate_price method retrieves the aggregate price of specified Oracle
    objects, returning three price statistics: mean, median, and trimmed mean.
    """

    method: RequestMethod = field(default=RequestMethod.GET_AGGREGATE_PRICE, init=False)

    base_asset: str = REQUIRED  # type: ignore
    """The currency code of the asset to be priced"""

    quote_asset: str = REQUIRED  # type: ignore
    """The currency code of the asset to quote the price of the base asset"""

    oracles: List[Oracle] = REQUIRED  # type: ignore
    """The oracle identifier"""

    trim: Optional[int] = None
    """The percentage of outliers to trim. Valid trim range is 1-25. If included, the
    API returns statistics for the trimmed mean"""

    time_threshold: Optional[int] = None
    """Defines a time range in seconds for filtering out older price data. Default
    value is 0, which doesn't filter any data"""

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        if len(self.oracles) == 0:
            errors["GetAggregatePrice"] = (
                "Oracles array must contain at least one element"
            )
        return errors
