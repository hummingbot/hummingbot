"""
The submit method applies a transaction and sends it to the network to be confirmed and
included in future ledgers.

This command has two modes:
* Submit-only mode takes a signed, serialized transaction as a binary blob, and submits
it to the network as-is. Since signed transaction objects are immutable, no part of the
transaction can be modified or automatically filled in after submission.
* Sign-and-submit mode takes a JSON-formatted Transaction object, completes and signs
the transaction in the same manner as the sign method, and then submits the signed
transaction. We recommend only using this mode for testing and development.

To send a transaction as robustly as possible, you should construct and sign it in
advance, persist it somewhere that you can access even after a power outage, then
submit it as a tx_blob. After submission, monitor the network with the tx method
command to see if the transaction was successfully applied; if a restart or other
problem occurs, you can safely re-submit the tx_blob transaction: it won't be applied
twice since it has the same sequence number as the old transaction.

`See submit <https://xrpl.org/submit.html>`_
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Type

from typing_extensions import Self

from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Submit(Request):
    """
    WARNING: This object should never be created. You should create an object of type
    `SignAndSubmit` or `SubmitOnly` instead.

    The submit method applies a transaction and sends it to the network to be confirmed
    and included in future ledgers.

    This command has two modes:
    * Submit-only mode takes a signed, serialized transaction as a binary blob, and
    submits it to the network as-is. Since signed transaction objects are immutable, no
    part of the transaction can be modified or automatically filled in after submission.
    * Sign-and-submit mode takes a JSON-formatted Transaction object, completes and
    signs the transaction in the same manner as the sign method, and then submits the
    signed transaction. We recommend only using this mode for testing and development.

    To send a transaction as robustly as possible, you should construct and sign it in
    advance, persist it somewhere that you can access even after a power outage, then
    submit it as a tx_blob. After submission, monitor the network with the tx method
    command to see if the transaction was successfully applied; if a restart or other
    problem occurs, you can safely re-submit the tx_blob transaction: it won't be
    applied twice since it has the same sequence number as the old transaction.

    `See submit <https://xrpl.org/submit.html>`_
    """

    method: RequestMethod = field(default=RequestMethod.SUBMIT, init=False)

    @classmethod
    def from_dict(cls: Type[Self], value: Dict[str, Any]) -> Self:
        """
        Construct a new Submit from a dictionary of parameters.

        Args:
            value: The value to construct the Submit from.

        Returns:
            A new Submit object, constructed using the given parameters.

        Raises:
            XRPLModelException: If the dictionary provided is invalid.
        """
        from xrpl.models.requests import SignAndSubmit, SubmitOnly

        if cls.__name__ == "Submit":
            if "tx_blob" in value:
                return SubmitOnly.from_dict(value)  # type: ignore
            return SignAndSubmit.from_dict(value)  # type: ignore
        return super(Submit, cls).from_dict(value)
