"""
The base class for all network response types.

Represents fields common to all response types.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Union

from typing_extensions import Self

from xrpl.models.base_model import BaseModel
from xrpl.models.required import REQUIRED
from xrpl.models.transactions import PaymentFlag
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


class ResponseStatus(str, Enum):
    """Represents the different status possibilities."""

    SUCCESS = "success"
    ERROR = "error"


class ResponseType(str, Enum):
    """Represents the different response types a Response can have."""

    RESPONSE = "response"
    LEDGER_CLOSED = "ledgerClosed"
    TRANSACTION = "transaction"


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Response(BaseModel):
    """
    The base class for all network response types.

    Represents fields common to all response types.
    """

    status: ResponseStatus = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    result: Dict[str, Any] = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    id: Optional[Union[int, str]] = None
    type: Optional[ResponseType] = None

    def __post_init__(self: Self) -> None:
        """Called by dataclasses immediately after __init__."""
        super().__post_init__()
        if self.contains_partial_payment():
            warnings.warn(
                """This response contains a partial payment. Please confirm
                the delivered amount is correct""",
                stacklevel=2,
            )

    def is_successful(self: Self) -> bool:
        """
        Returns whether the request was successfully received and understood by the
        server.

        Returns:
            Whether the request was successfully received and understood by the server.
        """
        return self.status == ResponseStatus.SUCCESS

    def contains_partial_payment(self: Self) -> bool:
        """
        Returns whether the request contains at least one transactions with
        the partial payment flag set.

        Returns:
            True if at least one transaction in this Response has the partial
            payment flag set. False otherwise.
        """
        return self._do_contains_partial_payment(self.result)

    def _do_contains_partial_payment(self: Self, val: Any) -> bool:  # noqa: ANN401
        flagged = []
        if isinstance(val, dict):
            formatted = {key.strip().lower(): value for key, value in val.items()}
            if (
                "transactiontype" in formatted
                and formatted["transactiontype"] == TransactionType.PAYMENT
            ):
                flagged = [
                    True
                    for key, value in val.items()
                    if self._is_partial_payment(key, value)
                ]
        if isinstance(val, list):
            flagged = [
                True for sub_val in val if self._do_contains_partial_payment(sub_val)
            ]
        return len(flagged) > 0

    def _is_partial_payment(self: Self, key: str, val: Any) -> bool:  # noqa: ANN401
        if isinstance(val, dict):
            return self._do_contains_partial_payment(val)
        try:
            int_val = int(val)
        except (TypeError, ValueError):
            return False
        return key.strip().lower() == "flags" and (
            int_val & PaymentFlag.TF_PARTIAL_PAYMENT != 0
        )
