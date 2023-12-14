import asyncio
import logging
from decimal import Decimal

import pandas as pd

from hummingbot.client.performance import PerformanceMetrics
from hummingbot.core.clock import Clock
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

ulp_logger = None
s_decimal_0 = Decimal("0")


class AmmV3LpStrategy(StrategyPyBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ulp_logger
        if ulp_logger is None:
            ulp_logger = logging.getLogger(__name__)
        return ulp_logger

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 fee_tier: str,
                 price_spread: Decimal,
                 amount: Decimal,
                 min_profitability: Decimal,
                 status_report_interval: float = 900):
        super().__init__()
        self._market_info = market_info
        self._fee_tier = fee_tier
        self._price_spread = price_spread
        self._amount = amount
        self._min_profitability = min_profitability

        self._ev_loop = asyncio.get_event_loop()
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([market_info.market])
        self._connector_ready = False
        self._last_price = s_decimal_0
        self._main_task = None
        self._fetch_prices_task = None

    @property
    def connector_name(self):
        return self._market_info.market.display_name

    @property
    def base_asset(self):
        return self._market_info.base_asset

    @property
    def quote_asset(self):
        return self._market_info.quote_asset

    @property
    def trading_pair(self):
        return self._market_info.trading_pair

    @property
    def active_positions(self):
        return [pos for pos in self._market_info.market.amm_lp_orders if pos.is_nft and pos.trading_pair == self.trading_pair]

    @property
    def active_orders(self):
        return [pos for pos in self._market_info.market.amm_lp_orders if not pos.is_nft and pos.trading_pair == self.trading_pair]

    async def get_pool_price(self, update_volatility: bool = False) -> float:
        prices = await self._market_info.market.get_price(self.trading_pair, self._fee_tier)
        if prices:
            return Decimal(prices[-1])
        else:
            return s_decimal_0

    def active_positions_df(self) -> pd.DataFrame:
        columns = ["Id", "Fee Tier", "Symbol", "Price Range", "Base/Quote Amount", "Unclaimed Base/Quote Fees", ""]
        data = []
        if len(self.active_positions) > 0:
            for position in self.active_positions:
                data.append([
                    position.token_id,
                    position.fee_tier,
                    position.trading_pair,
                    f"{PerformanceMetrics.smart_round(position.adjusted_lower_price, 8)} - "
                    f"{PerformanceMetrics.smart_round(position.adjusted_upper_price, 8)}",
                    f"{PerformanceMetrics.smart_round(position.amount_0, 8)} / "
                    f"{PerformanceMetrics.smart_round(position.amount_1, 8)}",
                    f"{PerformanceMetrics.smart_round(position.unclaimed_fee_0, 8)} / "
                    f"{PerformanceMetrics.smart_round(position.unclaimed_fee_1, 8)}",
                    "[In range]" if self._last_price >= position.adjusted_lower_price and self._last_price <= position.adjusted_upper_price else "[Out of range]"
                ])
        return pd.DataFrame(data=data, columns=columns)

    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: market,
        assets, spread and warnings(if any).
        """
        if not self._connector_ready:
            return f"{self.connector_name} connector not ready."

        columns = ["Exchange", "Market", "Pool Price"]
        data = []
        market, trading_pair, base_asset, quote_asset = self._market_info
        data.append([
            market.display_name,
            trading_pair,
            PerformanceMetrics.smart_round(Decimal(str(self._last_price)), 8)
        ])
        markets_df = pd.DataFrame(data=data, columns=columns)
        lines = []
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        # See if there're any active positions.
        if len(self.active_positions) > 0:
            pos_info_df = self.active_positions_df()
            lines.extend(["", "  Positions:"] + ["    " + line for line in pos_info_df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active positions."])

        assets_df = self.wallet_balance_data_frame([self._market_info])
        lines.extend(["", "  Assets:"] +
                     ["    " + line for line in str(assets_df).split("\n")])

        warning_lines = self.network_warning([self._market_info])
        warning_lines.extend(self.balance_warning([self._market_info]))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self._connector_ready:
            self._connector_ready = self._market_info.market.ready
            if not self._connector_ready:
                self.logger().warning(f"{self.connector_name} connector is not ready. Please wait...")
                return
            else:
                self.logger().info(f"{self.connector_name} connector is ready. Trading started.")

        if self._main_task is None or self._main_task.done():
            self._main_task = safe_ensure_future(self.main())

    async def main(self):
        if len(self.active_orders) == 0:  # this ensures that there'll always be one lp order per time
            lower_price, upper_price = await self.propose_position_boundary()
            if lower_price + upper_price != s_decimal_0:
                self.execute_proposal(lower_price, upper_price)
                self.close_matured_positions()

    def any_active_position(self, current_price: Decimal):
        """
        We use this to know if any existing position is in-range.
        :return: True/False
        """
        for position in self.active_positions:
            if current_price >= position.lower_price and current_price <= position.upper_price:
                return True
        return False

    async def propose_position_boundary(self):
        """
        We use this to create proposal for new range positions
        :return : lower_price, upper_price
        """
        lower_price = s_decimal_0
        upper_price = s_decimal_0
        current_price = await self.get_pool_price()

        if current_price != s_decimal_0:
            self._last_price = current_price
            if not self.any_active_position(current_price):  # only set prices if there's no active position
                half_spread = self._price_spread / Decimal("2")
                lower_price = (current_price * (Decimal("1") - half_spread))
                upper_price = (current_price * (Decimal("1") + half_spread))
        lower_price = max(s_decimal_0, lower_price)
        return lower_price, upper_price

    def execute_proposal(self, lower_price: Decimal, upper_price: Decimal):
        """
        This execute proposal generated earlier by propose_position_boundary function.
        :param lower_price: lower price for position to be created
        :param upper_price: upper price for position to be created
        """
        base_balance = self._market_info.market.get_available_balance(self.base_asset)
        quote_balance = self._market_info.market.get_available_balance(self.quote_asset)
        if base_balance + quote_balance == s_decimal_0:
            self.log_with_clock(logging.INFO,
                                "Both balances exhausted. Add more assets.")
        else:
            self.log_with_clock(logging.INFO, f"Creating new position over {lower_price} to {upper_price} price range.")
            self._market_info.market.add_liquidity(self.trading_pair,
                                                   min(base_balance, self._amount),
                                                   min(quote_balance, (self._amount * self._last_price)),
                                                   lower_price,
                                                   upper_price,
                                                   self._fee_tier)

    def close_matured_positions(self):
        """
        This closes out-of-range positions that have more than the min profitability.
        """
        for position in self.active_positions:
            if self._last_price <= position.lower_price or self._last_price >= position.upper_price:  # out-of-range
                if position.unclaimed_fee_0 + (position.unclaimed_fee_1 / self._last_price) > self._min_profitability:  # matured
                    self.log_with_clock(logging.INFO,
                                        f"Closing position with Id {position.token_id}."
                                        f"Unclaimed base fee: {position.unclaimed_fee_0}, unclaimed quote fee: {position.unclaimed_fee_1}")
                    self._market_info.market.remove_liquidity(self.trading_pair, position.token_id)

    def stop(self, clock: Clock):
        if self._main_task is not None:
            self._main_task.cancel()
            self._main_task = None
