from decimal import Decimal
import logging
import asyncio
import pandas as pd
from typing import List, Dict
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from .utils import create_arb_proposals, ArbProposal


NaN = float("nan")
s_decimal_zero = Decimal(0)
amm_logger = None


class AmmArbStrategy(StrategyPyBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global amm_logger
        if amm_logger is None:
            amm_logger = logging.getLogger(__name__)
        return amm_logger

    def __init__(self,
                 market_info_1: MarketTradingPairTuple,
                 market_info_2: MarketTradingPairTuple,
                 min_profitability: Decimal,
                 order_amount: Decimal,
                 slippage_buffer: Decimal = Decimal("0.0001"),
                 concurrent_orders_submission: bool = True,
                 status_report_interval: float = 900,
                 hb_app_notification: bool = True):
        super().__init__()
        self._market_info_1 = market_info_1
        self._market_info_2 = market_info_2
        self._min_profitability = min_profitability
        self._order_amount = order_amount
        self._slippage_buffer = slippage_buffer
        self._concurrent_orders_submission = concurrent_orders_submission
        self._last_no_arb_reported = 0
        self._arb_proposals = None
        self._all_markets_ready = False

        self._ev_loop = asyncio.get_event_loop()
        self._async_scheduler = None
        self._last_synced_checked = 0
        self._node_synced = False

        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._hb_app_notification = hb_app_notification
        self.add_markets([market_info_1.market, market_info_2.market])

    @property
    def min_profitability(self) -> Decimal:
        return self._min_profitability

    @property
    def order_amount(self) -> Decimal:
        return self._order_amount

    @order_amount.setter
    def order_amount(self, value):
        self._order_amount = value

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self._all_markets_ready:
            self._all_markets_ready = all([market.ready for market in self.active_markets])
            if not self._all_markets_ready:
                self.logger().warning(f"Markets are not ready. Please wait...")
                return
            else:
                self.logger().info(f"Markets are ready. Trading started.")
        if self.ready_for_new_arb_trades():
            self.main()

    def main(self):
        self._arb_proposals = create_arb_proposals(self._market_info_1, self._market_info_2, self._order_amount)
        arb_proposals = [t for t in self._arb_proposals if t.profit_pct() >= self._min_profitability]
        if len(arb_proposals) == 0:
            if self._last_no_arb_reported < self.current_timestamp - 20.:
                self.logger().info(f"No arbitrage opportunity.\n" +
                                   "\n".join(self.short_proposal_msg(self._arb_proposals, False)))
                self._last_no_arb_reported = self.current_timestamp
            return
        self.apply_budget_constraint(arb_proposals)
        self.execute_arb_proposals(arb_proposals)

    def apply_budget_constraint(self, arb_proposals: List[ArbProposal]):
        for arb_proposal in arb_proposals:
            for arb_side in (arb_proposal.first_side, arb_proposal.second_side):
                market = arb_side.market_info.market
                arb_side.amount = market.quantize_order_amount(arb_side.market_info.trading_pair, arb_side.amount)
                token = arb_side.market_info.quote_asset if arb_side.is_buy else arb_side.market_info.base_asset
                balance = market.get_available_balance(token)
                required = arb_side.amount
                if arb_side.is_buy:
                    required = (arb_side.amount * arb_side.order_price) * \
                               (Decimal("1") + market.estimate_fee_pct(False))
                if balance < required:
                    arb_side.amount = s_decimal_zero
                    self.logger().info(f"Can't arbitrage, {market.display_name} "
                                       f"{token} balance "
                                       f"({balance}) is below required order amount ({required}).")
                    continue

    def execute_arb_proposals(self, arb_proposals: List[ArbProposal]):
        for arb_proposal in arb_proposals:
            if any(p.amount <= s_decimal_zero for p in (arb_proposal.first_side, arb_proposal.second_side)):
                continue
            self.logger().info(f"Found arbitrage opportunity!: {arb_proposal}")
            for arb_side in (arb_proposal.first_side, arb_proposal.second_side):
                side = "BUY" if arb_side.is_buy else "SELL"
                self.log_with_clock(logging.INFO,
                                    f"Placing {side} order for {arb_side.amount} {arb_side.market_info.base_asset} "
                                    f"at {arb_side.market_info.market.display_name} at {arb_side.order_price} price")
                place_order_fn = self.buy_with_specific_market if arb_side.is_buy else self.sell_with_specific_market
                place_order_fn(arb_side.market_info,
                               arb_side.amount,
                               arb_side.market_info.market.get_taker_order_type(),
                               arb_side.order_price,
                               )

    def ready_for_new_arb_trades(self) -> bool:
        outstanding_orders = {**self._sb_order_tracker.get_limit_orders(),
                              **self._sb_order_tracker.get_market_orders()}
        for market_info in [self._market_info_1, self._market_info_2]:
            if not market_info.market.ready or len(outstanding_orders.get(market_info, {})) > 0:
                return False
        return True

    def short_proposal_msg(self, arb_proposal: List[ArbProposal], indented: bool = True) -> List[str]:
        lines = []
        for proposal in arb_proposal:
            side1 = "buy" if proposal.first_side.is_buy else "sell"
            side2 = "buy" if proposal.second_side.is_buy else "sell"
            lines.append(f"{'    ' if indented else ''}{side1} at {proposal.first_side.market_info.market.display_name}"
                         f", {side2} at {proposal.second_side.market_info.market.display_name}: "
                         f"{proposal.profit_pct():.2%}")
        return lines

    def format_status(self) -> str:
        if self._arb_proposals is None:
            return "  The strategy is not ready, please try again later."
        # active_orders = self.market_info_to_active_orders.get(self._market_info, [])
        columns = ["Exchange", "Market", "Sell Price", "Buy Price", "Mid Price"]
        data = []
        for market_info in [self._market_info_1, self._market_info_2]:
            market, trading_pair, base_asset, quote_asset = market_info
            buy_price = market.get_quote_price(trading_pair, True, self._order_amount)
            sell_price = market.get_quote_price(trading_pair, False, self._order_amount)
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

        assets_df = self.wallet_balance_data_frame([self._market_info_1, self._market_info_2])
        lines.extend(["", "  Assets:"] +
                     ["    " + line for line in str(assets_df).split("\n")])

        lines.extend(["", "  Profitability:"] + self.short_proposal_msg(self._arb_proposals))

        # warning_lines.extend(self.network_warning([self._market_info]))
        # warning_lines.extend(self.balance_warning([self._market_info]))
        # if len(warning_lines) > 0:
        #     lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)
