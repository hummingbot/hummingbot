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
from hummingbot.core.utils.async_utils import safe_gather

from hummingbot.core.event.events import (
    PositionAction,
    PositionSide
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
                    min_divergence: Decimal,
                    min_convergence: Decimal,
                    spot_slippage_buffer: Decimal = Decimal("0"),
                    perp_slippage_buffer: Decimal = Decimal("0"),
                    next_arbitrage_cycle_delay: float = 120,
                    status_report_interval: float = 10):
        """
        :param spot_market_info: The spot market info
        :param perp_market_info: The perpetual market info
        :param order_amount: The order amount
        :param min_divergence: The minimum spread to open arbitrage position (e.g. 0.0003 for 0.3%)
        :param min_convergence: The minimum spread to close arbitrage position (e.g. 0.0003 for 0.3%)
        :param spot_slippage_buffer: The buffer for which to adjust order price for higher chance of
        the order getting filled on spot market.
        :param perp_slippage_buffer: The slipper buffer for perpetual market.
        """
        self._spot_market_info = spot_market_info
        self._perp_market_info = perp_market_info
        self._min_divergence = min_divergence
        self._min_convergence = min_convergence
        self._order_amount = order_amount
        self._perp_leverage = perp_leverage
        self._spot_slippage_buffer = spot_slippage_buffer
        self._perp_slippage_buffer = perp_slippage_buffer
        self._next_arbitrage_cycle_delay = next_arbitrage_cycle_delay
        self._next_arbitrage_cycle_time = 0
        self._all_markets_ready = False
        self._ev_loop = asyncio.get_event_loop()
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([spot_market_info.market, perp_market_info.market])

        self._main_task = None
        self._spot_order_ids = []
        self._deriv_order_ids = []

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
                self.logger().info("Markets are ready. Trading started.")
                if len(self.perp_positions) > 0:
                    if self.perp_positions[0].amount == self._order_amount:
                        self.logger().info(f"There is an existing {self._perp_market_info.trading_pair} "
                                           f"{self.perp_positions[0].position_side.name} position. The bot resumes "
                                           f"waiting for spreads to converge to close out the arbitrage position")
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
        if self.is_on_closing_arbitrage():
            first_perp_side = self.perp_positions[0].position_side
            last_perp_is_buy = True if first_perp_side == PositionSide.SHORT else False
            proposals = [p for p in proposals if p.perp_side.is_buy == last_perp_is_buy]
        else:
            proposals = [p for p in proposals if p.spread() >= self._min_divergence]
        if len(proposals) > 1:
            raise Exception(f"Unexpected situation where number of proposals ({len(proposals)}) is > 1")
        self.apply_budget_constraint(proposals)
        if proposals and proposals[0].spot_side.amount > 0 and proposals[0].perp_side.amount > 0:
            pass

    def execute_proposals(self, proposals: List[ArbProposal]):
        pass

    def apply_budget_constraints(self, proposals: List[ArbProposal]):
        pass

    def is_on_closing_arbitrage(self) -> bool:
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
            ArbProposal(ArbProposalSide(self._spot_market_info, True, spot_buy, self._order_amount),
                        ArbProposalSide(self._perp_market_info, False, perp_sell, self._order_amount)),
            ArbProposal(ArbProposalSide(self._spot_market_info, False, spot_sell, self._order_amount),
                        ArbProposalSide(self._perp_market_info, True, perp_buy, self._order_amount)),
        ]

    def timed_log(self, timestamp: float, msg: str):
        """
        Displays log at specific intervals.
        :param timestamp: current timestamp
        :param msg: message to display at next interval
        """
        if timestamp - self._last_timestamp > self._status_report_interval:
            self.logger().info(msg)
            self._last_timestamp = timestamp

    def apply_slippage_buffers(self, arb_proposal: ArbProposal):
        """
        Updates arb_proposals by adjusting order price for slipper buffer percentage.
        E.g. if it is a buy order, for an order price of 100 and 1% slipper buffer, the new order price is 101,
        for a sell order, the new order price is 99.
        :param arb_proposal: the arbitrage proposal
        """
        for arb_side in (arb_proposal.spot_side, arb_proposal.perp_side):
            market = arb_side.market_info.market
            arb_side.amount = market.quantize_order_amount(arb_side.market_info.trading_pair, arb_side.amount)
            s_buffer = self._spot_slippage_buffer if market == self._spot_market_info.market \
                else self._perp_slippage_buffer
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
        return
        spot_market = self._spot_market_info.market
        deriv_market: Union[ConnectorBase, PerpetualTrading] = self._perp_market_info.market
        spot_token = self._spot_market_info.quote_asset if arb_proposal.spot_side.is_buy else self._spot_market_info.base_asset
        deriv_token = self._perp_market_info.quote_asset
        spot_token_balance = spot_market.get_available_balance(spot_token)
        deriv_token_balance = deriv_market.get_available_balance(deriv_token)
        required_spot_balance = arb_proposal.amount * arb_proposal.spot_side.order_price if arb_proposal.spot_side.is_buy else arb_proposal.amount
        required_deriv_balance = (arb_proposal.amount * arb_proposal.derivative_side.order_price) / self._perp_leverage
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
        return
        if arb_proposal.amount == s_decimal_zero:
            return
        self._spot_done = False
        self._deriv_done = False
        proposal = self.short_proposal_msg(False)
        if is_funding_msg:
            opportunity_msg = is_funding_msg
        else:
            first_arbitage = not bool(len(self.perp_positions))
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
        position_action = PositionAction.OPEN if len(self.perp_positions) == 0 else PositionAction.CLOSE
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
        for market_info in [self._spot_market_info, self._perp_market_info]:
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

    def did_complete_buy_order(self, order_completed_event):
        self.update_status(order_completed_event)

    def did_complete_sell_order(self, order_completed_event):
        self.update_status(order_completed_event)

    def did_fail_order(self, order_failed_event):
        self.retry_order(order_failed_event)

    def did_cancel_order(self, cancelled_event):
        self.retry_order(cancelled_event)

    @property
    def tracked_market_orders(self) -> List[Tuple[ConnectorBase, MarketOrder]]:
        return self._sb_order_tracker.tracked_market_orders

    def start(self, clock: Clock, timestamp: float):
        pass

    def stop(self, clock: Clock):
        if self._main_task is not None:
            self._main_task.cancel()
            self._main_task = None
