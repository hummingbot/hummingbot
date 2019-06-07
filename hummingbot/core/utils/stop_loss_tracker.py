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
from hummingbot.strategy.market_symbol_pair import MarketSymbolPair
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
                 market_symbol_pairs: List[MarketSymbolPair],
                 stop_handler: Callable):
        self._data_feed: DataFeedBase = data_feed
        self._market_symbol_pairs: List[MarketSymbolPair] = market_symbol_pairs
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
        for market_symbol_pair in self._market_symbol_pairs:
            b = market_symbol_pair.base_asset
            q = market_symbol_pair.quote_asset
            market_symbol_pair.market.get_balance(b)
            market_symbol_pair.market.get_balance(q)
            balance_dict[b] = balance_dict.get(b) or 0.0
            balance_dict[q] = balance_dict.get(q) or 0.0
            balance_dict[b] += market_symbol_pair.market.get_balance(b)
            balance_dict[q] += market_symbol_pair.market.get_balance(q)
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
        def calculate_total(balances, data_feed_prices):
            total_value: float = 0.0
            for market_symbol_pair in self._market_symbol_pairs:
                market, tp, b, q = market_symbol_pair
                base_price = (market.get_price(tp, True) + market.get_price(tp, False)) / 2
                total_value += balances[q] * data_feed_prices[q]
                # Not using base price in data feed because an new / smaller base tokens sometimes don't get
                # included in the price feed
                total_value += balances[b] * base_price * data_feed_prices[q]
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
