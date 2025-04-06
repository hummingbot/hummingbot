"""
A path is an ordered array. Each member of a path is an
object that specifies the step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from typing_extensions import Self

from xrpl.models.base_model import BaseModel
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class PathStep(BaseModel):
    """A PathStep represents an individual step along a Path."""

    account: Optional[str] = None
    currency: Optional[str] = None
    issuer: Optional[str] = None
    type: Optional[int] = None
    type_hex: Optional[str] = None

    def _get_errors(self: Self) -> Dict[str, str]:
        return {
            key: value
            for key, value in {
                **super()._get_errors(),
                "account": self._get_account_error(),
                "currency": self._get_currency_error(),
                "issuer": self._get_issuer_error(),
            }.items()
            if value is not None
        }

    def _get_account_error(self: Self) -> Optional[str]:
        if self.account is None:
            return None
        if self.currency is not None or self.issuer is not None:
            return "Cannot set account if currency or issuer are set"
        return None

    def _get_currency_error(self: Self) -> Optional[str]:
        if self.currency is None:
            return None
        if self.account is not None:
            return "Cannot set currency if account is set"
        if self.issuer is not None and self.currency.upper() == "XRP":
            return "Cannot set issuer if currency is XRP"
        return None

    def _get_issuer_error(self: Self) -> Optional[str]:
        if self.issuer is None:
            return None
        if self.account is not None:
            return "Cannot set issuer if account is set"
        if self.currency is not None and self.currency.upper() == "XRP":
            return "Cannot set issuer if currency is XRP"
        return None


Path = List[PathStep]
"""
A Path is an ordered array of PathSteps.
"""
