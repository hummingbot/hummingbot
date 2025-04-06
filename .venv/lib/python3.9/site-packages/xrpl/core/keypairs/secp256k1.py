"""secp256k1 elliptic curve cryptography interface."""

# The process for using SECP256k1 is complex and more involved than ED25519.
#
# See https://xrpl.org/cryptographic-keys.html#secp256k1-key-derivation
# for an overview of the algorithm.
from __future__ import annotations

from hashlib import sha256
from typing import Callable, Tuple, Type, cast

from ecpy.curves import Curve  # type: ignore
from ecpy.ecdsa import ECDSA  # type: ignore
from ecpy.keys import ECPrivateKey, ECPublicKey  # type: ignore
from typing_extensions import Final, Literal, Self

from xrpl.core.keypairs.crypto_implementation import CryptoImplementation
from xrpl.core.keypairs.exceptions import XRPLKeypairsException
from xrpl.core.keypairs.helpers import sha512_first_half

_CURVE: Final[Curve] = Curve.get_curve("secp256k1")
_GROUP_ORDER: Final[int] = _CURVE.order
_SIGNER: Final[ECDSA] = ECDSA("DER")

# String keys must be _KEY_LENGTH long
_KEY_LENGTH: Final[int] = 66
# Pad string keys with _PADDING_PREFIX to reach _KEY_LENGTH
_PADDING_PREFIX: Final[str] = "0"

# Generated sequence values are _SEQUENCE_SIZE bytes unsigned big-endian
_SEQUENCE_SIZE: Final[int] = 4
_SEQUENCE_MAX: Final[int] = 256**_SEQUENCE_SIZE

# Intermediate private keys are always padded with 4 bytes of zeros
_INTERMEDIATE_KEYPAIR_PADDING: Final[bytes] = (0).to_bytes(
    4,
    byteorder="big",
    signed=False,
)


class SECP256K1(CryptoImplementation):
    """
    Methods for using the ECDSA cryptographic system with the secp256k1
    elliptic curve.
    """

    @classmethod
    def derive_keypair(
        cls: Type[Self], decoded_seed: bytes, is_validator: bool
    ) -> Tuple[str, str]:
        """
        Derive the public and private secp256k1 keys from a given seed value.

        Args:
            decoded_seed: The secp256k1 seed to derive a key pair from, as bytes.
            is_validator: Whether to derive a validator keypair.

        Returns:
            A (public key, private key) pair derived from the given seed.
        """
        root_public, root_private = cls._do_derive_part(decoded_seed, "root")
        # validator keys just stop at the first pass
        if is_validator:
            return cls._format_keys(root_public, root_private)

        mid_public, mid_private = cls._do_derive_part(
            cls._public_key_to_bytes(root_public),
            "mid",
        )
        final_public, final_private = cls._derive_final_pair(
            root_public,
            root_private,
            mid_public,
            mid_private,
        )
        return cls._format_keys(final_public, final_private)

    @classmethod
    def sign(cls: Type[Self], message: bytes, private_key: str) -> bytes:
        """
        Signs a message using a given secp256k1 private key.

        Args:
            message: The message to sign, as bytes.
            private_key: The private key to use to sign the message.

        Returns:
            The signature of the message, as bytes.
        """
        wrapped_private = ECPrivateKey(int(private_key, 16), _CURVE)
        return cast(
            bytes,
            _SIGNER.sign_rfc6979(
                sha512_first_half(message),
                wrapped_private,
                sha256,
                canonical=True,
            ),
        )

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
        public_key_point = _CURVE.decode_point(bytes.fromhex(public_key))
        wrapped_public = ECPublicKey(public_key_point)
        return cast(
            bool,
            _SIGNER.verify(sha512_first_half(message), signature, wrapped_public),
        )

    @classmethod
    def _format_keys(
        cls: Type[Self], public: ECPublicKey, private: ECPrivateKey
    ) -> Tuple[str, str]:
        return (
            cls._format_key(cls._public_key_to_str(public)),
            cls._format_key(cls._private_key_to_str(private)),
        )

    @classmethod
    def _format_key(cls: Type[Self], keystr: str) -> str:
        return keystr.rjust(_KEY_LENGTH, _PADDING_PREFIX).upper()

    @classmethod
    def _public_key_to_bytes(cls: Type[Self], key: ECPublicKey) -> bytes:
        return bytes(_CURVE.encode_point(key.W, compressed=True))

    @classmethod
    def _public_key_to_str(cls: Type[Self], key: ECPublicKey) -> str:
        return cls._public_key_to_bytes(key).hex()

    @classmethod
    def _do_derive_part(
        cls: Type[Self], bytes_input: bytes, phase: Literal["root", "mid"]
    ) -> Tuple[ECPublicKey, ECPrivateKey]:
        """
        Given bytes_input determine public/private keypair for a given phase of
        this algorithm. The difference between generating the root and
        intermediate keypairs is just what bytes are input by the caller and that
        the intermediate keypair needs to inject _INTERMEDIATE_KEYPAIR_PADDING
        into the value to hash to get the raw private key.
        """

        def _candidate_merger(candidate: bytes) -> bytes:
            if phase == "root":
                return bytes_input + candidate
            return bytes_input + _INTERMEDIATE_KEYPAIR_PADDING + candidate

        raw_private = cls._get_secret(_candidate_merger)
        wrapped_private = ECPrivateKey(int.from_bytes(raw_private, "big"), _CURVE)
        return wrapped_private.get_public_key(), wrapped_private

    @classmethod
    def _derive_final_pair(
        cls: Type[Self],
        root_public: ECPublicKey,
        root_private: ECPrivateKey,
        mid_public: ECPublicKey,
        mid_private: ECPrivateKey,
    ) -> Tuple[ECPublicKey, ECPrivateKey]:
        raw_private = (root_private.d + mid_private.d) % _GROUP_ORDER
        wrapped_private = ECPrivateKey(raw_private, _CURVE)
        wrapped_public = ECPublicKey(_CURVE.add_point(root_public.W, mid_public.W))
        return wrapped_public, wrapped_private

    @classmethod
    def _get_secret(
        cls: Type[Self], candidate_merger: Callable[[bytes], bytes]
    ) -> bytes:
        """
        Given a function `candidate_merger` that knows how
        to prepare a sequence candidate bytestring into
        a possible full candidate secret, returns the first sequence
        value that is valid. If none are valid, raises; however this
        should be so exceedingly rare as to ignore.
        """
        for raw_root in range(_SEQUENCE_MAX):
            root = raw_root.to_bytes(
                _SEQUENCE_SIZE,
                byteorder="big",
                signed=False,
            )
            candidate = sha512_first_half(candidate_merger(root))
            if cls._is_secret_valid(candidate):
                return candidate
        raise XRPLKeypairsException(
            """Could not determine a key pair.
            This is extremely improbable. Please try again.""",
        )

    @classmethod
    def _is_secret_valid(cls: Type[Self], secret: bytes) -> bool:
        numerical_secret = int.from_bytes(secret, "big")
        return numerical_secret in range(1, _GROUP_ORDER)
