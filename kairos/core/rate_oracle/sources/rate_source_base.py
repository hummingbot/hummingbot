import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Optional

from kairos.logger import KairosLogger


class RateSourceBase(ABC):
    _logger: Optional[KairosLogger] = None

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @classmethod
    def logger(cls) -> KairosLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @abstractmethod
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        ...
