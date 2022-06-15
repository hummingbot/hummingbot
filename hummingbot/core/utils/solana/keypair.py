"""Keypair module to manage public-private key pair."""
from __future__ import annotations

from typing import Optional

import solders.keypair
from solders.signature import Signature

from hummingbot.core.utils.solana import publickey

"""
Because the Solana library conflicts with dydx-python and dydx-v2-python libraries,
    we need to copy the implementation of this class as a workaround.
"""
class Keypair:
    """An account keypair used for signing transactions.

    Args:
        keypair: a `solders.keypair.Keypair` instance. Optional, defaults to None.

    Example:
        >>> # Init with random keypair:
        >>> keypair = Keypair()
        >>> # Init with existing keypair:
        >>> underlying = solders.keypair.Keypair()
        >>> keypair = Keypair(underlying)
    """

    def __init__(self, keypair: Optional[solders.keypair.Keypair] = None) -> None:
        """Create a new keypair instance.

        Generate random keypair if no keypair is provided. Initialize class variables.
        """
        if keypair is None:
            # the PrivateKey object comes with a public key too
            self._solders = solders.keypair.Keypair()
        else:
            self._solders = keypair

    @classmethod
    def from_solders(cls, keypair: solders.keypair.Keypair) -> Keypair:
        """Convert from the corresponding `solders` type.

        Args:
            keypair: A `solders` keypair.

        Returns:
            A `solana-py` keypair.
        """
        return cls(keypair)

    def to_solders(self) -> solders.keypair.Keypair:
        """Convert to the corresponding `solders` type.

        Returns:
            A `solders` keypair.
        """
        return self._solders

    @classmethod
    def generate(cls) -> Keypair:
        """Generate a new random keypair.

        This method exists to provide familiarity for web3.js users.
        There isn't much reason to use it instead of just instantiating
        `Keypair()`.

        Returns:
            The generated keypair.
        """
        return cls()

    @classmethod
    def from_secret_key(cls, secret_key: bytes) -> Keypair:
        """Create a keypair from the 64-byte secret key.

        This method should only be used to recreate a keypair from a previously
        generated secret key. Generating keypairs from a random seed should be done
        with the `.from_seed` method.

        Args:

            secret_key: secret key in bytes.

        Returns:
            The generated keypair.
        """
        seed = secret_key[:32]
        return cls.from_seed(seed)

    @classmethod
    def from_seed(cls, seed: bytes) -> Keypair:
        """Generate a keypair from a 32 byte seed.

        Args:

            seed: 32-byte seed.

        Returns:
            The generated keypair.
        """
        return cls(solders.keypair.Keypair.from_seed(seed))

    def sign(self, msg: bytes) -> Signature:
        """Sign a message with this keypair.

        Args:
            msg: message to sign.

        Returns:
            A signed messeged object.

        Example:

            >>> seed = bytes([1] * 32)
            >>> keypair = Keypair.from_seed(seed)
            >>> msg = b"hello"
            >>> signature = keypair.sign(msg)
            >>> bytes(signature).hex()
            'e1430c6ebd0d53573b5c803452174f8991ef5955e0906a09e8fdc7310459e9c82a402526748c3431fe7f0e5faafbf7e703234789734063ee42be17af16438d08'
        """  # pylint: disable=line-too-long
        return self._solders.sign_message(msg)

    @property
    def seed(self) -> bytes:
        """The 32-byte secret seed."""
        return bytes(self._solders.secret())

    @property
    def public_key(self) -> publickey.PublicKey:
        """The public key for this keypair."""
        underlying = self._solders.pubkey()
        return publickey.PublicKey.from_solders(underlying)

    @property
    def secret_key(self) -> bytes:
        """The raw 64-byte secret key for this keypair."""
        return self.seed + bytes(self.public_key)

    def __eq__(self, other) -> bool:
        """Checks for equality by comparing public keys."""
        if not isinstance(other, self.__class__):
            return False
        return self.secret_key == other.secret_key

    def __ne__(self, other) -> bool:
        """Implemented by negating __eq__."""
        return not (self == other)  # pylint: disable=superfluous-parens

    def __hash__(self) -> int:
        """Returns a unique hash for set operations."""
        return hash(self._solders)
