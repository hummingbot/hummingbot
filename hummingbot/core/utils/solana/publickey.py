"""Library to interface with Solana public keys."""
from __future__ import annotations

from typing import Any, List, Tuple, Union

from solders.pubkey import Pubkey


def _rjust_pubkey(raw: bytes) -> bytes:
    return raw.rjust(Pubkey.LENGTH, b"\0")


class PublicKey:
    """The public key of a keypair.

    Example:
        >>> # An arbitary public key:
        >>> pubkey = PublicKey(1)
        >>> str(pubkey) # String representation in base58 form.
        '11111111111111111111111111111112'
        >>> bytes(pubkey).hex()
        '0000000000000000000000000000000000000000000000000000000000000001'

    """

    LENGTH = Pubkey.LENGTH
    """Constant for standard length of a public key."""

    def __init__(self, value: Union[bytearray, bytes, int, str, List[int], Pubkey]):
        """Init PublicKey object."""
        if isinstance(value, Pubkey):
            self._solders = value
        elif isinstance(value, str):
            try:
                self._solders = Pubkey.from_string(value)
            except ValueError as err:
                raise ValueError("invalid public key input:", value) from err
        elif isinstance(value, int):
            self._solders = Pubkey(_rjust_pubkey(bytes([value])))
        else:
            self._solders = Pubkey(_rjust_pubkey(bytes(value)))

    @classmethod
    def from_solders(cls, pubkey: Pubkey) -> PublicKey:
        """Convert from the corresponding `solders` type.

        Args:
            pubkey: A `solders` pubkey.

        Returns:
            A `solana-py` public key.
        """
        return cls(pubkey)

    def to_solders(self) -> Pubkey:
        """Convert to the corresponding `solders` type.

        Returns:
            A `solders` pubkey.
        """
        return self._solders

    def __bytes__(self) -> bytes:
        """Public key in bytes."""
        return bytes(self._solders)

    def __eq__(self, other: Any) -> bool:
        """Equality definition for PublicKeys."""
        return False if not isinstance(other, PublicKey) else bytes(self) == bytes(other)

    def __hash__(self) -> int:
        """Returns a unique hash for set operations."""
        return hash(self.__bytes__())

    def __repr__(self) -> str:
        """Representation of a PublicKey."""
        return str(self)

    def __str__(self) -> str:
        """String definition for PublicKey."""
        return self.to_base58().decode("utf-8")

    def to_base58(self) -> bytes:
        """Public key in base58.

        Returns:
            The base58-encoded public key.
        """
        return str(self._solders).encode()

    @classmethod
    def create_with_seed(cls, from_public_key: PublicKey, seed: str, program_id: PublicKey) -> PublicKey:
        """Derive a public key from another key, a seed, and a program ID.

        Returns:
            The derived public key.
        """
        underlying = Pubkey.create_with_seed(from_public_key.to_solders(), seed, program_id.to_solders())
        return PublicKey.from_solders(underlying)

    @classmethod
    def create_program_address(cls, seeds: List[bytes], program_id: PublicKey) -> PublicKey:
        """Derive a program address from seeds and a program ID.

        Returns:
            The derived program address.
        """
        underlying = Pubkey.create_program_address(seeds, program_id.to_solders())
        return cls.from_solders(underlying)

    @classmethod
    def find_program_address(cls, seeds: List[bytes], program_id: PublicKey) -> Tuple[PublicKey, int]:
        """Find a valid program address.

        Valid program addresses must fall off the ed25519 curve.  This function
        iterates a nonce until it finds one that when combined with the seeds
        results in a valid program address.

        Returns:
            The program address and nonce used.
        """
        underlying_pubkey, nonce = Pubkey.find_program_address(seeds, program_id.to_solders())
        return cls.from_solders(underlying_pubkey), nonce
