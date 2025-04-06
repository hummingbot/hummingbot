import asyncio
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class KillSwitch(ABC):
    @abstractmethod
    def start(self):
        ...

    @abstractmethod
    def stop(self):
        ...


class ActiveKillSwitch(KillSwitch):
    ks_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.ks_logger is None:
            cls.ks_logger = logging.getLogger(__name__)
        return cls.ks_logger

    def __init__(self,
                 kill_switch_rate: Decimal,
                 hummingbot_application: "HummingbotApplication"):  # noqa F821
        self._hummingbot_application = hummingbot_application

        self._kill_switch_rate: Decimal = kill_switch_rate / Decimal(100)
        self._started = False
        self._update_interval = 10.0
        self._check_profitability_task: Optional[asyncio.Task] = None
        self._profitability: Optional[Decimal] = None

    async def check_profitability_loop(self):
        while True:
            try:
                self._profitability: Decimal = await self._hummingbot_application.calculate_profitability()

                # Stop the bot if losing too much money, or if gained a certain amount of profit
                if (self._profitability <= self._kill_switch_rate < Decimal("0.0")) or \
                        (self._profitability >= self._kill_switch_rate > Decimal("0.0")):
                    self.logger().info("Kill switch threshold reached. Stopping the bot...")
                    self._hummingbot_application.notify(f"\n[Kill switch triggered]\n"
                                                        f"Current profitability "
                                                        f"is {self._profitability}. Stopping the bot...")
                    self._hummingbot_application.stop()
                    break

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error calculating profitability: {e}", exc_info=True)

            await asyncio.sleep(self._update_interval)

    def start(self):
        safe_ensure_future(self.start_loop())

    async def start_loop(self):
        self.stop()
        self._check_profitability_task = safe_ensure_future(self.check_profitability_loop())
        self._started = True

    def stop(self):
        if self._check_profitability_task and not self._check_profitability_task.done():
            self._check_profitability_task.cancel()
        self._started = False


class PassThroughKillSwitch(KillSwitch):
    def start(self):
        pass

    def stop(self):
        pass
