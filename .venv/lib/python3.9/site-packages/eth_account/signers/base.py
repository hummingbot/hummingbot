from abc import (
    ABC,
    abstractmethod,
)
from typing import (
    Any,
)

from eth_typing import (
    ChecksumAddress,
    Hash32,
)

from eth_account.datastructures import (
    SignedMessage,
    SignedTransaction,
)
from eth_account.messages import (
    SignableMessage,
)
from eth_account.types import (
    TransactionDictType,
)


class BaseAccount(ABC):
    """
    Specify convenience methods to sign transactions and message hashes.
    """

    @property
    @abstractmethod
    def address(self) -> ChecksumAddress:
        """
        The checksummed public address for this account.

        .. code-block:: python

            >>> my_account.address # doctest: +SKIP
            "0xF0109fC8DF283027b6285cc889F5aA624EaC1F55"

        """

    @abstractmethod
    def sign_message(self, signable_message: SignableMessage) -> SignedMessage:
        """
        Sign the EIP-191_ message.

        This uses the same structure
        as in :meth:`~eth_account.account.Account.sign_message`
        but without specifying the private key.

        :param signable_message: The encoded message, ready for signing

        .. _EIP-191: https://eips.ethereum.org/EIPS/eip-191
        """

    @abstractmethod
    def unsafe_sign_hash(self, message_hash: Hash32) -> SignedMessage:
        """
        Sign the hash of a message.

        .. WARNING:: *Never* sign a hash that you didn't generate,
            it can be an arbitrary transaction. For example, it might
            send all of your account's ether to an attacker.
            Instead, prefer :meth:`~eth_account.account.Account.sign_message`,
            which cannot accidentally sign a transaction.

        This uses the same structure
        as in :meth:`~eth_account.account.Account.unsafe_sign_hash`
        but without specifying the private key.

        :param bytes message_hash: 32 byte hash of the message to sign
        """

    @abstractmethod
    def sign_transaction(
        self, transaction_dict: TransactionDictType
    ) -> SignedTransaction:
        """
        Sign a transaction dict.

        This uses the same structure as in
        :meth:`~eth_account.account.Account.sign_transaction`
        but without specifying the private key.

        :param dict transaction_dict: transaction with all fields specified
        """

    def __eq__(self, other: Any) -> bool:
        """
        Equality test between two accounts.

        Two accounts are considered the same if they are exactly the same type,
        and can sign for the same address.
        """
        return type(self) is type(other) and self.address == other.address

    def __hash__(self) -> int:
        return hash((type(self), self.address))
