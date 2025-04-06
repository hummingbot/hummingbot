"""The information needed to control an XRPL account."""

from __future__ import annotations

from typing import List, Optional, Type

from typing_extensions import Self

from xrpl.constants import CryptoAlgorithm, XRPLException
from xrpl.core import addresscodec
from xrpl.core.addresscodec import classic_address_to_xaddress, ensure_classic_address
from xrpl.core.addresscodec.exceptions import XRPLAddressCodecException
from xrpl.core.keypairs import derive_classic_address, derive_keypair, generate_seed


class Wallet:
    """
    The cryptographic keys needed to control an XRP Ledger account. See
    `Cryptographic Keys <https://xrpl.org/cryptographic-keys.html>`_ for
    details.
    """

    @property
    def address(self: Self) -> str:
        """
        The XRPL address that publicly identifies this wallet,
        as a base58 string. This is the same value as the `classic_address`.
        """  # noqa: DAR201
        return self._address

    # TODO: Just alias classic_address once mypy has resolved this issue:
    #       https://github.com/python/mypy/issues/6700
    @property
    def classic_address(self: Self) -> str:
        """
        `classic_address` is the same as `address`. It is called `classic_address` to
        differentiate it from the x-address standard, which encodes the network,
        destination tag, and XRPL address into a single value.
        It's also a base58 string.
        """  # noqa: DAR201
        return self._address

    def __init__(
        self: Self,
        public_key: str,
        private_key: str,
        *,
        master_address: Optional[str] = None,
        seed: Optional[str] = None,
        algorithm: Optional[CryptoAlgorithm] = None,
    ) -> None:
        """
        Generate a new Wallet.

        Args:
            public_key: The public key for the account.
            private_key: The private key used for signing transactions for the account.
            master_address: Include if a Wallet uses a Regular Key Pair. This sets the
                address that this wallet corresponds to. The default is `None`.
            seed: The seed used to derive the account keys. The default is `None`.
            algorithm: The algorithm used to encode the keys. Inferred from the seed if
                not included
        """
        if algorithm is None:
            if seed is not None and seed.startswith("sEd"):
                wallet_algorithm = CryptoAlgorithm.ED25519
            else:
                wallet_algorithm = CryptoAlgorithm.SECP256K1
        else:
            wallet_algorithm = algorithm

        """
        The core value that is used to derive all other information about
        this wallet. MUST be kept secret!
        """
        # Validate the seed before initialization of Wallet object
        if seed is not None:
            try:
                # We do not use the outputs of the below function, we are interested in
                # whether it throws an exception or not
                addresscodec.decode_seed(seed, wallet_algorithm)
            except Exception as e:
                raise XRPLAddressCodecException(
                    "Attempted to initialize a Wallet with "
                    + "an invalid seed: "
                    + seed
                    + ". The cryptographic algorithm"
                    + " used is: "
                    + wallet_algorithm
                    + "\nError message: "
                    + str(e)
                )

        self.seed = seed

        self.algorithm = wallet_algorithm
        """
        The algorithm that is used to convert the seed into its public/private keypair.
        """

        self.public_key = public_key
        """
        The public key that is used to identify this wallet's signatures, as
        a hexadecimal string.
        """

        self.private_key = private_key
        """
        The private key that is used to create signatures, as a hexadecimal
        string. MUST be kept secret!
        """

        self._address = (
            ensure_classic_address(master_address)
            if master_address is not None
            else derive_classic_address(self.public_key)
        )
        """Internal variable for classic_address. Use classic_address instead."""

    @classmethod
    def create(
        cls: Type[Self], algorithm: CryptoAlgorithm = CryptoAlgorithm.ED25519
    ) -> Self:
        """
        Generates a new seed and Wallet.

        Args:
            algorithm: The key-generation algorithm to use when generating the seed.
                The default is `ED25519`.

        Returns:
            The wallet that is generated from the given seed.
        """
        seed = generate_seed(algorithm=algorithm)
        return cls.from_seed(seed, algorithm=algorithm)

    @classmethod
    def from_seed(
        cls: Type[Self],
        seed: str,
        *,
        master_address: Optional[str] = None,
        algorithm: CryptoAlgorithm = CryptoAlgorithm.ED25519,
    ) -> Self:
        """
        Generates a new Wallet from seed (secret).

        Args:
            seed: The seed (secret) used to derive the account keys.
            master_address: Include if a Wallet uses a Regular Key Pair. This sets the
                address that this wallet corresponds to. The default is `None`.
            algorithm: The key-generation algorithm to use when generating the seed.
                The default is `ED25519`.

        Returns:
            The wallet that is generated from the given secret.
        """
        public_key, private_key = derive_keypair(seed, algorithm=algorithm)
        return cls(
            public_key,
            private_key,
            master_address=master_address,
            seed=seed,
            algorithm=algorithm,
        )

    from_secret = from_seed

    @classmethod
    def from_entropy(
        cls: Type[Self],
        entropy: str,
        *,
        master_address: Optional[str] = None,
        algorithm: CryptoAlgorithm = CryptoAlgorithm.ED25519,
    ) -> Self:
        """
        Generates a new Wallet from entropy (hexadecimal string of random numbers).

        Args:
            entropy: A hexadecimal string of random numbers to generate a seed used
                to derive a wallet.
            master_address: Include if a Wallet uses a Regular Key Pair. This sets the
                address that this wallet corresponds to. The default is `None`.
            algorithm: The key-generation algorithm to use when generating the seed.
                The default is `ED25519`.

        Returns:
            The wallet that is generated from the given entropy.

        Raises:
            XRPLException: If passed in entropy is not a bytestring.
        """
        if entropy is not None and len(entropy) != 32:
            raise XRPLException(
                "Entropy must be a 16-byte hexadecimal string of random numbers."
            )

        seed = generate_seed(entropy, algorithm)
        return cls.from_seed(seed, master_address=master_address, algorithm=algorithm)

    @classmethod
    def from_secret_numbers(
        cls: Type[Self],
        secret_numbers: List[str] | str,
        *,
        master_address: Optional[str] = None,
        algorithm: CryptoAlgorithm = CryptoAlgorithm.SECP256K1,
    ) -> Self:
        """
        Generates a new Wallet from secret numbers.

        Args:
            secret_numbers: A string (whitespace delimited) or string array consisting
                of 8 times 6 numbers used to derive a wallet.
            master_address: Include if a Wallet uses a Regular Key Pair. It must be
                the master address of the account. The default is `None`.
            algorithm: The digital signature algorithm to generate an address for.
                The default is `SECP256K1
                <https://xrpl.org/cryptographic-keys.html#secp256k1-key-derivation>`_
                (XUMM standard as of December 2022).

        Returns:
            The wallet that is generated from the given secret numbers.

        Raises:
            XRPLException: If the number of secret numbers is not 8. If the length of
                any secret number is not 6. If the checksum of any secret number is
                invalid.
        """
        # Logic adapted from xrpl-secret-numbers secretToEntropy function
        # https://github.com/XRPLF/xrpl.js/blob/main/packages/secret-numbers/src/utils/index.ts

        parsed_secret_numbers = (
            secret_numbers.split()
            if isinstance(secret_numbers, str)
            else secret_numbers
        )

        if len(parsed_secret_numbers) != 8:
            raise XRPLException("There must be 8 secret numbers.")

        entropy = ""
        for i, secret_number in enumerate(parsed_secret_numbers):
            no = int(secret_number[:5])
            checksum = int(secret_number[5:])

            if len(secret_number) != 6:
                raise XRPLException("Each secret number must be 6 digits long.")
            if no * (i * 2 + 1) % 9 != checksum:
                raise XRPLException(f"Checksum of secret number {i} is invalid.")

            hexed = hex(no)[2:].zfill(4)
            entropy += hexed

        return cls.from_entropy(
            entropy, master_address=master_address, algorithm=algorithm
        )

    def get_xaddress(
        self: Self, *, tag: Optional[int] = None, is_test: bool = False
    ) -> str:
        """
        Returns the X-Address of the Wallet's account.

        Args:
            tag: The destination tag of the address. Defaults to `None`.
            is_test: Whether the address corresponds to an address on the test network.
                Defaults to `False`.

        Returns:
            The X-Address of the Wallet's account.
        """
        return classic_address_to_xaddress(self.address, tag, is_test)

    def __str__(self: Self) -> str:
        """
        Returns a string representation of a Wallet.

        Returns:
            A string representation of a Wallet.
        """
        return "\n".join(
            [
                f"public_key: {self.public_key}",
                "private_key: -HIDDEN-",
                f"classic_address: {self.address}",
            ]
        )
