"""Model for SignerListSet transaction type."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern

from typing_extensions import Final, Self

from xrpl.models.nested_model import NestedModel
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init

MAX_SIGNER_ENTRIES: Final[int] = 32
"""
Maximum number of signer entries allowed.

:meta private:
"""

HEX_WALLET_LOCATOR_REGEX: Final[Pattern[str]] = re.compile("[A-Fa-f0-9]{64}")
"""
Matches hex-encoded WalletLocator in the format allowed by XRPL.

:meta private:
"""


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class SignerEntry(NestedModel):
    """Represents one entry in a list of multi-signers authorized to an account."""

    account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    signer_weight: int = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    wallet_locator: Optional[str] = None
    """
    An arbitrary 256-bit (32-byte) field that can be used to identify the signer, which
    may be useful for smart contracts, or for identifying who controls a key in a large
    organization.
    """


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class SignerListSet(Transaction):
    """
    Represents a `SignerListSet <https://xrpl.org/signerlistset.html>`_
    transaction, which creates, replaces, or removes a list of signers that
    can be used to `multi-sign a transaction
    <https://xrpl.org/multi-signing.html>`_.
    """

    signer_quorum: int = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    signer_entries: Optional[List[SignerEntry]] = None
    transaction_type: TransactionType = field(
        default=TransactionType.SIGNER_LIST_SET,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()

        # deleting a signer list requires self.signer_quorum == 0 and
        # self.signer_entries is None
        if self.signer_quorum == 0 and self.signer_entries is not None:
            errors["signer_list_set"] = (
                "Must not include a `signer_entries` value if the signer list is being "
                "deleted."
            )
        if self.signer_quorum != 0 and self.signer_entries is None:
            errors["signer_list_set"] = (
                "Must have a value of zero for `signer_quorum` if the signer list is "
                "being deleted."
            )

        if self.signer_entries is None:  # deletion of the SignerList object
            return errors

        if self.signer_quorum == REQUIRED:
            errors["signer_quorum"] = "`signer_quorum` is not set."
        elif self.signer_quorum <= 0:
            errors["signer_quorum"] = (
                "`signer_quorum` must be greater than or equal to 0 when not deleting "
                "signer_list."
            )

        if not isinstance(self.signer_entries, list):
            errors["signer_entries"] = (
                "`signer_entries` must be a list of `SignerEntry` objects."
            )
            return errors

        if (
            len(self.signer_entries) < 1
            or len(self.signer_entries) > MAX_SIGNER_ENTRIES
        ):
            errors["signer_entries"] = (
                "`signer_entries` must have at least 1 member and no more than "
                f"{MAX_SIGNER_ENTRIES} members. If this transaction is deleting the "
                "SignerList, then this parameter must be omitted."
            )
            return errors

        account_set = set()
        signer_weight_sum = 0

        for signer_entry in self.signer_entries:
            if signer_entry.account == self.account:
                errors["signer_entries"] = (
                    "The account submitting the transaction cannot appear in a "
                    "signer entry."
                )
            if signer_entry.wallet_locator is not None and not bool(
                HEX_WALLET_LOCATOR_REGEX.fullmatch(signer_entry.wallet_locator)
            ):
                errors["signer_entries"] = (
                    "A SignerEntry's wallet_locator must be a 256-bit (32-byte)"
                    "hexadecimal value."
                )
            account_set.add(signer_entry.account)
            signer_weight_sum += signer_entry.signer_weight

        if self.signer_quorum > signer_weight_sum:
            errors["signer_quorum"] = (
                "`signer_quorum` must be less than or equal to the sum of the "
                "SignerWeight values in the `signer_entries` list."
            )

        if len(account_set) != len(self.signer_entries):
            errors["signer_entries"] = (
                "An account cannot appear multiple times in the list of signer "
                "entries."
            )
        return errors
