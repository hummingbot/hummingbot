"""Model for AccountSet transaction type."""

from __future__ import annotations  # Requires Python 3.7+

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from typing_extensions import Final, Self

from xrpl.models.flags import FlagInterface
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init

_MAX_TRANSFER_RATE: Final[int] = 2000000000
_MIN_TRANSFER_RATE: Final[int] = 1000000000
_SPECIAL_CASE_TRANFER_RATE: Final[int] = 0

_MIN_TICK_SIZE: Final[int] = 3
_MAX_TICK_SIZE: Final[int] = 15
_DISABLE_TICK_SIZE: Final[int] = 0

_MAX_DOMAIN_LENGTH: Final[int] = 256


class AccountSetAsfFlag(int, Enum):
    """
    Enum for AccountSet Flags.

    There are several options which can be either enabled or disabled for an account.
    Account options are represented by different types of flags depending on the
    situation. The AccountSet transaction type has several "AccountSet Flags" (prefixed
    `asf`) that can enable an option when passed as the SetFlag parameter, or disable
    an option when passed as the ClearFlag parameter. This enum represents those
    options.

    `See AccountSet asf Flags <https://xrpl.org/accountset.html#accountset-flags>`_
    """

    ASF_ACCOUNT_TXN_ID = 5
    """
    Track the ID of this account's most recent transaction. Required for
    `AccountTxnID <https://xrpl.org/transaction-common-fields.html#accounttxnid>`_
    """

    ASF_DEFAULT_RIPPLE = 8
    """
    Enable `rippling
    <https://xrpl.org/rippling.html>`_ on this account's trust lines by default.
    """

    ASF_DEPOSIT_AUTH = 9
    """
    Enable `Deposit Authorization
    <https://xrpl.org/depositauth.html>`_ on this account.
    """

    ASF_DISABLE_MASTER = 4
    """
    Disallow use of the master key pair. Can only be enabled if the account has
    configured another way to sign transactions, such as a `Regular Key
    <https://xrpl.org/cryptographic-keys.html>`_ or a `Signer List
    <https://xrpl.org/multi-signing.html>`_.
    """

    ASF_DISALLOW_XRP = 3
    """XRP should not be sent to this account. (Enforced by client applications)"""

    ASF_GLOBAL_FREEZE = 7
    """
    `Freeze
    <https://xrpl.org/freezes.html>`_ all assets issued by this account.
    """

    ASF_NO_FREEZE = 6
    """
    Permanently give up the ability to `freeze individual trust lines or disable
    Global Freeze <https://xrpl.org/freezes.html>`_. This flag can never be disabled
    after being enabled.
    """

    ASF_REQUIRE_AUTH = 2
    """
    Require authorization for users to hold balances issued by this address. Can
    only be enabled if the address has no trust lines connected to it.
    """

    ASF_REQUIRE_DEST = 1
    """Require a destination tag to send transactions to this account."""

    ASF_AUTHORIZED_NFTOKEN_MINTER = 10
    """Allow another account to mint and burn tokens on behalf of this account."""

    ASF_DISABLE_INCOMING_NFTOKEN_OFFER = 12
    """Disallow other accounts from creating NFTokenOffers directed at this account."""

    ASF_DISABLE_INCOMING_CHECK = 13
    """Disallow other accounts from creating Checks directed at this account."""

    ASF_DISABLE_INCOMING_PAYCHAN = 14
    """Disallow other accounts from creating PayChannels directed at this account."""

    ASF_DISABLE_INCOMING_TRUSTLINE = 15
    """Disallow other accounts from creating Trustlines directed at this account."""

    ASF_ALLOW_TRUSTLINE_CLAWBACK = 16
    """Allow trustline clawback feature"""


class AccountSetFlag(int, Enum):
    """
    Enum for AccountSet Transaction Flags.

    Transactions of the AccountSet type support additional values in the Flags field.
    This enum represents those options.

    `See AccountSet tf Flags <https://xrpl.org/accountset.html#accountset-flags>`_
    """

    TF_REQUIRE_DEST_TAG = 0x00010000
    """
    The same as SetFlag: asfRequireDest.
    """

    TF_OPTIONAL_DEST_TAG = 0x00020000
    """
    The same as ClearFlag: asfRequireDest.
    """

    TF_REQUIRE_AUTH = 0x00040000
    """
    The same as SetFlag: asfRequireAuth.
    """

    TF_OPTIONAL_AUTH = 0x00080000
    """
    The same as ClearFlag: asfRequireAuth.
    """

    TF_DISALLOW_XRP = 0x00100000
    """
    The same as SetFlag: asfDisallowXRP.
    """

    TF_ALLOW_XRP = 0x00200000
    """
    The same as ClearFlag: asfDisallowXRP.
    """


class AccountSetFlagInterface(FlagInterface):
    """
    Transactions of the AccountSet type support additional values in the Flags field.
    This TypedDict represents those options.

    `See AccountSet tf Flags <https://xrpl.org/accountset.html#accountset-flags>`_
    """

    TF_REQUIRE_DEST_TAG: bool
    TF_OPTIONAL_DEST_TAG: bool
    TF_REQUIRE_AUTH: bool
    TF_OPTIONAL_AUTH: bool
    TF_DISALLOW_XRP: bool
    TF_ALLOW_XRP: bool


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AccountSet(Transaction):
    """
    Represents an `AccountSet transaction <https://xrpl.org/accountset.html>`_,
    which modifies the properties of an account in the XRP Ledger.
    """

    clear_flag: Optional[AccountSetAsfFlag] = None
    """
    Disable a specific `AccountSet Flag
    <https://xrpl.org/accountset.html#accountset-flags>`_
    """

    domain: Optional[str] = None
    """
    Set the DNS domain of the account owner. Must be hex-encoded. You can
    use `xrpl.utils.str_to_hex` to convert a UTF-8 string to hex.
    """

    email_hash: Optional[str] = None
    """
    Set the MD5 Hash to be used for generating an avatar image for this
    account.
    """

    message_key: Optional[str] = None
    """Set a public key for sending encrypted messages to this account."""

    set_flag: Optional[AccountSetAsfFlag] = None
    """
    Enable a specific `AccountSet Flag
    <https://xrpl.org/accountset.html#accountset-flags>`_
    """

    transfer_rate: Optional[int] = None
    """
    Set the transfer fee to use for tokens issued by this account. See
    `TransferRate <https://xrpl.org/accountset.html#transferrate>`_ for
    details.
    """

    tick_size: Optional[int] = None
    """
    Set the tick size to use when trading tokens issued by this account in
    the decentralized exchange. See `Tick Size
    <https://xrpl.org/ticksize.html>`_ for details.
    """

    nftoken_minter: Optional[str] = None
    """
    Sets an alternate account that is allowed to mint NFTokens on this
    account's behalf using NFTokenMint's `Issuer` field. If set, you must
    also set the AccountSetAsfFlag.ASF_AUTHORIZED_NFTOKEN_MINTER flag.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.ACCOUNT_SET,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        return {
            key: value
            for key, value in {
                **super()._get_errors(),
                "tick_size": self._get_tick_size_error(),
                "transfer_rate": self._get_transfer_rate_error(),
                "domain": self._get_domain_error(),
                "clear_flag": self._get_clear_flag_error(),
                "nftoken_minter": self._get_nftoken_minter_error(),
            }.items()
            if value is not None
        }

    def _get_tick_size_error(self: Self) -> Optional[str]:
        if self.tick_size is None:
            return None
        if self.tick_size > _MAX_TICK_SIZE:
            return f"`tick_size` is above {_MAX_TICK_SIZE}."
        if self.tick_size < _MIN_TICK_SIZE and self.tick_size != _DISABLE_TICK_SIZE:
            return f"`tick_size` is below {_MIN_TICK_SIZE}."
        return None

    def _get_transfer_rate_error(self: Self) -> Optional[str]:
        if self.transfer_rate is None:
            return None
        if self.transfer_rate > _MAX_TRANSFER_RATE:
            return f"`transfer_rate` is above {_MAX_TRANSFER_RATE}."
        if (
            self.transfer_rate < _MIN_TRANSFER_RATE
            and self.transfer_rate != _SPECIAL_CASE_TRANFER_RATE
        ):
            return f"`transfer_rate` is below {_MIN_TRANSFER_RATE}."
        return None

    def _get_domain_error(self: Self) -> Optional[str]:
        if self.domain is not None and self.domain.lower() != self.domain:
            return f"Domain {self.domain} is not lowercase"
        if self.domain is not None and len(self.domain) > _MAX_DOMAIN_LENGTH:
            return f"Must not be longer than {_MAX_DOMAIN_LENGTH} characters"
        return None

    def _get_clear_flag_error(self: Self) -> Optional[str]:
        if self.clear_flag is not None and self.clear_flag == self.set_flag:
            return "Must not be equal to the set_flag"
        return None

    def _get_nftoken_minter_error(self: Self) -> Optional[str]:
        if (
            self.set_flag != AccountSetAsfFlag.ASF_AUTHORIZED_NFTOKEN_MINTER
            and self.nftoken_minter is not None
        ):
            return (
                "Will not set the minter unless "
                "AccountSetAsfFlag.ASF_AUTHORIZED_NFTOKEN_MINTER is set"
            )
        if (
            self.set_flag == AccountSetAsfFlag.ASF_AUTHORIZED_NFTOKEN_MINTER
            and self.nftoken_minter is None
        ):
            return (
                "Must be present if AccountSetAsfFlag.ASF_AUTHORIZED_NFTOKEN_MINTER "
                "is set"
            )
        if (
            self.clear_flag == AccountSetAsfFlag.ASF_AUTHORIZED_NFTOKEN_MINTER
            and self.nftoken_minter is not None
        ):
            return (
                "Must not be present if "
                "AccountSetAsfFlag.ASF_AUTHORIZED_NFTOKEN_MINTER is unset "
                "using clear_flag"
            )
        return None
