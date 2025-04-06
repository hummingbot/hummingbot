"""Model for DIDSet transaction type."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Pattern

from typing_extensions import Final, Self

from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init

HEX_REGEX: Final[Pattern[str]] = re.compile("[a-fA-F0-9]*")


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class DIDSet(Transaction):
    """Represents a DIDSet transaction."""

    did_document: Optional[str] = None
    """
    The DID document associated with the DID.

    To delete the Data, DIDDocument, or URI field from an existing DID ledger
    entry, add the field as an empty string.
    """

    data: Optional[str] = None
    """
    The public attestations of identity credentials associated with the DID.
    To delete the Data, DIDDocument, or URI field from an existing DID ledger
    entry, add the field as an empty string.
    """

    uri: Optional[str] = None
    """
    The Universal Resource Identifier associated with the DID.
    To delete the Data, DIDDocument, or URI field from an existing DID ledger
    entry, add the field as an empty string.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.DID_SET,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()

        if self.did_document is None and self.data is None and self.uri is None:
            errors["did_set"] = "Must have one of `did_document`, `data`, and `uri`."
            # Can return here because there are no fields to process
            return errors

        if self.did_document == "" and self.data == "" and self.uri == "":
            errors["did_set"] = (
                "At least one of the fields `did_document`, `data`, and `uri` "
                + "must have a length greater than zero"
            )

            return errors

        def _process_field(name: str, value: Optional[str]) -> None:
            if value is not None:
                error_strs = []
                if not bool(HEX_REGEX.fullmatch(value)):
                    error_strs.append("must be hex")
                if len(value) > 256:
                    error_strs.append("must be <= 256 characters")
                if len(error_strs) > 0:
                    errors[name] = (" and ".join(error_strs) + ".").capitalize()

        _process_field("did_document", self.did_document)
        _process_field("data", self.data)
        _process_field("uri", self.uri)

        return errors
