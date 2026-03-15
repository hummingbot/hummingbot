import logging
from decimal import Decimal
from typing import Callable

from hummingbot.logger import HummingbotLogger
from hummingbot.strategy_v2.executors.progressive_executor.data_types import LadderedTrailingStop


class TrailingStopManager:
    """
    Controller class for managing trailing stops.
    Can be used by any executor that needs trailing stop functionality.

    Trailing stops are activated when the net PnL percentage exceeds the activation threshold.
    When the net PnL percentage drops below the trigger threshold, the trailing stop is triggered.
    The trailing stop can be configured to take profits at certain PnL levels.
    """

    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
            self,
            trailing_stop_config: LadderedTrailingStop,
            pnl_relaxation: Decimal = Decimal("0.9"),
            max_trailing_pct: Decimal = Decimal("0.05"),
    ):
        self._config: LadderedTrailingStop = trailing_stop_config
        self._pnl_relaxation: Decimal = pnl_relaxation
        self._max_trailing_pct: Decimal = max_trailing_pct

        self._pnl_trigger: Decimal | None = None

    @property
    def pnl_trigger(self) -> Decimal | None:
        return self._pnl_trigger

    def update(
            self,
            net_pnl_pct: Decimal,
            current_amount: Decimal,
            on_close_position: Callable,
            on_partial_close: Callable,
    ) -> None:
        assert current_amount > 0, f"Current amount must be positive: {current_amount} <= 0"
        self.logger().debug(f"Updating trailing stop with net PnL percentage {net_pnl_pct}")

        trailing_pct = self._calculate_trailing_percentage(net_pnl_pct)
        if self._pnl_trigger is None:
            if net_pnl_pct >= self._config.activation_pnl_pct:
                self.logger().debug(f"Trailing stop activated at {net_pnl_pct} > {self._config.activation_pnl_pct}.")
                self._pnl_trigger = net_pnl_pct - trailing_pct
            return

        if (updated_trigger := net_pnl_pct - trailing_pct) > self._pnl_trigger:
            self._pnl_trigger = updated_trigger
            return

        if net_pnl_pct <= self._pnl_trigger:
            self._handle_stop_trigger(net_pnl_pct, current_amount, on_close_position, on_partial_close)
            self._pnl_trigger = net_pnl_pct - trailing_pct

    def _calculate_trailing_percentage(self, net_pnl_pct: Decimal) -> Decimal:
        base_trailing = self._config.trailing_pct
        extra_trailing = net_pnl_pct * self._pnl_relaxation if net_pnl_pct > base_trailing else Decimal("0")

        return min(
            base_trailing + extra_trailing,
            self._max_trailing_pct
        )

    def _handle_stop_trigger(
            self,
            net_pnl_pct: Decimal,
            current_amount: Decimal,
            on_close_position: Callable,
            on_partial_close: Callable,
    ) -> None:
        closest_take_profit = max(
            filter(lambda x: x[0] <= net_pnl_pct, self._config.take_profit_table),
            key=lambda x: x[0],
            default=(Decimal("0"), Decimal("1"))
        )
        close_ratio = closest_take_profit[1]

        if close_ratio == Decimal("1"):
            self.logger().debug(f"Trailing stop triggered at {net_pnl_pct}. Closing position.")
            on_close_position()
        else:
            self.logger().debug(f"Trailing stop triggered at {net_pnl_pct}. Closing {close_ratio} of the position.")
            on_partial_close(current_amount * close_ratio)

    def _find_closest_take_profit(self, net_pnl_pct: Decimal) -> tuple[Decimal, Decimal]:
        return max(
            filter(lambda x: x[0] <= net_pnl_pct, self._config.take_profit_table),
            key=lambda x: x[0],
            default=(Decimal("0"), Decimal("1"))
        )
