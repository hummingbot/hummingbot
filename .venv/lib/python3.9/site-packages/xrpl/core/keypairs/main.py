"""Interface for cryptographic key pairs for use with the XRP Ledger."""

from secrets import token_bytes
from typing import Dict, Optional, Tuple, Type, Union

from typing_extensions import Final

from xrpl.constants import CryptoAlgorithm
from xrpl.core import addresscodec
from xrpl.core.keypairs.crypto_implementation import CryptoImplementation
from xrpl.core.keypairs.ed25519 import ED25519
from xrpl.core.keypairs.ed25519 import PREFIX as ED_PREFIX
from xrpl.core.keypairs.exceptions import XRPLKeypairsException
from xrpl.core.keypairs.helpers import get_account_id
from xrpl.core.keypairs.secp256k1 import SECP256K1

_VERIFICATION_MESSAGE: Final[bytes] = b"This test message should verify."

_ALGORITHM_TO_MODULE_MAP: Final[Dict[CryptoAlgorithm, Type[CryptoImplementation]]] = {
    CryptoAlgorithm.ED25519: ED25519,
    CryptoAlgorithm.SECP256K1: SECP256K1,
}


def generate_seed(
    entropy: Optional[str] = None,
    algorithm: CryptoAlgorithm = CryptoAlgorithm.ED25519,
) -> str:
    """
    Generate a seed value that cryptographic keys can be derived from.

    Args:
        entropy: Hexadecimal string that is addresscodec.SEED_LENGTH bytes long
        algorithm: CryptoAlgorithm to use for seed generation. The default is
            :data:`CryptoAlgorithm.ED25519 <xrpl.CryptoAlgorithm.ED25519>`.

    Returns:
        A seed value that can be used to derive a key pair with the given
        cryptographic algorithm.

    Raises:
        XRPLAddressCodecException: If entropy is not of length addresscodec.SEED_LENGTH,
            this exception will be thrown in addresscodec.encode_seed.
    """
    if entropy is None:
        parsed_entropy = token_bytes(addresscodec.SEED_LENGTH)
    else:
        parsed_entropy = bytes.fromhex(entropy)
    return addresscodec.encode_seed(parsed_entropy, algorithm)


def derive_keypair(
    seed: str, validator: bool = False, algorithm: Optional[CryptoAlgorithm] = None
) -> Tuple[str, str]:
    """
    Derive the public and private keys from a given seed value.

    Args:
        seed: Seed to derive the key pair from. Use
            :func:`generate_seed() <xrpl.core.keypairs.generate_seed>` to generate an
            appropriate value.
        validator: Whether the keypair is a validator keypair.
        algorithm: The algorithm used to encode the keys. Inferred from the seed if not
            included.

    Returns:
        A (public key, private key) pair derived from the given seed.

    Raises:
        XRPLKeypairsException: If the derived keypair did not generate a
            verifiable signature.
    """
    decoded_seed, algorithm = addresscodec.decode_seed(seed, algorithm)
    module = _ALGORITHM_TO_MODULE_MAP[algorithm]
    public_key, private_key = module.derive_keypair(decoded_seed, validator)
    signature = module.sign(_VERIFICATION_MESSAGE, private_key)
    if not module.is_valid_message(_VERIFICATION_MESSAGE, signature, public_key):
        raise XRPLKeypairsException(
            "Derived keypair did not generate verifiable signature",
        )
    return public_key, private_key


def derive_classic_address(public_key: str) -> str:
    """
    Derive the XRP Ledger classic address for a given public key. See
    `Address Derivation
    <https://xrpl.org/cryptographic-keys.html#account-id-and-address>`_
    for more information.

    Args:
        public_key: The public key to derive the address from, as hexadecimal.

    Returns:
        The classic address corresponding to the given public key.
    """
    account_id = get_account_id(bytes.fromhex(public_key))
    return addresscodec.encode_classic_address(account_id)


def sign(message: Union[str, bytes], private_key: str) -> str:
    """
    Sign a message using a given private key.

    Args:
        message: The message to sign, as bytes.
        private_key: The private key to use to sign the message.

    Returns:
        Signed message, as hexadecimal.
    """
    if isinstance(message, str):
        message = bytes.fromhex(message)
    return (
        _get_module_from_key(private_key)
        .sign(
            message,
            private_key,
        )
        .hex()
        .upper()
    )


def is_valid_message(message: bytes, signature: bytes, public_key: str) -> bool:
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
    return _get_module_from_key(public_key).is_valid_message(
        message,
        signature,
        public_key,
    )


def _get_module_from_key(key: str) -> Type[CryptoImplementation]:
    if key.startswith(ED_PREFIX):
        return ED25519
    return SECP256K1
