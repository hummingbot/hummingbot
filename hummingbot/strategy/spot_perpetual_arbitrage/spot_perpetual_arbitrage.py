from decimal import Decimal
import time
import logging
import asyncio
import pandas as pd
from typing import List, Dict, Tuple, Union
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.event.events import FundingInfo

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
    If presents, the strategy submits taker orders to both market.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global spa_logger
        if spa_logger is None:
            spa_logger = logging.getLogger(__name__)
        return spa_logger

    def init_params(self,
                    spot_market_info: MarketTradingPairTuple,
                    derivative_market_info: MarketTradingPairTuple,
                    order_amount: Decimal,
                    derivative_leverage: int,
                    min_divergence: Decimal,
                    min_convergence: Decimal,
                    spot_market_slippage_buffer: Decimal = Decimal("0"),
                    derivative_market_slippage_buffer: Decimal = Decimal("0"),
                    maximize_funding_rate: bool = True,
                    next_arbitrage_cycle_delay: float = 120,
                    status_report_interval: float = 10):
        """
        :param spot_market_info: The first market
        :param derivative_market_info: The second market
        :param order_amount: The order amount
        :param min_divergence: The minimum spread to start arbitrage (e.g. 0.0003 for 0.3%)
        :param min_convergence: The minimum spread to close arbitrage (e.g. 0.0003 for 0.3%)
        :param spot_market_slippage_buffer: The buffer for which to adjust order price for higher chance of
        the order getting filled. This is quite important for AMM which transaction takes a long time where a slippage
        is acceptable rather having the transaction get rejected. The submitted order price will be adjust higher
        for buy order and lower for sell order.
        :param derivative_market_slippage_buffer: The slipper buffer for market_2
        :param maximize_funding_rate: whether to submit both arbitrage taker orders (buy and sell) simultaneously
        If false, the bot will wait for first exchange order filled before submitting the other order.
        """
        self._spot_market_info = spot_market_info
        self._derivative_market_info = derivative_market_info
        self._min_divergence = min_divergence
        self._min_convergence = min_convergence
        self._order_amount = order_amount
        self._derivative_leverage = derivative_leverage
        self._spot_market_slippage_buffer = spot_market_slippage_buffer
        self._derivative_market_slippage_buffer = derivative_market_slippage_buffer
        self._maximize_funding_rate = maximize_funding_rate
        self._next_arbitrage_cycle_delay = next_arbitrage_cycle_delay
        self._next_arbitrage_cycle_time = 0
        self._all_markets_ready = False

        self._ev_loop = asyncio.get_event_loop()

        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([spot_market_info.market, derivative_market_info.market])

        self._current_proposal = None
        self._main_task = None
        self._spot_done = True
        self._deriv_done = True
        self._spot_order_ids = []
        self._deriv_order_ids = []

    @property
    def current_proposal(self) -> ArbProposal:
        return self._current_proposal

    @current_proposal.setter
    def current_proposal(self, value):
        self._current_proposal = value

    @property
    def min_divergence(self) -> Decimal:
        return self._min_divergence

    @property
    def min_convergence(self) -> Decimal:
        return self._min_convergence

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
    def deriv_position(self) -> List[Position]:
        return [s for s in self._derivative_market_info.market.account_positions.values() if
                s.trading_pair == self._derivative_market_info.trading_pair]

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
                self.logger().info("Markets are ready. Trading started.")
                if len(self.deriv_position) > 0:
                    self.logger().info("Active position detected, bot assumes first arbitrage was done and would scan for second arbitrage.")
        if self.ready_for_new_arb_trades():
            if self._main_task is None or self._main_task.done():
                self.current_proposal = ArbProposal(self._spot_market_info, self._derivative_market_info, self.order_amount, timestamp)
                self._main_task = safe_ensure_future(self.main(timestamp))

    async def main(self, timestamp):
        """
        The main procedure for the arbitrage strategy. It first check if it's time for funding payment, decide if to compare with either
        min_convergence or min_divergence, applies the slippage buffer, applies budget constraint, then finally execute the
        arbitrage.
        """
        execute_arb = False
        funding_msg = ""
        await self.current_proposal.proposed_spot_deriv_arb()
        if len(self.deriv_position) > 0 and self.should_alternate_proposal_sides(self.current_proposal, self.deriv_position):
            self.current_proposal.alternate_proposal_sides()

        if self.current_proposal.is_funding_payment_time():
            if len(self.deriv_position) > 0:
                if self._maximize_funding_rate:
                    execute_arb = not self.would_receive_funding_payment(self.deriv_position)
                    if execute_arb:
                        funding_msg = "Time for funding payment, executing second arbitrage to prevent paying funding fee"
                    else:
                        funding_msg = "Waiting for funding payment."
                else:
                    funding_msg = "Time for funding payment, executing second arbitrage " \
                                  "immediately since we don't intend to maximize funding rate"
                    execute_arb = True
            else:
                funding_msg = "Funding payment time, not looking for arbitrage opportunity because prices should be converging now!"
        else:
            if len(self.deriv_position) > 0:
                execute_arb = self.ready_for_execution(self.current_proposal, False)
            else:
                execute_arb = self.ready_for_execution(self.current_proposal, True)

        if execute_arb:
            self.logger().info(self.spread_msg())
            self.apply_slippage_buffers(self.current_proposal)
            self.apply_budget_constraint(self.current_proposal)
            await self.execute_arb_proposals(self.current_proposal, funding_msg)
        else:
            if funding_msg:
                self.timed_logger(timestamp, funding_msg)
            elif self._next_arbitrage_cycle_time > time.time():
                self.timed_logger(timestamp, "Cooling off...")
            else:
                self.timed_logger(timestamp, self.spread_msg())

    def timed_logger(self, timestamp, msg):
        """
        Displays log at specific intervals.
        :param timestamp: current timestamp
        :param msg: message to display at next interval
        """
        if timestamp - self._last_timestamp > self._status_report_interval:
            self.logger().info(msg)
            self._last_timestamp = timestamp

    def ready_for_execution(self, proposal: ArbProposal, first: bool):
        """
        Check if the spread meets the required spread requirement for the right arbitrage.
        :param proposal: current proposal object
        :param first: True, if scanning for opportunity for first arbitrage, else, False
        :return: True if ready, else, False
        """
        spread = self.current_proposal.spread()
        if first and spread >= self.min_divergence and self._next_arbitrage_cycle_time < time.time():  # we do not want to start new cycle untill cooloff is over
            return True
        elif not first and spread <= self.min_convergence and self._next_arbitrage_cycle_time < time.time():  # we also don't want second arbitrage to ever be retried within this period
            return True
        return False

    def should_alternate_proposal_sides(self, proposal: ArbProposal, active_position: List[Position]):
        """
        Checks if there's need to alternate the sides of a proposed arbitrage.
        :param proposal: current proposal object
        :param active_position: information about active position for the derivative connector
        :return: True if sides need to be alternated, else, False
        """
        deriv_proposal_side = PositionSide.LONG if proposal.derivative_side.is_buy else PositionSide.SHORT
        position_side = PositionSide.LONG if active_position[0].amount > 0 else PositionSide.SHORT
        if deriv_proposal_side == position_side:
            return True
        return False

    def would_receive_funding_payment(self, active_position: List[Position]):
        """
        Checks if an active position would receive funding payment.
        :param active_position: information about active position for the derivative connector
        :return: True if funding payment would be received, else, False
        """
        funding_info: FundingInfo = self._derivative_market_info.market.get_funding_info(
            self._derivative_market_info.trading_pair)
        if (active_position[0].amount > 0 > funding_info.rate) or (active_position[0].amount < 0 < funding_info.rate):
            return True
        return False

    def apply_slippage_buffers(self, arb_proposal: ArbProposal):
        """
        Updates arb_proposals by adjusting order price for slipper buffer percentage.
        E.g. if it is a buy order, for an order price of 100 and 1% slipper buffer, the new order price is 101,
        for a sell order, the new order price is 99.
        :param arb_proposal: the arbitrage proposal
        """
        for arb_side in (arb_proposal.spot_side, arb_proposal.derivative_side):
            market = arb_side.market_info.market
            arb_side.amount = market.quantize_order_amount(arb_side.market_info.trading_pair, arb_side.amount)
            s_buffer = self._spot_market_slippage_buffer if market == self._spot_market_info.market \
                else self._derivative_market_slippage_buffer
            if not arb_side.is_buy:
                s_buffer *= Decimal("-1")
            arb_side.order_price *= Decimal("1") + s_buffer
            arb_side.order_price = market.quantize_order_price(arb_side.market_info.trading_pair,
                                                               arb_side.order_price)

    def apply_budget_constraint(self, arb_proposal: ArbProposal):
        """
        Updates arb_proposals by setting proposal amount to 0 if there is not enough balance to submit order with
        required order amount.
        :param arb_proposal: the arbitrage proposal
        """
        spot_market = self._spot_market_info.market
        deriv_market: Union[ConnectorBase, PerpetualTrading] = self._derivative_market_info.market
        spot_token = self._spot_market_info.quote_asset if arb_proposal.spot_side.is_buy else self._spot_market_info.base_asset
        deriv_token = self._derivative_market_info.quote_asset
        spot_token_balance = spot_market.get_available_balance(spot_token)
        deriv_token_balance = deriv_market.get_available_balance(deriv_token)
        required_spot_balance = arb_proposal.amount * arb_proposal.spot_side.order_price if arb_proposal.spot_side.is_buy else arb_proposal.amount
        required_deriv_balance = (arb_proposal.amount * arb_proposal.derivative_side.order_price) / self._derivative_leverage
        if spot_token_balance < required_spot_balance:
            arb_proposal.amount = s_decimal_zero
            self.logger().info(f"Can't arbitrage, {spot_market.display_name} "
                               f"{spot_token} balance "
                               f"({spot_token_balance}) is below required order amount ({required_spot_balance}).")
        elif deriv_token_balance < required_deriv_balance:
            arb_proposal.amount = s_decimal_zero
            self.logger().info(f"Can't arbitrage, {deriv_market.display_name} "
                               f"{deriv_token} balance "
                               f"({deriv_token_balance}) is below required order amount ({required_deriv_balance}).")

    async def execute_arb_proposals(self, arb_proposal: ArbProposal, is_funding_msg: str = ""):
        """
        Execute both sides of the arbitrage trades concurrently.
        :param arb_proposals: the arbitrage proposal
        :param is_funding_msg: message pertaining to funding payment
        """
        if arb_proposal.amount == s_decimal_zero:
            return
        self._spot_done = False
        self._deriv_done = False
        proposal = self.short_proposal_msg(False)
        if is_funding_msg:
            opportunity_msg = is_funding_msg
        else:
            first_arbitage = not bool(len(self.deriv_position))
            opportunity_msg = "Spread wide enough to execute first arbitrage" if first_arbitage else \
                              "Spread low enough to execute second arbitrage"
            if not first_arbitage:
                self._next_arbitrage_cycle_time = time.time() + self._next_arbitrage_cycle_delay
        self.logger().info(f"{opportunity_msg}!: \n"
                           f"{proposal[0]} \n"
                           f"{proposal[1]} \n")
        safe_ensure_future(self.execute_spot_side(arb_proposal.spot_side))
        safe_ensure_future(self.execute_derivative_side(arb_proposal.derivative_side))

    async def execute_spot_side(self, arb_side: ArbProposalSide):
        side = "BUY" if arb_side.is_buy else "SELL"
        place_order_fn = self.buy_with_specific_market if arb_side.is_buy else self.sell_with_specific_market
        self.log_with_clock(logging.INFO,
                            f"Placing {side} order for {arb_side.amount} {arb_side.market_info.base_asset} "
                            f"at {arb_side.market_info.market.display_name} at {arb_side.order_price} price")
        order_id = place_order_fn(arb_side.market_info,
                                  arb_side.amount,
                                  arb_side.market_info.market.get_taker_order_type(),
                                  arb_side.order_price,
                                  )
        self._spot_order_ids.append(order_id)

    async def execute_derivative_side(self, arb_side: ArbProposalSide):
        side = "BUY" if arb_side.is_buy else "SELL"
        place_order_fn = self.buy_with_specific_market if arb_side.is_buy else self.sell_with_specific_market
        position_action = PositionAction.OPEN if len(self.deriv_position) == 0 else PositionAction.CLOSE
        self.log_with_clock(logging.INFO,
                            f"Placing {side} order for {arb_side.amount} {arb_side.market_info.base_asset} "
                            f"at {arb_side.market_info.market.display_name} at {arb_side.order_price} price to {position_action.name} position.")
        order_id = place_order_fn(arb_side.market_info,
                                  arb_side.amount,
                                  arb_side.market_info.market.get_taker_order_type(),
                                  arb_side.order_price,
                                  position_action=position_action
                                  )
        self._deriv_order_ids.append(order_id)

    def ready_for_new_arb_trades(self) -> bool:
        """
        Returns True if there is no outstanding unfilled order.
        """
        for market_info in [self._spot_market_info, self._derivative_market_info]:
            if len(self.market_info_to_active_orders.get(market_info, [])) > 0:
                return False
            if not self._spot_done or not self._deriv_done:
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
        spread = self.current_proposal.spread()
        first = not bool(len(self.deriv_position))
        target_spread_str = "minimum divergence spread" if first else "minimum convergence spread"
        target_spread = self.min_divergence if first else self.min_convergence
        msg = f"Current spread: {spread:.2%}, {target_spread_str}: {target_spread:.2%}."
        return msg

    def active_positions_df(self) -> pd.DataFrame:
        columns = ["Symbol", "Type", "Entry Price", "Amount", "Leverage", "Unrealized PnL"]
        data = []
        for idx in self.deriv_position:
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
        for market_info in [self._spot_market_info, self._derivative_market_info]:
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
        if len(self.deriv_position) > 0:
            df = self.active_positions_df()
            lines.extend(["", "  Positions:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active positions."])

        assets_df = self.wallet_balance_data_frame([self._spot_market_info, self._derivative_market_info])
        lines.extend(["", "  Assets:"] +
                     ["    " + line for line in str(assets_df).split("\n")])

        try:
            lines.extend(["", "  Spread details:"] + ["    " + self.spread_msg()] +
                         self.short_proposal_msg())
        except Exception:
            pass

        warning_lines = self.network_warning([self._spot_market_info])
        warning_lines.extend(self.network_warning([self._derivative_market_info]))
        warning_lines.extend(self.balance_warning([self._spot_market_info]))
        warning_lines.extend(self.balance_warning([self._derivative_market_info]))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def did_complete_buy_order(self, order_completed_event):
        self.update_status(order_completed_event)

    def did_complete_sell_order(self, order_completed_event):
        self.update_status(order_completed_event)

    def did_fail_order(self, order_failed_event):
        self.retry_order(order_failed_event)

    def did_cancel_order(self, cancelled_event):
        self.retry_order(cancelled_event)

    def did_expire_order(self, expired_event):
        self.retry_order(expired_event)

    def did_complete_funding_payment(self, funding_payment_completed_event):
        # Excute second arbitrage if necessary (even spread hasn't reached min convergence)
        if len(self.deriv_position) > 0 and \
           self._all_markets_ready and \
           self.current_proposal and \
           self.ready_for_new_arb_trades():
            self.apply_slippage_buffers(self.current_proposal)
            self.apply_budget_constraint(self.current_proposal)
            funding_msg = "Executing second arbitrage after funding payment is received"
            safe_ensure_future(self.execute_arb_proposals(self.current_proposal, funding_msg))
        return

    def update_status(self, event):
        order_id = event.order_id
        if order_id in self._spot_order_ids:
            self._spot_done = True
            self._spot_order_ids.remove(order_id)
        elif order_id in self._deriv_order_ids:
            self._deriv_done = True
            self._deriv_order_ids.remove(order_id)

    def retry_order(self, event):
        order_id = event.order_id
        # To-do: Should be updated to do counted retry rather than time base retry. i.e mark as done after retrying 3 times
        if event.timestamp > (time.time() - 5):  # retry if order failed less than 5 secs ago
            if order_id in self._spot_order_ids:
                self.logger().info("Retrying failed order on spot exchange.")
                safe_ensure_future(self.execute_spot_side(self.current_proposal.spot_side))
                self._spot_order_ids.remove(order_id)
            elif order_id in self._deriv_order_ids:
                self.logger().info("Retrying failed order on derivative exchange.")
                safe_ensure_future(self.execute_derivative_side(self.current_proposal.derivative_side))
                self._deriv_order_ids.remove(order_id)
        else:  # mark as done
            self.update_status(event)

    @property
    def tracked_limit_orders(self) -> List[Tuple[ConnectorBase, LimitOrder]]:
        return self._sb_order_tracker.tracked_limit_orders

    @property
    def tracked_market_orders(self) -> List[Tuple[ConnectorBase, MarketOrder]]:
        return self._sb_order_tracker.tracked_market_orders

    def apply_initial_settings(self, trading_pair, leverage):
        deriv_market = self._derivative_market_info.market
        deriv_market.set_leverage(trading_pair, leverage)
        deriv_market.set_position_mode(PositionMode.ONEWAY)

    def start(self, clock: Clock, timestamp: float):
        self.apply_initial_settings(self._derivative_market_info.trading_pair, self._derivative_leverage)

    def stop(self, clock: Clock):
        if self._main_task is not None:
            self._main_task.cancel()
            self._main_task = None
