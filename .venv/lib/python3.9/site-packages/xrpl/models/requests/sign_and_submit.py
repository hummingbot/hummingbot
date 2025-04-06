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

from dataclasses import dataclass
from typing import Any, Dict, Optional, Type

from typing_extensions import Self

from xrpl.constants import CryptoAlgorithm
from xrpl.models.requests.submit import Submit
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class SignAndSubmit(Submit):
    """
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

    transaction: Transaction = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    secret: Optional[str] = None
    seed: Optional[str] = None
    seed_hex: Optional[str] = None
    passphrase: Optional[str] = None
    key_type: Optional[CryptoAlgorithm] = None
    offline: bool = False
    build_path: Optional[bool] = None  # note: None does have meaning here
    fee_mult_max: int = 10
    fee_div_max: int = 1

    @classmethod
    def from_dict(cls: Type[Self], value: Dict[str, Any]) -> Self:
        """
        Construct a new SignAndSubmit from a dictionary of parameters.

        Args:
            value: The value to construct the SignAndSubmit from.

        Returns:
            A new SignAndSubmit object, constructed using the given parameters.
        """
        if "tx_json" in value:
            fixed_value = {**value, "transaction": value["tx_json"]}
            del fixed_value["tx_json"]
        else:
            fixed_value = value
        return super(SignAndSubmit, cls).from_dict(fixed_value)

    def to_dict(self: Self) -> Dict[str, Any]:
        """
        Returns the dictionary representation of a SignAndSubmit.

        Returns:
            The dictionary representation of a SignAndSubmit.
        """
        return_dict = super().to_dict()
        del return_dict["transaction"]
        return_dict["tx_json"] = self.transaction.to_xrpl()
        return return_dict

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        if not self._has_only_one_seed():
            errors["SignAndSubmit"] = (
                "Must have only one of `secret`, `seed`, `seed_hex`, and `passphrase`."
            )

        if self.secret is not None and self.key_type is not None:
            errors["key_type"] = "Must omit `key_type` if `secret` is provided."

        return errors

    def _has_only_one_seed(self: Self) -> bool:
        present_items = [
            item
            for item in [self.secret, self.seed, self.seed_hex, self.passphrase]
            if item is not None
        ]
        return len(present_items) == 1
