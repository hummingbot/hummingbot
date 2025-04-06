"""The base model for all transactions and their nested object types."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha512
from typing import Any, Dict, List, Optional, Type, Union

from typing_extensions import Final, Self

from xrpl.core.binarycodec import decode, encode
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.amounts.mpt_amount import MPTAmount
from xrpl.models.base_model import ABBREVIATIONS, BaseModel
from xrpl.models.exceptions import XRPLModelException
from xrpl.models.flags import check_false_flag_definition, interface_to_flag_list
from xrpl.models.nested_model import NestedModel
from xrpl.models.requests import PathStep
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.types import PseudoTransactionType, TransactionType
from xrpl.models.types import XRPL_VALUE_TYPE
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init

_TRANSACTION_HASH_PREFIX: Final[int] = 0x54584E00


def transaction_json_to_binary_codec_form(
    dictionary: Dict[str, XRPL_VALUE_TYPE]
) -> Dict[str, XRPL_VALUE_TYPE]:
    """
    Returns a new dictionary in which the keys have been formatted as CamelCase and
    standardized to be serialized by the binary codec.

    Args:
        dictionary: The dictionary to be reformatted.

    Returns:
        A new dictionary object that has been reformatted.
    """
    # This method should be made private when it is removed from `xrpl.transactions`
    return {
        _key_to_tx_json(key): _value_to_tx_json(value)
        for (key, value) in dictionary.items()
    }


def _key_to_tx_json(key: str) -> str:
    """
    Transforms snake_case to PascalCase. For example:
        1. 'transaction_type' becomes 'TransactionType'
        2. 'URI' becomes 'uri'

    Known abbreviations (example 2 above) need to be enumerated in ABBREVIATIONS.
    """
    return "".join(
        [
            ABBREVIATIONS[word] if word in ABBREVIATIONS else word.capitalize()
            for word in key.split("_")
        ]
    )


def _value_to_tx_json(value: XRPL_VALUE_TYPE) -> XRPL_VALUE_TYPE:
    # IssuedCurrencyAmount and PathStep are special cases and should not be snake cased
    # and only contain primitive members
    if isinstance(value, list) and all(PathStep.is_dict_of_model(v) for v in value):
        return value
    if IssuedCurrencyAmount.is_dict_of_model(value):
        return value
    if MPTAmount.is_dict_of_model(value):
        return value
    if isinstance(value, dict):
        return transaction_json_to_binary_codec_form(value)
    if isinstance(value, list):
        return [_value_to_tx_json(sub_value) for sub_value in value]
    return value


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Memo(NestedModel):
    """
    An arbitrary piece of data attached to a transaction. A transaction can
    have multiple Memo objects as an array in the Memos field.
    Must contain one or more of ``memo_data``, ``memo_format``, and
    ``memo_type``.
    """

    memo_data: Optional[str] = None
    """The data of the memo, as a hexadecimal string."""

    memo_format: Optional[str] = None
    """
    The format of the memo, as a hexadecimal string. Conventionally, this
    should be the `MIME type
    <http://www.iana.org/assignments/media-types/media-types.xhtml>`_
    of the memo data.
    """

    memo_type: Optional[str] = None
    """
    The type of the memo, as a hexadecimal string. Conventionally, this
    should be an `RFC 5988 relation
    <http://tools.ietf.org/html/rfc5988#section-4>`_ defining the format of
    the memo data.
    """

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        present_memo_fields = [
            field
            for field in [
                self.memo_data,
                self.memo_format,
                self.memo_type,
            ]
            if field is not None
        ]
        if len(present_memo_fields) < 1:
            errors["Memo"] = "Memo must contain at least one field"
        return errors


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Signer(NestedModel):
    """
    One Signer in a multi-signature. A multi-signed transaction can have an
    array of up to 8 Signers, each contributing a signature, in the Signers
    field.
    """

    account: str = REQUIRED  # type: ignore
    """
    The address of the Signer. This can be a funded account in the XRP
    Ledger or an unfunded address.
    This field is required.

    :meta hide-value:
    """

    txn_signature: str = REQUIRED  # type: ignore
    """
    The signature that this Signer provided for this transaction.
    This field is required.

    :meta hide-value:
    """

    signing_pub_key: str = REQUIRED  # type: ignore
    """
    The public key that should be used to verify this Signer's signature.
    This field is required.

    :meta hide-value:
    """


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Transaction(BaseModel):
    """
    The base class for all `transaction types
    <https://xrpl.org/transaction-types.html>`_. Represents `fields common to all
    transaction types <https://xrpl.org/transaction-common-fields.html>`_.
    """

    account: str = REQUIRED  # type: ignore
    """
    The address of the sender of the transaction. Required.

    :meta hide-value:
    """

    transaction_type: Union[
        TransactionType, PseudoTransactionType
    ] = REQUIRED  # type: ignore

    fee: Optional[str] = None  # auto-fillable
    """
    (Auto-fillable) The amount of XRP to destroy as a cost to send this
    transaction. See `Transaction Cost
    <https://xrpl.org/transaction-cost.html>`_ for details.
    """

    sequence: Optional[int] = None  # auto-fillable
    """
    (Auto-fillable) The sequence number of the transaction. Must match the
    sending account's next unused sequence number. See `Account Sequence
    <https://xrpl.org/basic-data-types.html#account-sequence>`_ for details.
    """

    account_txn_id: Optional[str] = None
    """
    A hash value identifying a previous transaction from the same sender. If
    provided, this transaction is only considered valid if the identified
    transaction is the most recent transaction sent by this address. See
    `AccountTxnID
    <https://xrpl.org/transaction-common-fields.html#accounttxnid>`_ for
    details.
    """

    flags: Union[Dict[str, bool], int, List[int]] = 0
    """
    A List of flags, or a bitwise map of flags, modifying this transaction's
    behavior. See `Flags Field
    <https://xrpl.org/transaction-common-fields.html#flags-field>`_ for more details.
    """

    last_ledger_sequence: Optional[int] = None
    """
    The highest ledger index this transaction can appear in. Specifying this
    field places a strict upper limit on how long the transaction can wait
    to be validated or rejected. See `Reliable Transaction Submission
    <https://xrpl.org/reliable-transaction-submission.html>`_ for details.
    """

    memos: Optional[List[Memo]] = None
    """Additional arbitrary information attached to this transaction."""

    signers: Optional[List[Signer]] = None
    """
    Signing data authorizing a multi-signed transaction. Added during
    multi-signing.
    """

    source_tag: Optional[int] = None
    """
    An arbitrary `source tag
    <https://xrpl.org/source-and-destination-tags.html>`_ representing a
    hosted user or specific purpose at the sending account where this
    transaction comes from.
    """

    signing_pub_key: str = ""
    """
    The public key authorizing a single-signed transaction. Automatically
    added during signing.
    """

    ticket_sequence: Optional[int] = None
    """
    The sequence number of the ticket to use in place of a Sequence number. If
    this is provided, sequence must be 0. Cannot be used with account_txn_id.
    """

    txn_signature: Optional[str] = None
    """
    The cryptographic signature from the sender that authorizes this
    transaction. Automatically added during signing.
    """

    network_id: Optional[int] = None
    """The network id of the transaction."""

    def _get_errors(self: Self) -> Dict[str, str]:
        # import must be here to avoid circular dependencies
        from xrpl.wallet.main import Wallet

        errors = super()._get_errors()
        if self.ticket_sequence is not None and (
            (self.sequence is not None and self.sequence != 0)
            or self.account_txn_id is not None
        ):
            errors[
                "Transaction"
            ] = """If ticket_sequence is provided,
            account_txn_id must be None and sequence must be None or 0"""

        if isinstance(self.account, Wallet):
            errors["account"] = "Must pass in `wallet.address`, not `wallet`."

        return errors

    def to_dict(self: Self) -> Dict[str, Any]:
        """
        Returns the dictionary representation of a Transaction.

        Returns:
            The dictionary representation of a Transaction.
        """
        # we need to override this because transaction_type is using ``field``
        # which will not include the value in the objects __dict__
        return {
            **super().to_dict(),
            "transaction_type": self.transaction_type.value,
            "flags": self._flags_to_int(),
        }

    def _iter_to_int(
        self: Self,
        lst: List[int],
    ) -> int:
        """Calculate flag as int."""
        accumulator = 0
        for flag in lst:
            accumulator |= flag
        return accumulator

    def _flags_to_int(self: Self) -> int:
        if isinstance(self.flags, int):
            return self.flags
        check_false_flag_definition(tx_type=self.transaction_type, tx_flags=self.flags)
        if isinstance(self.flags, dict):
            return self._iter_to_int(
                lst=interface_to_flag_list(
                    tx_type=self.transaction_type,
                    tx_flags=self.flags,
                )
            )

        return self._iter_to_int(lst=self.flags)

    def to_xrpl(self: Self) -> Dict[str, Any]:
        """
        Creates a JSON-like dictionary in the JSON format used by the binary codec
        based on the Transaction object.

        Returns:
            A JSON-like dictionary in the JSON format used by the binary codec.
        """
        return transaction_json_to_binary_codec_form(self.to_dict())

    def blob(self: Self) -> str:
        """
        Creates the canonical binary format of the Transaction object.

        Returns:
            The binary-encoded object, as a hexadecimal string.
        """
        return encode(self.to_xrpl())

    @classmethod
    def from_dict(cls: Type[Self], value: Dict[str, Any]) -> Self:
        """
        Construct a new Transaction from a dictionary of parameters.

        Args:
            value: The value to construct the Transaction from.

        Returns:
            A new Transaction object, constructed using the given parameters.

        Raises:
            XRPLModelException: If the dictionary provided is invalid.
        """
        if cls.__name__ == "Transaction" or cls.__name__ == "PseudoTransaction":
            # using `(Pseudo)Transaction.from_dict` and not a subclass
            if "transaction_type" not in value:
                raise XRPLModelException(
                    "Transaction does not include transaction_type."
                )
            correct_type = cls.get_transaction_type(value["transaction_type"])
            return correct_type.from_dict(value)  # type: ignore
        else:
            if "transaction_type" in value:
                if value["transaction_type"] != cls.__name__:
                    transaction_type = value["transaction_type"]
                    raise XRPLModelException(
                        f"Using wrong constructor: using {cls.__name__} constructor "
                        f"with transaction type {transaction_type}."
                    )
                value = {**value}
                del value["transaction_type"]
            return super(Transaction, cls).from_dict(value)

    def has_flag(self: Self, flag: int) -> bool:
        """
        Returns whether the transaction has the given flag value set.

        Args:
            flag: The given flag value for which the function will determine whether it
                is set.

        Returns:
            Whether the transaction has the given flag value set.
        """
        if isinstance(self.flags, int):
            return self.flags & flag != 0
        elif isinstance(self.flags, dict):
            return flag in interface_to_flag_list(
                tx_type=self.transaction_type,
                tx_flags=self.flags,
            )
        else:  # is List[int]
            return flag in self.flags

    def is_signed(self: Self) -> bool:
        """
        Checks if a transaction has been signed.

        Returns:
            Whether the transaction has been signed
        """
        if self.signers:
            for signer in self.signers:
                if (
                    signer.signing_pub_key is None or len(signer.signing_pub_key) <= 0
                ) or (signer.txn_signature is None or len(signer.txn_signature) <= 0):
                    return False
            return True
        return (
            self.signing_pub_key is not None and len(self.signing_pub_key) > 0
        ) and (self.txn_signature is not None and len(self.txn_signature) > 0)

    def get_hash(self: Self) -> str:
        """
        Hashes the Transaction object as the ledger does. Only valid for signed
        Transaction objects.

        Returns:
            The hash of the Transaction object.

        Raises:
            XRPLModelException: if the Transaction is unsigned.
        """
        if self.txn_signature is None and self.signers is None:
            raise XRPLModelException(
                "Cannot get the hash from an unsigned Transaction."
            )
        prefix = hex(_TRANSACTION_HASH_PREFIX)[2:].upper()
        encoded_str = bytes.fromhex(prefix + encode(self.to_xrpl()))
        return sha512(encoded_str).digest().hex().upper()[:64]

    @classmethod
    def get_transaction_type(
        cls: Type[Self], transaction_type: str
    ) -> Type[Transaction]:
        """
        Returns the correct transaction type based on the string name.

        Args:
            transaction_type: The String name of the Transaction object.

        Returns:
            The transaction class with the given name.

        Raises:
            XRPLModelException: If `transaction_type` is not a valid Transaction type.
        """
        import xrpl.models.transactions as transaction_models
        import xrpl.models.transactions.pseudo_transactions as pseudo_transaction_models

        transaction_types: Dict[str, Type[Transaction]] = {
            t.value: getattr(transaction_models, t)
            for t in transaction_models.types.TransactionType
        }
        if transaction_type in transaction_types:
            return transaction_types[transaction_type]

        pseudo_transaction_types: Dict[str, Type[Transaction]] = {
            t.value: getattr(pseudo_transaction_models, t)
            for t in transaction_models.types.PseudoTransactionType
        }
        if transaction_type in pseudo_transaction_types:
            return pseudo_transaction_types[transaction_type]

        raise XRPLModelException(f"{transaction_type} is not a valid Transaction type")

    @staticmethod
    def from_blob(tx_blob: str) -> Transaction:
        """
        Decodes a transaction blob.

        Args:
            tx_blob: the tx blob to decode.

        Returns:
            The formatted transaction.
        """
        return Transaction.from_xrpl(decode(tx_blob))

    @classmethod
    def from_xrpl(cls: Type[Self], value: Union[str, Dict[str, Any]]) -> Self:
        """
        Creates a Transaction object based on a JSON or JSON-string representation of
        data

        In Payment transactions, the DeliverMax field is renamed to the Amount field.

        Args:
            value: The dictionary or JSON string to be instantiated.

        Returns:
            A Transaction object instantiated from the input.

        Raises:
            XRPLModelException: If Payment transactions have different values for
                                amount and deliver_max fields
        """
        processed_value = cls._process_xrpl_json(value)

        # handle the deliver_max alias in Payment transactions
        if (
            "transaction_type" in processed_value
            and processed_value["transaction_type"] == "Payment"
        ) and "deliver_max" in processed_value:
            if (
                "amount" in processed_value
                and processed_value["amount"] != processed_value["deliver_max"]
            ):
                raise XRPLModelException(
                    "Error: amount and deliver_max fields must be equal if both are "
                    + "provided"
                )
            else:
                processed_value["amount"] = processed_value["deliver_max"]

            # deliver_max field is not recognised in the Payment Request format,
            # nor is it supported in the serialization operations.
            del processed_value["deliver_max"]

        return cls.from_dict(processed_value)
