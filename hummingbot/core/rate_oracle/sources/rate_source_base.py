import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Optional

from hummingbot.logger import HummingbotLogger


class RateSourceBase(ABC):
    _logger: Optional[HummingbotLogger] = None

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @abstractmethod
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        ...
