"""
The sign method takes a transaction in JSON format and a seed value, and returns a
signed binary representation of the transaction. To contribute one signature to a
multi-signed transaction, use the sign_for method instead.

By default, this method is admin-only. It can be used as a public method if the server
has enabled public signing.

Caution:
Unless you run the rippled server yourself, you should do local signing with RippleAPI
instead of using this command. An untrustworthy server could change the transaction
before signing it, or use your secret key to sign additional arbitrary transactions as
if they came from you.

`See sign <https://xrpl.org/sign.html>`_
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
class Sign(Request):
    """
    The sign method takes a transaction in JSON format and a seed value, and returns a
    signed binary representation of the transaction. To contribute one signature to a
    multi-signed transaction, use the sign_for method instead.

    By default, this method is admin-only. It can be used as a public method if the
    server has enabled public signing.

    Caution:
    Unless you run the rippled server yourself, you should do local signing with
    RippleAPI instead of using this command. An untrustworthy server could change the
    transaction before signing it, or use your secret key to sign additional arbitrary
    transactions as if they came from you.

    `See sign <https://xrpl.org/sign.html>`_
    """

    method: RequestMethod = field(default=RequestMethod.SIGN, init=False)
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
        Construct a new Sign from a dictionary of parameters.

        Args:
            value: The value to construct the Sign from.

        Returns:
            A new Sign object, constructed using the given parameters.
        """
        if "tx_json" in value:
            fixed_value = {**value, "transaction": value["tx_json"]}
            del fixed_value["tx_json"]
        else:
            fixed_value = value
        return super(Sign, cls).from_dict(fixed_value)

    def to_dict(self: Self) -> Dict[str, Any]:
        """
        Returns the dictionary representation of a Sign.

        Returns:
            The dictionary representation of a Sign.
        """
        return_dict = super().to_dict()
        del return_dict["transaction"]
        return_dict["tx_json"] = self.transaction.to_xrpl()
        return return_dict

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        if not self._has_only_one_seed():
            errors["Sign"] = (
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
