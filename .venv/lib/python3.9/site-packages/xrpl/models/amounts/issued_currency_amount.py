"""
Specifies an amount in an issued currency.

See https://xrpl.org/currency-formats.html#issued-currency-amounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Union

from typing_extensions import Self

from xrpl.models.currencies import IssuedCurrency
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class IssuedCurrencyAmount(IssuedCurrency):
    """
    Specifies an amount in an issued currency.

    See https://xrpl.org/currency-formats.html#issued-currency-amounts.
    """

    value: Union[str, int, float] = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    def to_currency(self: Self) -> IssuedCurrency:
        """
        Build an IssuedCurrency from this IssuedCurrencyAmount.

        Returns:
            The IssuedCurrency for this IssuedCurrencyAmount.
        """
        return IssuedCurrency(issuer=self.issuer, currency=self.currency)

    def to_dict(self: Self) -> Dict[str, str]:
        """
        Returns the dictionary representation of an IssuedCurrencyAmount.

        Returns:
            The dictionary representation of an IssuedCurrencyAmount.
        """
        return {**super().to_dict(), "value": str(self.value)}
