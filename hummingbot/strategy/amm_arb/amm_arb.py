import asyncio
import heapq
import logging
from decimal import Decimal
from functools import lru_cache
from typing import Callable, Dict, List, Optional, Tuple, cast

import pandas as pd

from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.settings import AllConnectorSettings, GatewayConnectionSetting
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.amm.gateway_evm_amm import GatewayEVMAMM
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import PriceType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    OrderType,
    SellOrderCompletedEvent,
)
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.amm_arb.data_types import ArbProposalSide
from hummingbot.strategy.amm_arb.utils import ArbProposal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

NaN = float("nan")
s_decimal_zero = Decimal(0)
amm_logger = None


class AmmArbStrategy(StrategyPyBase):
    """
    This is a basic arbitrage strategy which can be used for most types of connectors (CEX, DEX or AMM).
    For a given order amount, the strategy checks both sides of the trade (market_1 and market_2) for arb opportunity.
    If presents, the strategy submits taker orders to both market.
    """

    _market_adapters: List[MarketTradingPairTuple]
    _min_profitability: Decimal
    _max_order_amount: Decimal
    _slippage_buffer: Decimal
    _rebal_slippage_buffer: Decimal
    _concurrent_orders_submission: bool
    _inventory_threshhold: Decimal
    _last_no_arb_reported: float
    _arb_proposals: Optional[List[ArbProposal]]
    _all_markets_ready: bool
    _ev_loop: asyncio.AbstractEventLoop
    _main_task: Optional[asyncio.Task]
    _last_timestamp: float
    _status_report_interval: float
    _quote_eth_rate_fetch_loop_task: Optional[asyncio.Task]
    _rate_source: Optional[RateOracle]
    _cancel_outdated_orders_task: Optional[asyncio.Task]
    _gateway_transaction_cancel_interval: int

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global amm_logger
        if amm_logger is None:
            amm_logger = logging.getLogger(__name__)
        return amm_logger

    def init_params(
        self,
        market_adapters: List[MarketTradingPairTuple],
        min_profitability: Decimal,
        max_order_amount: Decimal,
        slippage_buffer: Decimal,
        inventory_threshhold: Decimal,
        rebal_slippage_buffer: Decimal,
        concurrent_orders_submission: bool = True,
        status_report_interval: float = 900,
        gateway_transaction_cancel_interval: int = 600,
        rate_source: Optional[RateOracle] = RateOracle.get_instance(),
    ):

        log_msg: str = f"Inputs are: {market_adapters}, {min_profitability}, {max_order_amount}, {slippage_buffer},{concurrent_orders_submission}"
        self.log_with_clock(logging.INFO, log_msg)

        self._market_adapters = market_adapters
        self._min_profitability = min_profitability
        self._max_order_amount = max_order_amount
        self._slippage_buffer = slippage_buffer
        self._inventory_threshhold = inventory_threshhold
        self._concurrent_orders_submission = concurrent_orders_submission
        self._rebal_slippage_buffer = rebal_slippage_buffer
        self._last_no_arb_reported = 0
        self._all_arb_proposals = None
        self._all_markets_ready = False

        self._ev_loop = asyncio.get_event_loop()
        self._main_task = None

        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([market_info.market for market_info in self._market_adapters])
        self._quote_eth_rate_fetch_loop_task = None

        self._rate_source = rate_source

        self._cancel_outdated_orders_task = None
        self._gateway_transaction_cancel_interval = gateway_transaction_cancel_interval

        self._order_id_side_map: Dict[str, ArbProposalSide] = {}

        self._inventory_metrics = {}

        self._ideal_position = Decimal("0.5")

    @property
    def all_markets_ready(self) -> bool:
        return self._all_markets_ready

    @all_markets_ready.setter
    def all_markets_ready(self, value: bool):
        self._all_markets_ready = value

    @property
    def min_profitability(self) -> Decimal:
        return self._min_profitability

    @property
    def order_amount(self) -> Decimal:
        return self._order_amount

    @order_amount.setter
    def order_amount(self, value: Decimal):
        self._order_amount = value

    @property
    def rate_source(self) -> Optional[RateOracle]:
        return self._rate_source

    @rate_source.setter
    def rate_source(self, src: Optional[RateOracle]):
        self._rate_source = src

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    @staticmethod
    @lru_cache(maxsize=10)
    def is_gateway_market(market_info: MarketTradingPairTuple) -> bool:
        return market_info.market.name in sorted(AllConnectorSettings.get_gateway_amm_connector_names())

    @staticmethod
    @lru_cache(maxsize=10)
    def is_gateway_market_evm_compatible(market_info: MarketTradingPairTuple) -> bool:
        connector_spec: Dict[str, str] = GatewayConnectionSetting.get_connector_spec_from_market_name(
            market_info.market.name
        )
        return connector_spec["chain_type"] == "EVM"

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self.all_markets_ready:
            self.all_markets_ready = all([market.ready for market in self.active_markets])
            if not self.all_markets_ready:
                if int(timestamp) % 10 == 0:  # prevent spamming by logging every 10 secs
                    unready_markets = [market for market in self.active_markets if market.ready is False]
                    for market in unready_markets:
                        msg = ", ".join([k for k, v in market.status_dict.items() if v is False])
                        self.logger().warning(f"{market.name} not ready: waiting for {msg}.")
                return
            else:
                self.logger().info("Markets are ready. Trading started.")

        if self.ready_for_new_arb_trades():
            if self._main_task is None or self._main_task.done():
                self._main_task = safe_ensure_future(self.main())
        if self._cancel_outdated_orders_task is None or self._cancel_outdated_orders_task.done():
            self._cancel_outdated_orders_task = safe_ensure_future(self.apply_gateway_transaction_cancel_interval())

    async def update_inventory_metrics(self):
        """Update inventory metrics across all exchanges"""
        self._inventory_metrics = {}
        # First pass: collect total balances
        for market_info in self._market_adapters:
            base_balance = market_info.base_balance
            quote_balance = market_info.quote_balance

            total_worth_in_quote = (base_balance + quote_balance / market_info.get_mid_price())
            ratio = base_balance / total_worth_in_quote if total_worth_in_quote > 0 else Decimal("0")

            self._inventory_metrics[market_info.market.name] = {
                "base_balance": base_balance,
                "quote_balance": quote_balance,
                "current_ratio": ratio
            }
        for market_info in self._market_adapters:
            metrics = self._inventory_metrics[market_info.market.name]
            # Calculate allowable range
            min_ratio = Decimal("0.5") - self._inventory_threshhold
            max_ratio = Decimal("0.5") + self._inventory_threshhold
            metrics.update({
                "ratio_status": "balanced" if min_ratio <= metrics["current_ratio"] <= max_ratio else "oversupplied" if metrics["current_ratio"] > max_ratio else "undersupplied"})
            logging.info(f"{market_info.market.name} - {metrics['ratio_status']} - {metrics['current_ratio']}")

    async def check_for_rebalance(self):
        oversupplied = []
        undersupplied = []
        slippage_threshold = self._rebal_slippage_buffer
        for market_info in self._market_adapters:
            if self._inventory_metrics[market_info.market.name]["ratio_status"] == "oversupplied":
                oversupplied.append(market_info)
            elif self._inventory_metrics[market_info.market.name]["ratio_status"] == "undersupplied":
                undersupplied.append(market_info)
        if not undersupplied and not oversupplied:
            return False
        for market_info in undersupplied:
            # to buy
            ratio_difference = abs(self._ideal_position - self._inventory_metrics[market_info.market.name]["current_ratio"])
            amount = ratio_difference * (self._inventory_metrics[market_info.market.name]["base_balance"] + self._inventory_metrics[market_info.market.name]["quote_balance"] / market_info.get_mid_price())
            amount = min(amount, self._inventory_metrics[market_info.market.name]["quote_balance"] * market_info.get_mid_price())
            best_buy_price = market_info.get_price_for_volume(False, amount).result_price
            logging.info(best_buy_price)
            slippage = abs(market_info.get_price_by_type(PriceType.MidPrice) - best_buy_price) / market_info.get_price_by_type(PriceType.MidPrice)
            if slippage < slippage_threshold:
                order_id: str = await self.place_arb_order(
                    market_info, True, amount, best_buy_price
                )
                logging.info(f"Rebalance Buy Order with slippage {slippage} in {market_info.market.name} Price- {best_buy_price} Qty- {amount},OrderId- {order_id}")
                await asyncio.sleep(10)
            else:
                logging.info("Please rebalance manually")
        for market_info in oversupplied:
            # to sell
            ratio_difference = abs(self._ideal_position - self._inventory_metrics[market_info.market.name]["current_ratio"])
            amount = ratio_difference * (self._inventory_metrics[market_info.market.name]["base_balance"] + self._inventory_metrics[market_info.market.name]["quote_balance"] / market_info.get_mid_price())
            amount = min(amount, self._inventory_metrics[market_info.market.name]["quote_balance"] * market_info.get_mid_price())
            best_sell_price = market_info.get_price_for_volume(True, amount).result_price
            logging.info(best_sell_price)
            slippage = abs(market_info.get_price_by_type(PriceType.MidPrice) - best_sell_price) / market_info.get_price_by_type(PriceType.MidPrice)
            if slippage < slippage_threshold:
                order_id: str = await self.place_arb_order(
                    market_info, False, amount, best_sell_price
                )
                logging.info(f"rebalance Sell Order with slippage {slippage} in {market_info.market.name} Price- {best_sell_price} Qty- {amount} OrderId - {order_id}")
                await asyncio.sleep(10)
            else:
                logging.info("Please rebalance manually")
        return True

    async def main(self):
        bids = []  # Max-heap (inverted values for max-heap behavior)
        asks = []  # Min-heap

        await self.update_inventory_metrics()
        rebaled = await self.check_for_rebalance()
        if rebaled:
            return

        def add_bid(price, quantity, market):
            # Insert as negative to maintain max-heap behavior
            heapq.heappush(bids, (-price, quantity, market))

        def add_ask(price, quantity, market):
            heapq.heappush(asks, (price, quantity, market))

        def remove_bid():
            if bids:
                heapq.heappop(bids)

        def remove_ask():
            if asks:
                heapq.heappop(asks)

        def get_best_bid():
            if bids:
                return (-bids[0][0], bids[0][1], bids[0][2])  # Invert to get the actual price
            return None

        def get_best_ask():
            if asks:
                return (asks[0][0], asks[0][1], asks[0][2])
            return None

        for market_info in self._market_adapters:
            for ask in list(market_info.order_book_ask_entries())[:5]:
                add_ask(ask.price, ask.amount, market_info)
            for bid in list(market_info.order_book_bid_entries())[:5]:
                add_bid(bid.price, bid.amount, market_info)
        arb_proposals = []
        # Start with highest bid and lowest ask
        best_bid = get_best_bid()
        best_ask = get_best_ask()
        iterations = 0
        while best_bid and best_ask:
            iterations += 1
            if best_bid[0] < best_ask[0]:
                break

            elif best_bid[0] >= best_ask[0]:
                if best_bid[2] == best_ask[2]:
                    remove_ask()
                    best_ask = get_best_ask()
                else:
                    bid_extra_fees = [getattr(best_bid[2].market, "network_transaction_fee") if hasattr(best_bid[2].market, "network_transaction_fee") else []]
                    ask_extra_fees = [getattr(best_ask[2].market, "network_transaction_fee") if hasattr(best_ask[2].market, "network_transaction_fee") else []]
                    balances_coin = best_bid[2].base_balance
                    balances_quote = best_ask[2].quote_balance / best_ask[2].get_mid_price()
                    amount = min(balances_coin, balances_quote, self._max_order_amount, best_bid[1], best_ask[1])
                    if amount <= 0:
                        break
                    proposal = ArbProposal(
                        first_side = ArbProposalSide(
                            market_info=best_ask[2],
                            is_buy=True,
                            quote_price=best_ask[0],
                            order_price=best_ask[0],
                            amount=round(amount, 4),
                            extra_flat_fees=ask_extra_fees,
                        ),
                        second_side = ArbProposalSide(
                            market_info=best_bid[2],
                            is_buy=False,
                            quote_price=best_bid[0],
                            order_price=best_bid[0],
                            amount=round(amount, 4),
                            extra_flat_fees=bid_extra_fees,
                        )
                    )
                    pp = proposal.profit_pct(rate_source= self._rate_source)
                    log_msg: str = f"profit % - {pp}"
                    self.log_with_clock(logging.INFO, log_msg)
                    if proposal.profit_pct(rate_source=self._rate_source) >= self.min_profitability:
                        log_msg: str = "profitable arb"
                        self.log_with_clock(logging.INFO, log_msg)
                        arb_proposals.append(proposal)
                    break

        if len(arb_proposals) == 0:
            self.logger().info("No arbitrage opportunity.\n")
            self._last_no_arb_reported = self.current_timestamp
            return

        await self.apply_slippage_buffers(arb_proposals)
        self.apply_budget_constraint(arb_proposals)
        await self.execute_arb_proposals(arb_proposals)

    async def apply_gateway_transaction_cancel_interval(self):
        # XXX (martin_kou): Concurrent cancellations are not supported before the nonce architecture is fixed.
        # See: https://app.shortcut.com/coinalpha/story/24553/nonce-architecture-in-current-amm-trade-and-evm-approve-apis-is-incorrect-and-causes-trouble-with-concurrent-requests
        gateway_connectors = []
        for market_info in self._market_adapters:
            if self.is_gateway_market(market_info) and self.is_gateway_market_evm_compatible(market_info):
                gateway_connectors.append(cast(GatewayEVMAMM, market_info.market))
        for gateway in gateway_connectors:
            await gateway.cancel_outdated_orders(self._gateway_transaction_cancel_interval)

    async def apply_slippage_buffers(self, arb_proposals: List[ArbProposal]):
        """
        Updates arb_proposals by adjusting order price for slipper buffer percentage.
        E.g. if it is a buy order, for an order price of 100 and 1% slipper buffer, the new order price is 101,
        for a sell order, the new order price is 99.
        :param arb_proposals: the arbitrage proposal
        """
        for arb_proposal in arb_proposals:
            for arb_side in (arb_proposal.first_side, arb_proposal.second_side):
                market = arb_side.market_info.market
                arb_side.amount = market.quantize_order_amount(arb_side.market_info.trading_pair, arb_side.amount)
                s_buffer = self._slippage_buffer
                if not arb_side.is_buy:
                    s_buffer *= Decimal("-1")
                arb_side.order_price *= Decimal("1") + s_buffer
                arb_side.order_price = market.quantize_order_price(
                    arb_side.market_info.trading_pair, arb_side.order_price
                )

    def apply_budget_constraint(self, arb_proposals: List[ArbProposal]):
        """
        Updates arb_proposals by setting proposal amount to 0 if there is not enough balance to submit order with
        required order amount.
        :param arb_proposals: the arbitrage proposal
        """
        for arb_proposal in arb_proposals:
            for arb_side in (arb_proposal.first_side, arb_proposal.second_side):
                market = arb_side.market_info.market
                token = arb_side.market_info.quote_asset if arb_side.is_buy else arb_side.market_info.base_asset
                balance = market.get_available_balance(token)
                required = arb_side.amount * arb_side.order_price if arb_side.is_buy else arb_side.amount
                if balance < required:
                    arb_side.amount = s_decimal_zero
                    self.logger().info(
                        f"Can't arbitrage, {market.display_name} "
                        f"{token} balance "
                        f"({balance}) is below required order amount ({required})."
                    )
                    continue

    def prioritize_evm_exchanges(self, arb_proposal: ArbProposal) -> ArbProposal:
        """
        Prioritize the EVM exchanges in the arbitrage proposals

        :param arb_proposal: The arbitrage proposal from which the sides are to be prioritized.
        :type arb_proposal: ArbProposal
        :return: A new ArbProposal object with evm exchanges prioritized.
        :rtype: ArbProposal
        """

        results = []
        for side in [arb_proposal.first_side, arb_proposal.second_side]:
            if self.is_gateway_market(side.market_info):
                results.insert(0, side)
            else:
                results.append(side)

        return ArbProposal(first_side=results[0], second_side=results[1])

    async def execute_arb_proposals(self, arb_proposals: List[ArbProposal]):
        """
        Execute both sides of the arbitrage trades. If concurrent_orders_submission is False, it will wait for the
        first order to fill before submit the second order.
        :param arb_proposals: the arbitrage proposal
        """
        for arb_proposal in arb_proposals:
            if any(p.amount <= s_decimal_zero for p in (arb_proposal.first_side, arb_proposal.second_side)):
                continue

            if not self._concurrent_orders_submission:
                arb_proposal = self.prioritize_evm_exchanges(arb_proposal)

            self.logger().info(f"Found arbitrage opportunity!: {arb_proposal}")

            for arb_side in (arb_proposal.first_side, arb_proposal.second_side):
                side: str = "BUY" if arb_side.is_buy else "SELL"
                self.log_with_clock(
                    logging.INFO,
                    f"Placing {side} order for {arb_side.amount} {arb_side.market_info.base_asset} "
                    f"at {arb_side.market_info.market.display_name} at {arb_side.order_price} price",
                )

                order_id: str = await self.place_arb_order(
                    arb_side.market_info, arb_side.is_buy, arb_side.amount, arb_side.order_price
                )

                self._order_id_side_map.update({order_id: arb_side})

                if not self._concurrent_orders_submission:
                    await arb_side.completed_event.wait()
                    if arb_side.is_failed:
                        self.log_with_clock(
                            logging.ERROR,
                            f"Order {order_id} seems to have failed in this arbitrage opportunity. "
                            f"Dropping Arbitrage Proposal. ",
                        )
                        return

            await arb_proposal.wait()

    async def place_arb_order(
        self, market_info: MarketTradingPairTuple, is_buy: bool, amount: Decimal, order_price: Decimal
    ) -> str:
        place_order_fn: Callable[[MarketTradingPairTuple, Decimal, OrderType, Decimal], str] = cast(
            Callable, self.buy_with_specific_market if is_buy else self.sell_with_specific_market
        )
        return place_order_fn(market_info, amount, market_info.market.get_taker_order_type(), order_price)

    def ready_for_new_arb_trades(self) -> bool:
        """
        Returns True if there is no outstanding unfilled order.
        """
        for market_info in self._market_adapters:
            if len(self.market_info_to_active_orders.get(market_info, [])) > 0:
                return False
        return True

    def short_proposal_msg(self, arb_proposal: List[ArbProposal], indented: bool = True) -> List[str]:
        """
        Composes a short proposal message.
        :param arb_proposal: The arbitrage proposal
        :param indented: If the message should be indented (by 4 spaces)
        :return A list of messages
        """
        lines = []
        for proposal in arb_proposal:
            side1: str = "buy" if proposal.first_side.is_buy else "sell"
            side2: str = "buy" if proposal.second_side.is_buy else "sell"
            market_1_name: str = proposal.first_side.market_info.market.display_name
            market_2_name: str = proposal.second_side.market_info.market.display_name
            profit_pct = proposal.profit_pct(
                rate_source=self._rate_source,
                account_for_fee=True,
            )
            lines.append(
                f"{'    ' if indented else ''}{side1} at {market_1_name}"
                f", {side2} at {market_2_name}: "
                f"{profit_pct:.2%}"
            )
        return lines

    def get_fixed_rates_df(self):
        columns = ["Pair", "Rate"]
        quotes_pair: str = f"{self._market_info_2.quote_asset}-{self._market_info_1.quote_asset}"
        bases_pair: str = f"{self._market_info_2.base_asset}-{self._market_info_1.base_asset}"
        data = [
            [quotes_pair, PerformanceMetrics.smart_round(self._rate_source.get_pair_rate(quotes_pair))],
            [bases_pair, PerformanceMetrics.smart_round(self._rate_source.get_pair_rate(bases_pair))],
        ]
        return pd.DataFrame(data=data, columns=columns)

    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: markets,
        assets, profitability and warnings(if any).
        """

        if self._all_arb_proposals is None:
            return "  The strategy is not ready, please try again later."
        columns = ["Exchange", "Market", "Sell Price", "Buy Price", "Mid Price"]
        data = []
        for market_info in [self._market_info_1, self._market_info_2]:
            market, trading_pair, base_asset, quote_asset = market_info
            buy_price = await market.get_quote_price(trading_pair, True, self._max_order_amount)
            sell_price = await market.get_quote_price(trading_pair, False, self._max_order_amount)

            # check for unavailable price data
            buy_price = PerformanceMetrics.smart_round(Decimal(str(buy_price)), 8) if buy_price is not None else "-"
            sell_price = PerformanceMetrics.smart_round(Decimal(str(sell_price)), 8) if sell_price is not None else "-"
            mid_price = (
                PerformanceMetrics.smart_round(((buy_price + sell_price) / 2), 8)
                if "-" not in [buy_price, sell_price]
                else "-"
            )

            data.append([market.display_name, trading_pair, sell_price, buy_price, mid_price])
        markets_df = pd.DataFrame(data=data, columns=columns)
        lines = []
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        columns = ["Exchange", "Gas Fees"]
        data = []
        for market_info in [self._market_info_1, self._market_info_2]:
            if hasattr(market_info.market, "network_transaction_fee"):
                transaction_fee: TokenAmount = getattr(market_info.market, "network_transaction_fee")
                data.append([market_info.market.display_name, f"{transaction_fee.amount} {transaction_fee.token}"])
        network_fees_df = pd.DataFrame(data=data, columns=columns)
        if len(data) > 0:
            lines.extend(
                ["", "  Network Fees:"] + ["    " + line for line in network_fees_df.to_string(index=False).split("\n")]
            )

        assets_df = self.wallet_balance_data_frame([self._market_info_1, self._market_info_2])
        lines.extend(["", "  Assets:"] + ["    " + line for line in str(assets_df).split("\n")])

        lines.extend(["", "  Profitability:"] + self.short_proposal_msg(self._all_arb_proposals))

        fixed_rates_df = self.get_fixed_rates_df()
        lines.extend(
            ["", f"  Exchange Rates: ({str(self._rate_source)})"]
            + ["    " + line for line in str(fixed_rates_df).split("\n")]
        )

        warning_lines = self.network_warning([self._market_info_1])
        warning_lines.extend(self.network_warning([self._market_info_2]))
        warning_lines.extend(self.balance_warning([self._market_info_1]))
        warning_lines.extend(self.balance_warning([self._market_info_2]))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def set_order_completed(self, order_id: str):
        arb_side: Optional[ArbProposalSide] = self._order_id_side_map.get(order_id)
        if arb_side:
            arb_side.set_completed()

    def set_order_failed(self, order_id: str):
        arb_side: Optional[ArbProposalSide] = self._order_id_side_map.get(order_id)
        if arb_side:
            arb_side.set_failed()
            arb_side.set_completed()

    def did_complete_buy_order(self, order_completed_event: BuyOrderCompletedEvent):
        self.set_order_completed(order_id=order_completed_event.order_id)

        market_info: MarketTradingPairTuple = self.order_tracker.get_market_pair_from_order_id(
            order_completed_event.order_id
        )
        log_msg: str = f"Buy order completed on {market_info.market.name}: {order_completed_event.order_id}."
        if self.is_gateway_market(market_info):
            log_msg += f" txHash: {order_completed_event.exchange_order_id}"
        self.log_with_clock(logging.INFO, log_msg)
        self.notify_hb_app_with_timestamp(
            f"Bought {order_completed_event.base_asset_amount:.8f} "
            f"{order_completed_event.base_asset}-{order_completed_event.quote_asset} "
            f"on {market_info.market.name}."
        )

    def did_complete_sell_order(self, order_completed_event: SellOrderCompletedEvent):
        self.set_order_completed(order_id=order_completed_event.order_id)

        market_info: MarketTradingPairTuple = self.order_tracker.get_market_pair_from_order_id(
            order_completed_event.order_id
        )
        log_msg: str = f"Sell order completed on {market_info.market.name}: {order_completed_event.order_id}."
        if self.is_gateway_market(market_info):
            log_msg += f" txHash: {order_completed_event.exchange_order_id}"
        self.log_with_clock(logging.INFO, log_msg)
        self.notify_hb_app_with_timestamp(
            f"Sold {order_completed_event.base_asset_amount:.8f} "
            f"{order_completed_event.base_asset}-{order_completed_event.quote_asset} "
            f"on {market_info.market.name}."
        )

    def did_fail_order(self, order_failed_event: MarketOrderFailureEvent):
        self.set_order_failed(order_id=order_failed_event.order_id)

    def did_cancel_order(self, cancelled_event: OrderCancelledEvent):
        self.set_order_completed(order_id=cancelled_event.order_id)

    def did_expire_order(self, expired_event: OrderExpiredEvent):
        self.set_order_completed(order_id=expired_event.order_id)

    @property
    def tracked_limit_orders(self) -> List[Tuple[ConnectorBase, LimitOrder]]:
        return self._sb_order_tracker.tracked_limit_orders

    @property
    def tracked_market_orders(self) -> List[Tuple[ConnectorBase, MarketOrder]]:
        return self._sb_order_tracker.tracked_market_orders

    def start(self, clock: Clock, timestamp: float):
        super().start(clock, timestamp)

    def stop(self, clock: Clock):
        if self._main_task is not None:
            self._main_task.cancel()
            self._main_task = None
        super().stop(clock)
