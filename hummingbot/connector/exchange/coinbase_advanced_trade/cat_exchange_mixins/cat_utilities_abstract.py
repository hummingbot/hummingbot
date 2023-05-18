from abc import ABC, abstractmethod

from hummingbot.logger import HummingbotLogger


class _UtilitiesMixinAbstract(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    async def _sleep(self, sleep: float):
        super()._sleep(sleep=sleep)

    def logger(self) -> HummingbotLogger:
        return super().logger()
