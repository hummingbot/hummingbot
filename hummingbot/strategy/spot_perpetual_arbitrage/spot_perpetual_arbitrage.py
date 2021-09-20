from decimal import Decimal
import logging
import asyncio
import pandas as pd
from typing import List, Dict, Tuple
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.event.events import OrderType
from hummingbot.core.event.events import TradeType

from hummingbot.core.event.events import (
    PositionAction,
    PositionSide,
    PositionMode
)
from hummingbot.connector.derivative.position import Position

from .arb_proposal import ArbProposalSide, ArbProposal


NaN = float("nan")
s_decimal_zero = Decimal(0)
spa_logger = None


class SpotPerpetualArbitrageStrategy(StrategyPyBase):
    """
    This strategy arbitrages between a spot and a perpetual exchange connector.
    For a given order amount, the strategy checks the divergence and convergence in prices that could occur
    before and during funding payment on the perpetual exchange.
    If presents, the strategy submits taker orders to both markets.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global spa_logger
        if spa_logger is None:
            spa_logger = logging.getLogger(__name__)
        return spa_logger

    def init_params(self,
                    spot_market_info: MarketTradingPairTuple,
                    perp_market_info: MarketTradingPairTuple,
                    order_amount: Decimal,
                    perp_leverage: int,
                    min_opening_arbitrage_pct: Decimal,
                    min_closing_arbitrage_pct: Decimal,
                    spot_market_slippage_buffer: Decimal = Decimal("0"),
                    perp_market_slippage_buffer: Decimal = Decimal("0"),
                    next_arbitrage_opening_delay: float = 120,
                    status_report_interval: float = 10):
        """
        :param spot_market_info: The spot market info
        :param perp_market_info: The perpetual market info
        :param order_amount: The order amount
        :param min_opening_arbitrage_pct: The minimum spread to open arbitrage position (e.g. 0.0003 for 0.3%)
        :param min_closing_arbitrage_pct: The minimum spread to close arbitrage position (e.g. 0.0003 for 0.3%)
        :param spot_market_slippage_buffer: The buffer for which to adjust order price for higher chance of
        the order getting filled on spot market.
        :param perp_market_slippage_buffer: The slipper buffer for perpetual market.
        """
        self._spot_market_info = spot_market_info
        self._perp_market_info = perp_market_info
        self._min_opening_arbitrage_pct = min_opening_arbitrage_pct
        self._min_closing_arbitrage_pct = min_closing_arbitrage_pct
        self._order_amount = order_amount
        self._perp_leverage = perp_leverage
        self._spot_market_slippage_buffer = spot_market_slippage_buffer
        self._perp_market_slippage_buffer = perp_market_slippage_buffer
        self._next_arbitrage_opening_delay = next_arbitrage_opening_delay
        self._next_arbitrage_opening_ts = 0  # next arbitrage opening timestamp
        self._all_markets_ready = False
        self._ev_loop = asyncio.get_event_loop()
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([spot_market_info.market, perp_market_info.market])

        self._main_task = None
        self._spot_order_ids = []
        self._deriv_order_ids = []

    @property
    def min_opening_arbitrage_pct(self) -> Decimal:
        return self._min_opening_arbitrage_pct

    @property
    def min_closing_arbitrage_pct(self) -> Decimal:
        return self._min_closing_arbitrage_pct

    @property
    def order_amount(self) -> Decimal:
        return self._order_amount

    @order_amount.setter
    def order_amount(self, value):
        self._order_amount = value

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    @property
    def perp_positions(self) -> List[Position]:
        return [s for s in self._perp_market_info.market.account_positions.values() if
                s.trading_pair == self._perp_market_info.trading_pair and s.amount != s_decimal_zero]

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """

        if not self._all_markets_ready:
            self._all_markets_ready = all([market.ready for market in self.active_markets])
            if not self._all_markets_ready:
                # self.logger().warning("Markets are not ready. Please wait...")
                return
            else:
                self.logger().info("Markets are ready.")

                if not self.check_budget_available():
                    self.logger().info("Trading not possible.")
                    return

                self.logger().info("Trading started.")
                if self._perp_market_info.market.position_mode != PositionMode.ONEWAY or \
                        len(self.perp_positions) > 1:
                    self.logger().info("This strategy supports only Oneway position mode. Please update your position "
                                       "mode before starting this strategy.")
                    self.stop(self.clock)
                    return

                if len(self.perp_positions) == 1:
                    if self.perp_positions[0].amount == self._order_amount:
                        self.logger().info(f"There is an existing {self._perp_market_info.trading_pair} "
                                           f"{self.perp_positions[0].position_side.name} position. The bot resumes "
                                           f"operation to close out the arbitrage position")
                    else:
                        self.logger().info(f"There is an existing {self._perp_market_info.trading_pair} "
                                           f"{self.perp_positions[0].position_side.name} position with unmatched "
                                           f"position amount. Please manually close out the position before starting "
                                           f"this strategy.")
                        self.stop(self.clock)
                        return
        if self._main_task is None or self._main_task.done():
            self._main_task = safe_ensure_future(self.main(timestamp))

    async def main(self, timestamp):
        """
        The main procedure for the arbitrage strategy.
        """
        proposals = await self.create_base_proposals()
        is_on_closing = self.is_on_closing_arbitrage()
        if is_on_closing:
            first_perp_side = self.perp_positions[0].position_side
            perp_is_buy = True if first_perp_side == PositionSide.SHORT else False
            proposals = [p for p in proposals if p.perp_side.is_buy == perp_is_buy and p.profit_pct() >=
                         self._min_closing_arbitrage_pct]
        else:
            proposals = [p for p in proposals if p.profit_pct() >= self._min_opening_arbitrage_pct]
        if len(proposals) > 1:
            raise Exception(f"Unexpected situation where number of valid proposals ({len(proposals)}) is > 1")
        if len(proposals) == 0:
            return
        if not self.ready_to_execute_arbitrage_position():
            return
        proposal = proposals[0]
        pos_txt = "closing" if is_on_closing else "opening"
        self.logger().info(f"Arbitrage position {pos_txt} opportunity found.")
        self.logger().info(f"Profitability ({proposal.profit_pct():.2%}) is now above min_{pos_txt}_arbitrage_pct.")
        self.apply_slippage_buffers(proposal)
        if not self.check_budget_constraint(proposal):
            return
        self.execute_arb_proposal(proposal)
        if is_on_closing:
            self._next_arbitrage_opening_ts = self.current_timestamp + self._next_arbitrage_opening_delay

    def is_on_closing_arbitrage(self) -> bool:
        adjusted_perp_amount = self._perp_market_info.market.quantize_order_amount(self._perp_market_info.trading_pair,
                                                                                   self._order_amount)
        if self.perp_positions and self.perp_positions[0].amount == adjusted_perp_amount:
            return True
        return False

    async def create_base_proposals(self) -> List[ArbProposal]:
        tasks = [self._spot_market_info.market.get_order_price(self._spot_market_info.trading_pair, True,
                                                               self._order_amount),
                 self._spot_market_info.market.get_order_price(self._spot_market_info.trading_pair, False,
                                                               self._order_amount),
                 self._perp_market_info.market.get_order_price(self._perp_market_info.trading_pair, True,
                                                               self._order_amount),
                 self._perp_market_info.market.get_order_price(self._perp_market_info.trading_pair, False,
                                                               self._order_amount)]
        prices = await safe_gather(*tasks, return_exceptions=True)
        spot_buy, spot_sell, perp_buy, perp_sell = [*prices]
        return [
            ArbProposal(ArbProposalSide(self._spot_market_info, True, spot_buy),
                        ArbProposalSide(self._perp_market_info, False, perp_sell),
                        self._order_amount),
            ArbProposal(ArbProposalSide(self._spot_market_info, False, spot_sell),
                        ArbProposalSide(self._perp_market_info, True, perp_buy),
                        self._order_amount)
        ]

    # def timed_log(self, timestamp: float, msg: str):
    #     """
    #     Displays log at specific intervals.
    #     :param timestamp: current timestamp
    #     :param msg: message to display at next interval
    #     """
    #     if timestamp - self._last_timestamp > self._status_report_interval:
    #         self.logger().info(msg)
    #         self._last_timestamp = timestamp

    def apply_slippage_buffers(self, proposal: ArbProposal):
        """
        Updates arb_proposals by adjusting order price for slipper buffer percentage.
        E.g. if it is a buy order, for an order price of 100 and 1% slipper buffer, the new order price is 101,
        for a sell order, the new order price is 99.
        :param proposal: the arbitrage proposal
        """
        for arb_side in (proposal.spot_side, proposal.perp_side):
            market = arb_side.market_info.market
            # arb_side.amount = market.quantize_order_amount(arb_side.market_info.trading_pair, arb_side.amount)
            s_buffer = self._spot_market_slippage_buffer if market == self._spot_market_info.market \
                else self._perp_market_slippage_buffer
            if not arb_side.is_buy:
                s_buffer *= Decimal("-1")
            arb_side.order_price *= Decimal("1") + s_buffer
            arb_side.order_price = market.quantize_order_price(arb_side.market_info.trading_pair,
                                                               arb_side.order_price)

    def check_budget_available(self) -> bool:
        """
        Checks if there's any balance for trading to be possible at all
        :return: True if user has available balance enough for orders submission.
        """

        spot_base, spot_quote = self._spot_market_info.trading_pair.split("-")
        perp_base, perp_quote = self._perp_market_info.trading_pair.split("-")

        balance_spot_base = self._spot_market_info.market.get_available_balance(spot_base)
        balance_spot_quote = self._spot_market_info.market.get_available_balance(spot_quote)

        balance_perp_quote = self._perp_market_info.market.get_available_balance(perp_quote)

        if balance_spot_base == s_decimal_zero and balance_spot_quote == s_decimal_zero:
            self.logger().info(f"Cannot arbitrage, {self._spot_market_info.market.display_name} {spot_base} balance "
                               f"({balance_spot_base}) is 0 and {self._spot_market_info.market.display_name} {spot_quote} balance "
                               f"({balance_spot_quote}) is 0.")
            return False

        if balance_perp_quote == s_decimal_zero:
            self.logger().info(f"Cannot arbitrage, {self._perp_market_info.market.display_name} {perp_quote} balance "
                               f"({balance_perp_quote}) is 0.")
            return False

        return True

    def check_budget_constraint(self, proposal: ArbProposal) -> bool:
        """
        Updates arb_proposals by setting proposal amount to 0 if there is not enough balance to submit order with
        required order amount.
        :param proposal: An arbitrage proposal
        :return: True if user has available balance enough for both orders submission.
        """
        spot_side = proposal.spot_side
        spot_token = spot_side.market_info.quote_asset if spot_side.is_buy else spot_side.market_info.base_asset
        spot_avai_bal = spot_side.market_info.market.get_available_balance(spot_token)
        if spot_side.is_buy:
            fee = spot_side.market_info.market.get_fee(
                spot_side.market_info.base_asset,
                spot_side.market_info.quote_asset, OrderType.LIMIT, TradeType.BUY, s_decimal_zero, s_decimal_zero
            )
            spot_required_bal = (proposal.order_amount * proposal.spot_side.order_price) * (Decimal("1") + fee.percent)
        else:
            spot_required_bal = proposal.order_amount
        if spot_avai_bal < spot_required_bal:
            self.logger().info(f"Cannot arbitrage, {spot_side.market_info.market.display_name} {spot_token} balance "
                               f"({spot_avai_bal}) is below required order amount ({spot_required_bal}).")
            return False
        if self.is_on_closing_arbitrage():
            # For perpetual, the collateral in the existing position should be enough to cover the closing call
            return True
        perp_side = proposal.perp_side
        perp_token = perp_side.market_info.quote_asset
        perp_avai_bal = perp_side.market_info.market.get_available_balance(perp_token)
        fee = spot_side.market_info.market.get_fee(
            spot_side.market_info.base_asset,
            spot_side.market_info.quote_asset, OrderType.LIMIT, TradeType.BUY, s_decimal_zero, s_decimal_zero
        )
        pos_size = (proposal.order_amount * proposal.spot_side.order_price)
        perp_required_bal = (pos_size / self._perp_leverage) + (pos_size * fee.percent)
        if perp_avai_bal < perp_required_bal:
            self.logger().info(f"Cannot arbitrage, {perp_side.market_info.market.display_name} {perp_token} balance "
                               f"({perp_avai_bal}) is below required position amount ({perp_required_bal}).")
            return False
        return True

    def execute_arb_proposal(self, proposal: ArbProposal):
        """
        Execute both sides of the arbitrage trades concurrently.
        :param proposal: the arbitrage proposal
        """
        if proposal.order_amount == s_decimal_zero:
            return
        spot_side = proposal.spot_side
        spot_order_fn = self.buy_with_specific_market if spot_side.is_buy else self.sell_with_specific_market
        side = "BUY" if spot_side.is_buy else "SELL"
        self.log_with_clock(
            logging.INFO,
            f"Placing {side} order for {proposal.order_amount} {spot_side.market_info.base_asset} "
            f"at {spot_side.market_info.market.display_name} at {spot_side.order_price} price"
        )
        spot_order_fn(
            spot_side.market_info,
            proposal.order_amount,
            spot_side.market_info.market.get_taker_order_type(),
            spot_side.order_price,
        )
        perp_side = proposal.perp_side
        perp_order_fn = self.buy_with_specific_market if perp_side.is_buy else self.sell_with_specific_market
        side = "BUY" if perp_side.is_buy else "SELL"
        position_action = PositionAction.CLOSE if self.is_on_closing_arbitrage() else PositionAction.OPEN
        self.log_with_clock(
            logging.INFO,
            f"Placing {side} order for {proposal.order_amount} {perp_side.market_info.base_asset} "
            f"at {perp_side.market_info.market.display_name} at {perp_side.order_price} price to "
            f"{position_action.name} position."
        )
        perp_order_fn(
            perp_side.market_info,
            proposal.order_amount,
            perp_side.market_info.market.get_taker_order_type(),
            perp_side.order_price,
            position_action=position_action
        )

    def ready_to_execute_arbitrage_position(self) -> bool:
        """
        Returns True if the strategy is ready to execute arbitrage position or either opening or closing.
        """
        for market_info in [self._spot_market_info, self._perp_market_info]:
            if len(self.market_info_to_active_orders.get(market_info, [])) > 0:
                return False
        if self._next_arbitrage_opening_ts > self.current_timestamp and not self.is_on_closing_arbitrage():
            return False
        return True

    def short_proposal_msg(self, indented: bool = True) -> List[str]:
        """
        Composes a short proposal message.
        :param indented: If the message should be indented (by 4 spaces)
        :return A list of info on both sides of an arbitrage
        """
        lines = []
        proposal = self.current_proposal
        lines.append(f"{'    ' if indented else ''}{proposal.spot_side}")
        lines.append(f"{'    ' if indented else ''}{proposal.derivative_side}")
        return lines

    def spread_msg(self):
        """
        Composes a short spread message.
        :return Info about current spread of an arbitrage
        """
        spread = self.current_proposal.profit_pct()
        first = not bool(len(self.perp_positions))
        target_spread_str = "minimum divergence spread" if first else "minimum convergence spread"
        target_spread = self.min_divergence if first else self.min_convergence
        msg = f"Current spread: {spread:.2%}, {target_spread_str}: {target_spread:.2%}."
        return msg

    def active_positions_df(self) -> pd.DataFrame:
        columns = ["Symbol", "Type", "Entry Price", "Amount", "Leverage", "Unrealized PnL"]
        data = []
        for idx in self.perp_positions:
            unrealized_profit = ((self.current_proposal.derivative_side.order_price - idx.entry_price) * idx.amount)
            data.append([
                idx.trading_pair,
                idx.position_side.name,
                idx.entry_price,
                idx.amount,
                idx.leverage,
                unrealized_profit
            ])

        return pd.DataFrame(data=data, columns=columns)

    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: markets,
        assets, spread and warnings(if any).
        """
        columns = ["Exchange", "Market", "Sell Price", "Buy Price", "Mid Price"]
        data = []
        for market_info in [self._spot_market_info, self._perp_market_info]:
            market, trading_pair, base_asset, quote_asset = market_info
            buy_price = await market.get_quote_price(trading_pair, True, self._order_amount)
            sell_price = await market.get_quote_price(trading_pair, False, self._order_amount)
            mid_price = (buy_price + sell_price) / 2
            data.append([
                market.display_name,
                trading_pair,
                float(sell_price),
                float(buy_price),
                float(mid_price)
            ])
        markets_df = pd.DataFrame(data=data, columns=columns)
        lines = []
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        # See if there're any active positions.
        if len(self.perp_positions) > 0:
            df = self.active_positions_df()
            lines.extend(["", "  Positions:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active positions."])

        assets_df = self.wallet_balance_data_frame([self._spot_market_info, self._perp_market_info])
        lines.extend(["", "  Assets:"] +
                     ["    " + line for line in str(assets_df).split("\n")])

        try:
            lines.extend(["", "  Spread details:"] + ["    " + self.spread_msg()] +
                         self.short_proposal_msg())
        except Exception:
            pass

        warning_lines = self.network_warning([self._spot_market_info])
        warning_lines.extend(self.network_warning([self._perp_market_info]))
        warning_lines.extend(self.balance_warning([self._spot_market_info]))
        warning_lines.extend(self.balance_warning([self._perp_market_info]))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    @property
    def tracked_market_orders(self) -> List[Tuple[ConnectorBase, MarketOrder]]:
        return self._sb_order_tracker.tracked_market_orders

    @property
    def tracked_limit_orders(self) -> List[Tuple[ConnectorBase, LimitOrder]]:
        return self._sb_order_tracker.tracked_limit_orders

    def start(self, clock: Clock, timestamp: float):
        pass

    def stop(self, clock: Clock):
        if self._main_task is not None:
            self._main_task.cancel()
            self._main_task = None
