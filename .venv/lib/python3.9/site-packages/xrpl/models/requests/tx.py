"""
The tx method retrieves information on a single transaction.

`See tx <https://xrpl.org/tx.html>`_
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from typing_extensions import Self

from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Tx(Request):
    """
    The tx method retrieves information on a single transaction.
    The Request must contain either transaction or CTID parameter, but not both.

    `See tx <https://xrpl.org/tx.html>`_
    """

    method: RequestMethod = field(default=RequestMethod.TX, init=False)
    ctid: Optional[str] = None
    """
    This field is optional.

    The compact transaction identifier of the transaction to look up.
    Must use uppercase hexadecimal only. New in: rippled 1.12.0  (Not supported in
    Clio v2.0 and earlier)

    The tx request accepts either ctid or transaction parameter, but not both.
    """

    transaction: Optional[str] = None
    """
    This field is optional.

    The 256-bit hash of the transaction to look up, as hexadecimal.

    The tx request accepts either ctid or transaction parameter, but not both.
    """

    binary: bool = False
    """
    This field is optional.

    If true, return transaction data and metadata as binary serialized to
    hexadecimal strings. If false, return transaction data and metadata as JSON.
    The default is false.
    """

    min_ledger: Optional[int] = None
    """
    This field is optional.

    Use this with max_ledger to specify a range of up to 1000 ledger indexes, starting
    with this ledger (inclusive). If the server cannot find the transaction, it
    confirms whether it was able to search all the ledgers in this range.
    """

    max_ledger: Optional[int] = None
    """
    This field is optional.

    Use this with min_ledger to specify a range of up to 1000 ledger indexes, ending
    with this ledger (inclusive). If the server cannot find the transaction, it
    confirms whether it was able to search all the ledgers in the requested range.
    """

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        if not self._has_only_one_input():
            errors["Tx"] = (
                "Must have only one of `ctid` or `transaction`, but not both."
            )
        return errors

    def _has_only_one_input(self: Self) -> bool:
        unique_ids = [self.transaction, self.ctid]
        present_items = list(filter(bool, unique_ids))
        return len(present_items) == 1
