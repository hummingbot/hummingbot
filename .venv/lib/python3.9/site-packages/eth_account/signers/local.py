from typing import (
    Any,
    Dict,
    Optional,
    cast,
)

from eth_keyfile.keyfile import (
    KDFType,
)
from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    ChecksumAddress,
    Hash32,
)

from eth_account.account_local_actions import (
    AccountLocalActions,
)
from eth_account.datastructures import (
    SignedMessage,
    SignedTransaction,
)
from eth_account.messages import (
    SignableMessage,
)
from eth_account.signers.base import (
    BaseAccount,
)
from eth_account.types import (
    Blobs,
    TransactionDictType,
)


class LocalAccount(BaseAccount):
    r"""
    A collection of convenience methods to sign and encrypt, with an
    embedded private key.

    :var bytes key: the 32-byte private key data

    .. code-block:: python

        >>> my_local_account.address
        "0xF0109fC8DF283027b6285cc889F5aA624EaC1F55"
        >>> my_local_account.key
        b"\x01\x23..."

    You can also get the private key by casting the account to :class:`bytes`:

    .. code-block:: python

        >>> bytes(my_local_account)
        b"\\x01\\x23..."
    """

    def __init__(self, key: PrivateKey, account: AccountLocalActions):
        """
        Initialize a new account with the given private key.

        :param eth_keys.PrivateKey key: to prefill in private key execution
        :param ~eth_account.account.Account account: the key-unaware management API
        """
        self._publicapi: AccountLocalActions = account

        self._address: ChecksumAddress = key.public_key.to_checksum_address()

        key_raw: bytes = key.to_bytes()
        self._private_key = key_raw

        self._key_obj: PrivateKey = key

    def __bytes__(self) -> bytes:
        return self.key

    @property
    def address(self) -> ChecksumAddress:
        return self._address

    @property
    def key(self) -> bytes:
        """
        Get the private key.
        """
        return self._private_key

    def encrypt(
        self,
        password: str,
        kdf: Optional[KDFType] = None,
        iterations: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate a string with the encrypted key.

        This uses the same structure as in
        :meth:`~eth_account.account.Account.encrypt`, but without a
        private key argument.
        """
        return self._publicapi.encrypt(
            self.key, password, kdf=kdf, iterations=iterations
        )

    def unsafe_sign_hash(self, message_hash: Hash32) -> SignedMessage:
        return cast(
            SignedMessage,
            self._publicapi.unsafe_sign_hash(
                message_hash,
                private_key=self.key,
            ),
        )

    def sign_message(self, signable_message: SignableMessage) -> SignedMessage:
        """
        Generate a string with the encrypted key.

        This uses the same structure as in
        :meth:`~eth_account.account.Account.sign_message`, but without a
        private key argument.
        """
        return cast(
            SignedMessage,
            self._publicapi.sign_message(signable_message, private_key=self.key),
        )

    def sign_transaction(
        self, transaction_dict: TransactionDictType, blobs: Optional[Blobs] = None
    ) -> SignedTransaction:
        return cast(
            SignedTransaction,
            self._publicapi.sign_transaction(transaction_dict, self.key, blobs=blobs),
        )

    def sign_typed_data(
        self,
        domain_data: Optional[Dict[str, Any]] = None,
        message_types: Optional[Dict[str, Any]] = None,
        message_data: Optional[Dict[str, Any]] = None,
        full_message: Optional[Dict[str, Any]] = None,
    ) -> SignedMessage:
        """
        Sign the provided EIP-712 message with the local private key.

        This uses the same structure as in
        :meth:`~eth_account.account.Account.sign_typed_data`, but without a
        private key argument.
        """
        return cast(
            SignedMessage,
            self._publicapi.sign_typed_data(
                private_key=self.key,
                domain_data=domain_data,
                message_types=message_types,
                message_data=message_data,
                full_message=full_message,
            ),
        )

    def sign_authorization(self, authorization: Dict[str, Any]) -> SignedMessage:
        return cast(
            SignedMessage,
            self._publicapi.sign_authorization(authorization, private_key=self.key),
        )
