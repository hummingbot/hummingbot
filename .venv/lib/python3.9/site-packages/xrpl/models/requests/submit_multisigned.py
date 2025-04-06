"""
The submit_multisigned command applies a multi-signed transaction and sends it to the
network to be included in future ledgers. (You can also submit multi-signed
transactions in binary form using the submit command in submit-only mode.)

This command requires the MultiSign amendment to be enabled.

`See submit_multisigned <https://xrpl.org/submit_multisigned.html>`_
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Type

from typing_extensions import Self

from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class SubmitMultisigned(Request):
    """
    The submit_multisigned command applies a multi-signed transaction and sends it to
    the network to be included in future ledgers. (You can also submit multi-signed
    transactions in binary form using the submit command in submit-only mode.)

    This command requires the MultiSign amendment to be enabled.

    `See submit_multisigned <https://xrpl.org/submit_multisigned.html>`_
    """

    method: RequestMethod = field(default=RequestMethod.SUBMIT_MULTISIGNED, init=False)
    tx_json: Transaction = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    fail_hard: bool = False

    @classmethod
    def from_dict(cls: Type[Self], value: Dict[str, Any]) -> Self:
        """
        Construct a new SubmitMultisigned object from a dictionary of parameters.

        Args:
            value: The value to construct the SubmitMultisigned from.

        Returns:
            A new SubmitMultisigned object, constructed using the given parameters.
        """
        fixed_value = {**value}
        if "TransactionType" in fixed_value["tx_json"]:  # xrpl format
            fixed_value["tx_json"] = Transaction.from_xrpl(fixed_value["tx_json"])
        return super(SubmitMultisigned, cls).from_dict(fixed_value)

    def to_dict(self: Self) -> Dict[str, Any]:
        """
        Returns the dictionary representation of a SubmitMultisigned object.

        Returns:
            The dictionary representation of a SubmitMultisigned object.
        """
        xrpl_dict = super().to_dict()
        xrpl_dict["tx_json"] = self.tx_json.to_xrpl()
        return xrpl_dict
