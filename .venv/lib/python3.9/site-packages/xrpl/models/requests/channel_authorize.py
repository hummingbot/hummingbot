"""
The channel_authorize method creates a signature that can
be used to redeem a specific amount of XRP from a payment channel.

Warning: Do not send secret keys to untrusted servers or through unsecured network
connections. (This includes the secret, seed, seed_hex, or passphrase fields of this
request.) You should only use this method on a secure, encrypted network connection to
a server you run or fully trust with your funds. Otherwise, eavesdroppers could use
your secret key to sign claims and take all the money from this payment channel and
anything else using the same key pair. See
`Set Up Secure Signing <https://xrpl.org/set-up-secure-signing.html>`_ for instructions.

`See channel_authorize <https://xrpl.org/channel_authorize.html>`_
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from typing_extensions import Self

from xrpl.constants import CryptoAlgorithm
from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class ChannelAuthorize(Request):
    """
    The channel_authorize method creates a signature that can
    be used to redeem a specific amount of XRP from a payment channel.

    Warning: Do not send secret keys to untrusted servers or through unsecured network
    connections. (This includes the secret, seed, seed_hex, or passphrase fields of
    this request.) You should only use this method on a secure, encrypted network
    connection to a server you run or fully trust with your funds. Otherwise,
    eavesdroppers could use your secret key to sign claims and take all the money from
    this payment channel and anything else using the same key pair. See
    `Set Up Secure Signing <https://xrpl.org/set-up-secure-signing.html>`_ for
    instructions.

    `See channel_authorize <https://xrpl.org/channel_authorize.html>`_
    """

    method: RequestMethod = field(default=RequestMethod.CHANNEL_AUTHORIZE, init=False)
    channel_id: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    amount: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    secret: Optional[str] = None
    seed: Optional[str] = None
    seed_hex: Optional[str] = None
    passphrase: Optional[str] = None
    key_type: Optional[CryptoAlgorithm] = None

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        signing_methods = [
            method
            for method in [
                self.secret,
                self.seed,
                self.seed_hex,
                self.passphrase,
            ]
            if method is not None
        ]
        if len(signing_methods) != 1:
            errors["ChannelAuthorize"] = (
                "Must set exactly one of `secret`, `seed`, `seed_hex`, or `passphrase`."
            )
        return errors
