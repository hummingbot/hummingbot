"""Enum containing the different Psuedo-Transaction types."""

from enum import Enum


class PseudoTransactionType(str, Enum):
    """Enum containing the different Psuedo-Transaction types."""

    ENABLE_AMENDMENT = "EnableAmendment"
    SET_FEE = "SetFee"
    UNL_MODIFY = "UNLModify"
