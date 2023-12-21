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
                 min_amount: Decimal,
                 max_amount: Decimal,
                 min_profitability: Decimal,
                 status_report_interval: float = 900):
        super().__init__()
        self._market_info = market_info
        self._fee_tier = fee_tier
        self._price_spread = price_spread
        self._min_amount = min_amount
        self._max_amount = max_amount
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
        return [pos for pos in self._market_info.market.amm_lp_orders if
                pos.is_nft and pos.trading_pair == self.trading_pair]

    @property
    def active_orders(self):
        return [pos for pos in self._market_info.market.amm_lp_orders if
                not pos.is_nft and pos.trading_pair == self.trading_pair]

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
                    f"{self.get_position_status_by_price_range(self._last_price, position, Decimal(0.5))}",
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
            lines.extend(
                ["", "  Positions:"] + ["    " + line for line in pos_info_df.to_string(index=False).split("\n")])
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
                await self.execute_proposal(lower_price, upper_price)
                self.close_matured_positions()

    def any_active_position(self, current_price: Decimal, buffer_spread: Decimal = Decimal("0")) -> bool:
        """
        We use this to know if any existing position is in-range.
        :return: True/False
        """
        for position in self.active_positions:
            if ((position.lower_price * (Decimal("1") - (buffer_spread / 100))) <= current_price <=
                    (position.upper_price * (Decimal("1") + (buffer_spread / 100)))):
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
            if not self.any_active_position(Decimal(current_price),
                                            Decimal("0.5")):  # only set prices if there's no active position
                half_spread = self._price_spread / Decimal("2")
                lower_price = (current_price * (Decimal("1") - half_spread))
                upper_price = (current_price * (Decimal("1") + half_spread))
        lower_price = max(s_decimal_0, lower_price)
        return lower_price, upper_price

    async def execute_proposal(self, lower_price: Decimal, upper_price: Decimal):
        """
        This execute proposal generated earlier by propose_position_boundary function.
        :param lower_price: lower price for position to be created
        :param upper_price: upper price for position to be created
        """
        await self._market_info.market._update_balances()  # this is to ensure that we have the latest balances

        base_balance = self._market_info.market.get_available_balance(self.base_asset)
        quote_balance = self._market_info.market.get_available_balance(self.quote_asset)

        proposed_lower_price = lower_price
        proposed_upper_price = upper_price

        # Make sure we don't create position with too little amount of base asset
        if base_balance < self._min_amount:
            base_balance = s_decimal_0
            proposed_upper_price = self._last_price * (Decimal("1") - Decimal("0.1") / 100)

        # Make sure we don't create position with too little amount of quote asset
        if (quote_balance * self._last_price) < self._min_amount:
            quote_balance = s_decimal_0
            proposed_lower_price = self._last_price * (Decimal("1") + Decimal("0.1") / 100)

        if base_balance + quote_balance == s_decimal_0:
            self.log_with_clock(logging.INFO,
                                "Both balances exhausted. Add more assets.")
        else:
            self.log_with_clock(logging.INFO, f"Creating new position over {lower_price} to {upper_price} price range.")
            self.log_with_clock(logging.INFO, f"Base balance: {base_balance}, quote balance: {quote_balance}")
            self._market_info.market.add_liquidity(self.trading_pair,
                                                   min(base_balance, self._max_amount),
                                                   min(quote_balance, (self._max_amount * self._last_price)),
                                                   proposed_lower_price,
                                                   proposed_upper_price,
                                                   self._fee_tier)

    def close_matured_positions(self):
        """
        This closes out-of-range positions that have more than the min profitability.
        """
        for position in self.active_positions:
            if self._last_price <= position.lower_price or self._last_price >= position.upper_price:  # out-of-range
                if position.unclaimed_fee_0 + (
                        position.unclaimed_fee_1 / self._last_price) > self._min_profitability:  # matured
                    self.log_with_clock(logging.INFO,
                                        f"Closing position with Id {position.token_id} (Matured position)."
                                        f"Unclaimed base fee: {position.unclaimed_fee_0}, unclaimed quote fee: {position.unclaimed_fee_1}")
                    self._market_info.market.remove_liquidity(self.trading_pair, position.token_id)
                else:
                    self.close_out_of_buffered_range_position(position, Decimal("0.5"))

    def close_out_of_buffered_range_position(self, position: any, buffer_spread: Decimal = None):
        """
        This closes out-of-range positions that are too far from last price.
        """
        if self._last_price <= (
                position.lower_price * (Decimal("1") - (buffer_spread / 100))) or self._last_price >= (
                position.upper_price * (Decimal("1") + (buffer_spread / 100))):  # out-of-range
            self.log_with_clock(logging.INFO,
                                f"Closing position with Id {position.token_id} (Out of range)."
                                f"Unclaimed base fee: {position.unclaimed_fee_0}, unclaimed quote fee: {position.unclaimed_fee_1}")
            self._market_info.market.remove_liquidity(self.trading_pair, position.token_id)

    def get_position_status_by_price_range(self, last_price: Decimal, position: any, buffer_spread: Decimal = None):
        """
        This returns the status of a position based on last price and buffer spread.
        There are 3 possible statuses: In range, In buffered range, Out of range.
        """
        if position.lower_price <= last_price <= position.upper_price:
            return "[In range]"
        elif ((position.lower_price * (Decimal("1") - (buffer_spread / 100))) <= last_price <=
              (position.upper_price * (Decimal("1") + (buffer_spread / 100)))):
            return "[In buffered range]"
        else:
            return "[Out of range]"

    def stop(self, clock: Clock):
        if self._main_task is not None:
            self._main_task.cancel()
            self._main_task = None
