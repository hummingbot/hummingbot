from typing import Union

from .savings import SavingsCustodian
from .spot import SpotCustodian

Custodian = Union[SavingsCustodian, SpotCustodian]

__all__ = [
    "SavingsCustodian",
    "SpotCustodian",
]
