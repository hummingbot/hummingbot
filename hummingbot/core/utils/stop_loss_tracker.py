import logging
import asyncio
from typing import (
    List,
    Dict,
    Callable,
    Optional,
)

from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.market.market_base import MarketBase
from hummingbot.logger import HummingbotLogger


class StopLossTracker:
    slc_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.slc_logger is None:
            cls.slc_logger = logging.getLogger(__name__)
        return cls.slc_logger

    def __init__(self,
                 data_feed: DataFeedBase,
                 assets: List[str],
                 markets: List[MarketBase],
                 stop_handler: Callable):
        self._data_feed: DataFeedBase = data_feed
        self._markets: List[MarketBase] = markets
        self._assets: List[str] = assets
        self._stop_handler: Callable = stop_handler
        self._stop_loss_pct = global_config_map.get("stop_loss_pct").value
        self._stop_loss_price_type = global_config_map.get("stop_loss_price_type").value
        self._stop_loss_base_token = global_config_map.get("stop_loss_base_token").value

        self._starting_balances: Dict[str, float] = {}
        self._starting_prices: Dict[str, float] = {}
        self._current_pnl = 0.0
        self._started = False
        self._update_interval = 10.0
        self._check_stop_loss_task: Optional[asyncio.Task] = None

    @property
    def current_pnl(self):
        return self._current_pnl

    def get_balances(self) -> Dict[str, float]:
        balance_dict: Dict[str, float] = {}
        for asset in self._assets:
            balance_dict[asset] = 0.0
            for market in self._markets:
                balance_dict[asset] += market.get_balance(asset)
        return balance_dict

    async def stop_loss_loop(self):
        while True:
            try:
                self._current_pnl = self.calculate_profit_loss_pct(self._stop_loss_price_type)
                if self._current_pnl <= -self._stop_loss_pct:
                    self.logger().info("Stop loss threshold reached. Stopping the bot...")
                    self._stop_handler()
                    break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error calculating stop loss percentage: {e}", exc_info=True)

            await asyncio.sleep(self._update_interval)

    def calculate_profit_loss_pct(self, stop_loss_type: str) -> float:
        def calculate_total(balances, prices):
            total_value: float = 0.0
            for asset in self._assets:
                total_value += balances[asset] * prices[asset]
            return total_value

        starting_total = calculate_total(self._starting_balances, self._starting_prices)
        current_balances = self.get_balances()
        current_prices = self._data_feed.price_dict
        try:
            if stop_loss_type == "fixed":
                current_total = calculate_total(current_balances, self._starting_prices)
                return (current_total - starting_total) / starting_total
            elif stop_loss_type == "dynamic":
                starting_total /= self._starting_prices[self._stop_loss_base_token]
                current_total = calculate_total(current_balances, current_prices) / \
                                (current_prices[self._stop_loss_base_token])
                return (current_total - starting_total) / starting_total
        except ZeroDivisionError:
            return 0.0
        except Exception as e:
            self.logger().error(f"Error calculating stop loss percentage: {e}", exc_info=True)
            return 0.0
        raise ValueError(f"Stop loss type {stop_loss_type} does not exist")

    def start(self):
        if self._stop_loss_pct >= 0:
            asyncio.ensure_future(self.start_loop())

    async def start_loop(self):
        await self._data_feed.get_ready()
        self.stop()
        self._starting_balances = self.get_balances()
        self._starting_prices = self._data_feed.price_dict.copy()
        self._check_stop_loss_task = asyncio.ensure_future(self.stop_loss_loop())
        self._started = True

    def stop(self):
        if self._check_stop_loss_task and not self._check_stop_loss_task.done():
            self._check_stop_loss_task.cancel()
        self._started = False
