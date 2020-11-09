import asyncio
import logging
from decimal import Decimal
from typing import Optional
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future


class KillSwitch:
    ks_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.ks_logger is None:
            cls.ks_logger = logging.getLogger(__name__)
        return cls.ks_logger

    def __init__(self,
                 hummingbot_application: "HummingbotApplication"):  # noqa F821
        self._hummingbot_application = hummingbot_application

        self._kill_switch_enabled: bool = global_config_map.get("kill_switch_enabled").value
        self._kill_switch_rate: Decimal = Decimal(global_config_map.get("kill_switch_rate").value or "0.0") / \
            Decimal(100)
        self._started = False
        self._update_interval = 10.0
        self._check_profitability_task: Optional[asyncio.Task] = None
        self._profitability: Optional[Decimal] = None

    async def check_profitability_loop(self):
        while True:
            try:
                if self._kill_switch_enabled:
                    self._profitability: Decimal = await self._hummingbot_application.calculate_profitability()

                    # Stop the bot if losing too much money, or if gained a certain amount of profit
                    if (self._profitability <= self._kill_switch_rate < Decimal("0.0")) or \
                            (self._profitability >= self._kill_switch_rate > Decimal("0.0")):
                        self.logger().info("Kill switch threshold reached. Stopping the bot...")
                        self._hummingbot_application._notify(f"\n[Kill switch triggered]\n"
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
