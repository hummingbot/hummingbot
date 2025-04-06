"""Specifies an MPT amount."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Union

from typing_extensions import Self

from xrpl.models.base_model import BaseModel
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class MPTAmount(BaseModel):
    """Specifies an MPT amount."""

    mpt_issuance_id: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    value: Union[str, int, float] = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    def to_dict(self: Self) -> Dict[str, str]:
        """
        Returns the dictionary representation of an MPTAmount.

        Returns:
            The dictionary representation of an MPTAmount.
        """
        return {**super().to_dict(), "value": str(self.value)}
