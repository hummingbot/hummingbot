from decimal import Decimal
import logging
import asyncio
import pandas as pd
import numpy as np
from hummingbot.core.clock import Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.connector.connector.uniswap_v3.uniswap_v3_in_flight_position import UniswapV3InFlightPosition
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from ..__utils__.trailing_indicators.historical_volatility import HistoricalVolatilityIndicator

ulp_logger = None
s_decimal_0 = Decimal("0")


class UniswapV3LpStrategy(StrategyPyBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ulp_logger
        if ulp_logger is None:
            ulp_logger = logging.getLogger(__name__)
        return ulp_logger

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 fee_tier: str,
                 use_volatility: bool,
                 volatility_period: int,
                 volatility_factor: Decimal,
                 buy_spread: Decimal,
                 sell_spread: Decimal,
                 base_token_amount: Decimal,
                 quote_token_amount: Decimal,
                 min_profitability: Decimal,
                 status_report_interval: float = 900):
        super().__init__()
        self._market_info = market_info
        self._fee_tier = fee_tier
        self._use_volatility = use_volatility
        self._volatility_period = volatility_period
        self._volatility_factor = volatility_factor
        self._buy_spread = buy_spread
        self._sell_spread = sell_spread
        self._base_token_amount = base_token_amount
        self._quote_token_amount = quote_token_amount
        self._min_profitability = min_profitability

        self._ev_loop = asyncio.get_event_loop()
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([market_info.market])
        self._connector_ready = False
        self._last_price = s_decimal_0
        self._volatility = HistoricalVolatilityIndicator(3600, 1)
        self._main_task = None
        self._fetch_prices_task = None
        self._next_price_fetch = 0

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
    def active_buys(self):
        return [buy for buy in self.active_positions if buy.upper_price <= self._last_price]

    @property
    def active_sells(self):
        return [sell for sell in self.active_positions if sell.upper_price >= self._last_price]

    @property
    def active_positions(self):
        return [pos for pos in self._market_info.market._in_flight_positions.values() if pos.trading_pair == self.trading_pair]

    @property
    def active_orders(self):
        return self._market_info.market._in_flight_orders.values()

    async def get_current_price(self, update_volatility: bool = False) -> float:
        if update_volatility:
            prices = await self._market_info.market.get_price_by_fee_tier(self.trading_pair, self._fee_tier, 3600, True)
            for price in prices:
                self._volatility.add_sample(float(price))
        else:
            price = await self._market_info.market.get_price_by_fee_tier(self.trading_pair, self._fee_tier)
        return Decimal(prices[-1]) if update_volatility else Decimal(price)

    def active_positions_df(self) -> pd.DataFrame:
        columns = ["Id", "Symbol", "Fee Tier", "Range", "Current Base", "Current Quote", ""]
        data = []
        if len(self.active_positions) > 0:
            for position in self.active_positions:
                data.append([
                    position.token_id,
                    position.trading_pair,
                    position.fee_tier,
                    f"{PerformanceMetrics.smart_round(position.lower_price, 8)} - "
                    f"{PerformanceMetrics.smart_round(position.upper_price, 8)}",
                    PerformanceMetrics.smart_round(position.current_base_amount, 8),
                    PerformanceMetrics.smart_round(position.current_quote_amount, 8),
                    "[In range]" if self._last_price >= position.lower_price and self._last_price <= position.upper_price else "[Out of range]"
                ])
        return pd.DataFrame(data=data, columns=columns)

    def calculate_volatility(self):
        """
        This function returns the current volatility.
        """
        current_volatility = Decimal(str(self._volatility.current_value)) if self._volatility.current_value else s_decimal_0
        return (self._volatility_factor * Decimal(str(np.sqrt(self._volatility_period * Decimal("3600")))) * current_volatility)

    async def calculate_profitability(self, position: UniswapV3InFlightPosition):
        """
        Does simple computation and returns a dictionary containing data required by other functions.
        :param position: an instance of UniswapV3InFlightPosition
        :return {}: dictionaty containing "base_change", "quote_change", "base_fee", "quote_fee"
                    "tx_fee", "profitability".
        """
        base_tkn, quote_tkn = position.trading_pair.split("-")
        init_base = position.base_amount
        init_quote = position.quote_amount
        base_change = position.current_base_amount - position.base_amount
        quote_change = position.current_quote_amount - position.quote_amount
        base_fee = position.unclaimed_base_amount
        quote_fee = position.unclaimed_quote_amount
        if len(position.tx_fees) < 2 or position.tx_fees[-1] == s_decimal_0:
            remove_lp_fee = await self._market_info.market._remove_position(position.hb_id, position.token_id, Decimal("100.0"), True)
            remove_lp_fee = remove_lp_fee if remove_lp_fee is not None else s_decimal_0
            position.tx_fees.append(remove_lp_fee)
        if quote_tkn != "WETH":
            fee_rate = RateOracle.get_instance().rate(f"ETH-{quote_tkn}")
            if fee_rate:
                tx_fee = sum(position.tx_fees) * fee_rate
            else:  # cases like this would be rare
                tx_fee = sum(position.tx_fees)
        else:
            tx_fee = sum(position.tx_fees)
        init_value = (init_base * self._last_price) + init_quote
        profitability = s_decimal_0 if init_value == s_decimal_0 else \
            ((((base_change + base_fee) * self._last_price) + quote_change + quote_fee - tx_fee) / init_value)
        return {"base_change": base_change,
                "quote_change": quote_change,
                "base_fee": base_fee,
                "quote_fee": quote_fee,
                "tx_fee": tx_fee,
                "profitability": profitability
                }

    async def profitability_df(self):
        data = []
        columns = ["Id", f"{self.base_asset} Change", f"{self.quote_asset} Change",
                   f"Unclaimed {self.base_asset}", f"Unclaimed {self.quote_asset}", "Total Profit/loss (%)"]
        for position in self.active_positions:
            profit_data = await self.calculate_profitability(position)
            data.append([position.token_id,
                        PerformanceMetrics.smart_round(profit_data['base_change'], 8),
                        PerformanceMetrics.smart_round(profit_data['quote_change'], 8),
                        PerformanceMetrics.smart_round(profit_data['base_fee'], 8),
                        PerformanceMetrics.smart_round(profit_data['quote_fee'], 8),
                        PerformanceMetrics.smart_round(profit_data['profitability'], 8)])
        return pd.DataFrame(data=data, columns=columns)

    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: market,
        assets, spread and warnings(if any).
        """
        if not self._connector_ready:
            return "UniswapV3 connector not ready."

        columns = ["Exchange", "Market", "Current Price"]
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

            pos_profitability_df = await self.profitability_df()
            lines.extend(["", "  Positions Performance:"] + ["    " + line for line in pos_profitability_df.to_string(index=False).split("\n")])
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
                self.logger().warning("Uniswap v3 connector is not ready. Please wait...")
                return
            else:
                if self._market_info.market._trading_pairs[0] != self.trading_pair:
                    self.logger().info(f"Market should be {self._market_info.market._trading_pairs[0]}"
                                       f" not {self.trading_pair}. Update config accordingly and restart strategy.")
                    self._connector_ready = False
                    return
                self.logger().info("Uniswap v3 connector is ready. Trading started.")

        if timestamp > self._next_price_fetch and self._use_volatility:
            if not self._fetch_prices_task:
                self._fetch_prices_task = safe_ensure_future(self.get_current_price(True))
            elif self._fetch_prices_task.done():
                self.logger().info(f"New volatility for {self._volatility_period} hours: {self.calculate_volatility()}")
                self._next_price_fetch = timestamp + 3600
                self._fetch_prices_task = None
            else:
                return

        if self._main_task is None or self._main_task.done():
            self._main_task = safe_ensure_future(self.main())

    async def main(self):
        pending_positions = [position.last_status.is_pending() for position in self.active_positions]
        if not any(pending_positions) and len(self.active_orders) == 0:
            # Then we proceed with creating new position if necessary
            proposal = await self.propose_position_creation()
            if len(proposal) > 0:
                self.execute_proposal(proposal)

    def generate_proposal(self, is_buy):
        """
        We use this to generate range for positions.
        :param is_buy: True is position range goes below current price, else False
        :return: [lower_price, upper_price]
        """
        volatility = self.calculate_volatility() if self._use_volatility else s_decimal_0
        if is_buy:
            buy_spread = volatility if volatility != s_decimal_0 else self._buy_spread
            upper_price = self._last_price
            lower_price = max(s_decimal_0, (Decimal("1") - buy_spread) * self._last_price)
        else:
            sell_spread = volatility if volatility != s_decimal_0 else self._sell_spread
            lower_price = self._last_price
            upper_price = (Decimal("1") + sell_spread) * self._last_price
        return [lower_price, upper_price]

    def total_position_range(self):
        """
        We use this to know the overall range all active lp orders cover.
        :return: lower_bound, upper_bound
        """
        lower_bound = s_decimal_0
        upper_bound = s_decimal_0

        for position in self.active_positions:
            if lower_bound == s_decimal_0 or position.lower_price < lower_bound:
                lower_bound = position.lower_price
            if position.upper_price > upper_bound:
                upper_bound = position.upper_price

        return lower_bound, upper_bound

    async def propose_position_creation(self):
        """
        We use this to create proposal for new range positions
        :return : [buy_prices, sell_prices]
        """
        buy_prices = sell_prices = []  # [lower_price, upper_price]

        current_price = await self.get_current_price()

        current_strategy_range = self.total_position_range()

        while not self._volatility.is_sampling_buffer_full and self._use_volatility:
            await self.get_current_price(True)

        if self._last_price != current_price and current_price != s_decimal_0:
            self._last_price = current_price

            if current_strategy_range[0] == s_decimal_0 or self._last_price < current_strategy_range[0]:
                buy_prices = self.generate_proposal(True)

            if current_strategy_range[1] == s_decimal_0 or self._last_price > current_strategy_range[1]:
                sell_prices = self.generate_proposal(False)

            if self._use_volatility and self.calculate_volatility() == s_decimal_0:
                self.logger().info("Unable to use price volatility to set spreads because volatility in last hour is zero."
                                   " Using set spreads.")

        return [buy_prices, sell_prices]

    def execute_proposal(self, proposal):
        """
        This execute proposal generated earlier by propose_position_creation function.
        :param proposal: [buy_prices, sell_prices]
        """
        base_balance = self._market_info.market.get_available_balance(self.base_asset)
        quote_balance = self._market_info.market.get_available_balance(self.quote_asset)
        if len(proposal[0]) > 0:
            if quote_balance < self._quote_token_amount:
                self.log_with_clock(logging.INFO,
                                    f"Insufficient {self.quote_asset}  asset to create new range position."
                                    f"Required: {self._quote_token_amount} {self.quote_asset}, Available: {quote_balance} {self.quote_asset}. ")
            else:
                self.log_with_clock(logging.INFO, f"Creating new buy position over {proposal[0][0]} to {proposal[0][1]} price range.")
                self._market_info.market.add_position(self.trading_pair,
                                                      self._fee_tier,
                                                      self._base_token_amount,
                                                      self._quote_token_amount,
                                                      proposal[0][0],
                                                      proposal[0][1])
        if len(proposal[1]) > 0:
            if base_balance < (self._base_token_amount):
                self.log_with_clock(logging.INFO,
                                    f"Insufficient {self.base_asset} asset to create new range position."
                                    f"Required: {self._base_token_amount} {self.base_asset}, Available: {base_balance} {self.base_asset}. ")
            else:
                self.log_with_clock(logging.INFO, f"Creating new sell position over {proposal[1][0]} to {proposal[1][1]} price range.")
                self._market_info.market.add_position(self.trading_pair,
                                                      self._fee_tier,
                                                      self._base_token_amount,
                                                      self._quote_token_amount,
                                                      proposal[1][0],
                                                      proposal[1][1])

    def stop(self, clock: Clock):
        if self._main_task is not None:
            self._main_task.cancel()
            self._main_task = None
