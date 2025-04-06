"""
The sign_for command provides one signature for a multi-signed transaction.

By default, this method is admin-only. It can be used as a public method if the server
has enabled public signing.

This command requires the MultiSign amendment to be enabled.

`See sign_for <https://xrpl.org/sign_for.html>`_
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type

from typing_extensions import Self

from xrpl.constants import CryptoAlgorithm
from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class SignFor(Request):
    """
    The sign_for command provides one signature for a multi-signed transaction.

    By default, this method is admin-only. It can be used as a public method if the
    server has enabled public signing.

    This command requires the MultiSign amendment to be enabled.

    `See sign_for <https://xrpl.org/sign_for.html>`_
    """

    method: RequestMethod = field(default=RequestMethod.SIGN_FOR, init=False)
    account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
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

    @classmethod
    def from_dict(cls: Type[Self], value: Dict[str, Any]) -> Self:
        """
        Construct a new SignFor from a dictionary of parameters.

        Args:
            value: The value to construct the SignFor from.

        Returns:
            A new SignFor object, constructed using the given parameters.
        """
        if "tx_json" in value:
            fixed_value = {**value, "transaction": value["tx_json"]}
            del fixed_value["tx_json"]
        else:
            fixed_value = value
        return super(SignFor, cls).from_dict(fixed_value)

    def to_dict(self: Self) -> Dict[str, Any]:
        """
        Returns the dictionary representation of a SignFor.

        Returns:
            The dictionary representation of a SignFor.
        """
        return_dict = super().to_dict()
        del return_dict["transaction"]
        return_dict["tx_json"] = self.transaction.to_xrpl()
        return return_dict

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        if not self._has_only_one_seed():
            errors["SignFor"] = (
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
