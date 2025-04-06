"""Ed25519 elliptic curve cryptography interface."""

from __future__ import annotations

from hashlib import sha512
from typing import Tuple, Type, cast

from ecpy.curves import Curve  # type: ignore
from ecpy.eddsa import EDDSA  # type: ignore
from ecpy.keys import ECPrivateKey, ECPublicKey  # type: ignore
from typing_extensions import Final, Self

from xrpl.core.keypairs.crypto_implementation import CryptoImplementation
from xrpl.core.keypairs.exceptions import XRPLKeypairsException
from xrpl.core.keypairs.helpers import sha512_first_half

PREFIX: Final[str] = "ED"
_CURVE: Final[Curve] = Curve.get_curve("Ed25519")
_SIGNER: Final[EDDSA] = EDDSA(sha512)


class ED25519(CryptoImplementation):
    """Methods for using the Ed25519 cryptographic system."""

    @classmethod
    def derive_keypair(
        cls: Type[Self], decoded_seed: bytes, is_validator: bool
    ) -> Tuple[str, str]:
        """
        Derives a key pair in Ed25519 format for use with the XRP Ledger from a
        seed value.

        Args:
            decoded_seed: The Ed25519 seed to derive a key pair from, as bytes.
            is_validator: Whether to derive a validator keypair.
                However, validator signing keys cannot use Ed25519.
                (See `#3434 <https://github.com/ripple/rippled/issues/3434>`_
                for more information.)

        Returns:
            A (public key, private key) pair derived from the given seed.

        Raises:
            XRPLKeypairsException: If the keypair is a validator keypair.
        """
        if is_validator:
            raise XRPLKeypairsException("Validator key pairs cannot use Ed25519")

        raw_private = sha512_first_half(decoded_seed)
        private = ECPrivateKey(int.from_bytes(raw_private, "big"), _CURVE)
        public = EDDSA.get_public_key(private, sha512)
        return (
            cls._format_key(cls._public_key_to_str(public)),
            cls._format_key(cls._private_key_to_str(private)),
        )

    @classmethod
    def sign(cls: Type[Self], message: bytes, private_key: str) -> bytes:
        """
        Signs a message using a given Ed25519 private key.

        Args:
            message: The message to sign, as bytes.
            private_key: The private key to use to sign the message.

        Returns:
            The signature of the message.
        """
        raw_private = private_key[len(PREFIX) :]
        wrapped_private = ECPrivateKey(int(raw_private, 16), _CURVE)
        return cast(bytes, _SIGNER.sign(message, wrapped_private))

    @classmethod
    def is_valid_message(
        cls: Type[Self], message: bytes, signature: bytes, public_key: str
    ) -> bool:
        """
        Verifies the signature on a given message.

        Args:
            message: The message to validate.
            signature: The signature of the message.
            public_key: The public key to use to verify the message and
                signature.

        Returns:
            Whether the message is valid for the given signature and public key.
        """
        raw_public = public_key[len(PREFIX) :]
        public_key_point = _CURVE.decode_point(bytes.fromhex(raw_public))
        wrapped_public = ECPublicKey(public_key_point)
        return cast(bool, _SIGNER.verify(message, signature, wrapped_public))

    @classmethod
    def _public_key_to_str(cls: Type[Self], key: ECPublicKey) -> str:
        return cast(str, _CURVE.encode_point(key.W).hex())

    @classmethod
    def _format_key(cls: Type[Self], keystr: str) -> str:
        if len(keystr) < 64:
            keystr = keystr.zfill(64)
        return (PREFIX + keystr).upper()
