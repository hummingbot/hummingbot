from decimal import Decimal
import logging
import asyncio
import pandas as pd
from hummingbot.core.clock import Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.client.performance import smart_round
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.core.utils.async_utils import safe_ensure_future

ulp_logger = None


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
                 buy_position_price_spread: Decimal,
                 sell_position_price_spread: Decimal,
                 base_token_amount: Decimal,
                 quote_token_amount: Decimal,
                 status_report_interval: float = 900):
        super().__init__()
        self._market_info = market_info
        self._fee_tier = fee_tier
        self._buy_position_price_spread = buy_position_price_spread
        self._sell_position_price_spread = sell_position_price_spread
        self._base_token_amount = base_token_amount
        self._quote_token_amount = quote_token_amount

        self._ev_loop = asyncio.get_event_loop()
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([market_info.market])
        self._connector_ready = False
        self._last_price = Decimal("0")
        self._main_task = None

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

    async def get_current_price(self) -> float:
        return await self._market_info.market.get_price_by_fee_tier(self.trading_pair, self._fee_tier)

    def active_positions_df(self) -> pd.DataFrame:
        columns = ["Symbol", "Type", "Fee Tier", "Amount", "Upper Price", "Lower Price", ""]
        data = []
        if len(self.active_positions) > 0:
            for position in self.active_positions:
                amount = self._base_token_amount if position in self.active_buys else self._quote_token_amount
                data.append([
                    position.trading_pair,
                    "Buy" if position in self.active_buys else "Sell",
                    position.fee_tier,
                    f"{smart_round(Decimal(str(amount)), 8)}",
                    smart_round(Decimal(str(position.upper_price)), 8),
                    smart_round(Decimal(str(position.lower_price)), 8),
                    "[In range]" if self._last_price >= position.lower_price and self._last_price <= position.upper_price else "[Out of range]"
                ])
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
            smart_round(Decimal(str(self._last_price)), 8)
        ])
        markets_df = pd.DataFrame(data=data, columns=columns)
        lines = []
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        # See if there're any active positions.
        if len(self.active_positions) > 0:
            df = self.active_positions_df()
            lines.extend(["", "  Positions:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
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
                self.logger().info("Uniswap v3 connector is ready. Trading started.")
        if self._main_task is None or self._main_task.done():
            self._main_task = safe_ensure_future(self.main())

    async def main(self):
        pending_positions = [position.last_status.is_pending() for position in self.active_positions]
        if not any(pending_positions) and len(self.active_orders) == 0:
            proposal = await self.propose_position_creation_and_removal()
            if len(proposal) > 0:
                await self.execute_proposal(proposal)

    def generate_proposal(self, is_buy):
        if is_buy:
            upper_price = self._last_price
            lower_price = (Decimal("1") - self._buy_position_price_spread) * self._last_price
        else:
            lower_price = self._last_price
            upper_price = (Decimal("1") + self._sell_position_price_spread) * self._last_price
        return [lower_price, upper_price]

    def in_range_sell(self):
        """
        We use this to know if there is any sell position that is in range.
        """
        for sell in self.active_sells:
            if sell.upper_price > self._last_price and sell.lower_price < self._last_price:
                return True
        return False

    async def propose_position_creation_and_removal(self):
        buy_prices = sell_prices = []  # [lower_price, upper_price, token_id(to be removed)]
        current_price = await self.get_current_price()
        if self._last_price != current_price or len(self.active_buys) == 0 or len(self.active_sells) == 0:
            if current_price != Decimal("0"):
                self._last_price = current_price
            if (not self.in_range_sell() and len(self.active_buys) == 0) or \
               (self.in_range_sell() and len(self.active_sells) == 1 and len(self.active_buys) == 0):
                buy_prices = self.generate_proposal(True)
                if len(self.active_sells) <= 1:
                    buy_prices.append(0)
                elif len(self.active_sells) > 1:
                    # we remove the farthest sell position
                    sell_id = self.active_sells[0] if self.active_sells[0].upper_price > self.active_sells[1].upper_price \
                        else self.active_sells[1]
                    buy_prices.append(sell_id)
            if len(self.active_sells) == 0:
                sell_prices = self.generate_proposal(False)
                if len(self.active_buys) <= 1:
                    sell_prices.append(0)
                elif len(self.active_buys) > 1:
                    # we remove the farthest buy position
                    buy_id = self.active_buys[0] if self.active_buys[0].lower_price < self.active_buys[1].lower_price \
                        else self.active_buys[1]
                    sell_prices.append(buy_id)
        return [buy_prices, sell_prices]

    async def execute_proposal(self, proposal):
        base_balance = self._market_info.market.get_available_balance(self.base_asset)
        quote_balance = self._market_info.market.get_available_balance(self.quote_asset)
        if len(proposal[0]) > 0:
            if proposal[0][-1] != 0:  # close sell position first
                self.log_with_clock(logging.INFO, f"Removing position with ID - {proposal[0][-1].token_id}")
                self._market_info.market.remove_position(proposal[0][-1].hb_id, proposal[0][-1].token_id)
            if quote_balance < self._quote_token_amount:
                self.log_with_clock(logging.INFO,
                                    f"Executing sell order for {self._quote_token_amount} {self._market_info.quote_asset} "
                                    f"at {self._last_price} price so as to have enough balance to place buy position.")
                self.sell_with_specific_market(self._market_info,
                                               self._quote_token_amount,
                                               self._market_info.market.get_taker_order_type(),
                                               self._last_price,
                                               )
            self.log_with_clock(logging.INFO, f"Creating new buy position over {proposal[0][0]} to {proposal[0][1]} price range.")
            self._market_info.market.add_position(self.trading_pair,
                                                  self._fee_tier,
                                                  self._base_token_amount,
                                                  self._quote_token_amount,
                                                  proposal[0][0],
                                                  proposal[0][1])
        if len(proposal[1]) > 0:
            if proposal[1][-1] != 0:  # close buy position first
                self.log_with_clock(logging.INFO, f"Removing position with ID - {proposal[1][-1].token_id}")
                self._market_info.market.remove_position(proposal[1][-1].hb_id, proposal[1][-1].token_id)
            if base_balance < (self._base_token_amount):
                self.log_with_clock(logging.INFO,
                                    f"Executing buy order for {self._base_token_amount} {self._market_info.base_asset} "
                                    f"at {self._last_price} price so as to have enough balance to place sell position.")
                self.buy_with_specific_market(self._market_info,
                                              self._base_token_amount,
                                              self._market_info.market.get_taker_order_type(),
                                              self._last_price,
                                              )
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
