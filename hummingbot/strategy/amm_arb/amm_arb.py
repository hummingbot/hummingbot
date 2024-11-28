import asyncio
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

    _market_infos: List[MarketTradingPairTuple]
    _min_profitability: Decimal
    _order_amount: Decimal
    _slippage_buffers: Dict[MarketTradingPairTuple, Decimal]
    _concurrent_orders_submission: bool
    _last_no_arb_reported: float
    _arb_proposals: Optional[List[ArbProposal]]
    _all_markets_ready: bool
    _ev_loop: asyncio.AbstractEventLoop
    _main_task: Optional[asyncio.Task]
    _last_timestamp: float
    _status_report_interval: float
    _quote_eth_rate_fetch_loop_task: Optional[asyncio.Task]
    _market_1_quote_eth_rate: None  # XXX (martin_kou): Why are these here?
    _market_2_quote_eth_rate: None  # XXX (martin_kou): Why are these here?
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
        market_infos: List[MarketTradingPairTuple],
        min_profitability: Decimal,
        order_amount: Decimal,
        slippage_buffers: Dict[MarketTradingPairTuple, Decimal],
        concurrent_orders_submission: bool = True,
        status_report_interval: float = 900,
        gateway_transaction_cancel_interval: int = 600,
        rate_source: Optional[RateOracle] = RateOracle.get_instance(),
    ):

        # log_msg: str = f"Inputs are: {market_infos}, {min_profitability}, {order_amount}, {slippage_buffers},{concurrent_orders_submission}"
        # self.log_with_clock(logging.INFO, log_msg)
        self._market_infos = market_infos
        self._min_profitability = min_profitability
        self._order_amount = order_amount
        self._slippage_buffers = slippage_buffers
        self._concurrent_orders_submission = concurrent_orders_submission
        self._last_no_arb_reported = 0
        self._all_arb_proposals = None
        self._all_markets_ready = False

        self._ev_loop = asyncio.get_event_loop()
        self._main_task = None

        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        markets_temp = []
        for market_info in market_infos:
            markets_temp.append(market_info.market)
        self.add_markets(markets_temp)
        self._quote_eth_rate_fetch_loop_task = None

        self._rate_source = rate_source

        self._cancel_outdated_orders_task = None
        self._gateway_transaction_cancel_interval = gateway_transaction_cancel_interval

        self._order_id_side_map: Dict[str, ArbProposalSide] = {}

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
                log_msg: str = "Ready to Roll !!"
                self.log_with_clock(logging.INFO, log_msg)
                self._main_task = safe_ensure_future(self.main())
        if self._cancel_outdated_orders_task is None or self._cancel_outdated_orders_task.done():
            self._cancel_outdated_orders_task = safe_ensure_future(self.apply_gateway_transaction_cancel_interval())

    async def main(self):
        """
        Optimized arbitrage execution loop that stops after reaching target amount:
        1. Builds global orderbook from all markets
        2. Efficiently matches orders until target amount is reached
        3. Applies fees and slippage
        4. Executes profitable trades
        """
        # Initialize empty lists for global orderbook
        global_bids = []
        global_asks = []
        # Build global orderbook
        for market_info in self._market_infos:
            # Get asks and bids from each market
            ask_entries = list(market_info.order_book_ask_entries())
            bid_entries = list(market_info.order_book_bid_entries())
            # Add market identifier to each entry
            for ask in ask_entries[:20]:
                global_asks.append(
                    {"price": ask.price, "amount": ask.amount, "market": market_info, "update_id": ask.update_id}
                )
            for bid in bid_entries[:20]:
                global_bids.append(
                    {"price": bid.price, "amount": bid.amount, "market": market_info, "update_id": bid.update_id}
                )
        # Sort global orderbook
        global_asks.sort(key=lambda x: x["price"])  # Sort asks ascending
        global_bids.sort(key=lambda x: x["price"], reverse=True)  # Sort bids descending
        # Find arbitrage opportunities
        arb_proposals = []
        total_amount_matched = 0
        # Start with highest bid and lowest ask
        bid_idx = 0
        ask_idx = 0
        while bid_idx < len(global_bids) and ask_idx < len(global_asks) and total_amount_matched < self._order_amount:
            best_bid = global_bids[bid_idx]
            best_ask = global_asks[ask_idx]
            # Skip if same market
            if best_bid["market"] == best_ask["market"]:
                ask_idx += 1
                continue
            # Calculate potential profit
            bid_price = best_bid["price"]
            ask_price = best_ask["price"]
            # If no profit potential exit
            if bid_price <= ask_price:
                break
            # Calculate maximum possible trade amount
            remaining_target = self._order_amount - total_amount_matched
            max_amount = min(best_bid["amount"], best_ask["amount"], remaining_target)
            # Skip if amount too small
            if max_amount <= 0:
                ask_idx += 1
                continue
            # Calculate fees
            bid_market = best_bid["market"].market
            ask_market = best_ask["market"].market
            # Initialize extra flat fees
            bid_extra_fees = []
            ask_extra_fees = []
            # Add network fees if applicable
            if hasattr(bid_market, "network_transaction_fee"):
                bid_extra_fees.append(getattr(bid_market, "network_transaction_fee"))
            if hasattr(ask_market, "network_transaction_fee"):
                ask_extra_fees.append(getattr(ask_market, "network_transaction_fee"))
            # Create arbitrage proposal
            buy_side = ArbProposalSide(
                market_info=best_ask["market"],
                is_buy=True,
                quote_price=ask_price,
                order_price=ask_price,
                amount=round(max_amount, 2),
                extra_flat_fees=ask_extra_fees,
            )
            sell_side = ArbProposalSide(
                market_info=best_bid["market"],
                is_buy=False,
                quote_price=bid_price,
                order_price=bid_price,
                amount=round(max_amount, 2),
                extra_flat_fees=bid_extra_fees,
            )
            proposal = ArbProposal(first_side=buy_side, second_side=sell_side)
            # Calculate profit after fees
            profit_pct = proposal.profit_pct(rate_source=self._rate_source, account_for_fee=True)
            # print(f"{proposal}  profit: {profit_pct}")
            if profit_pct >= self._min_profitability:
                arb_proposals.append(proposal)
                total_amount_matched += max_amount
                # Update amounts
                best_bid["amount"] -= max_amount
                best_ask["amount"] -= max_amount
                # If bid is exhausted, move to next bid
                if best_bid["amount"] <= 0:
                    bid_idx += 1
                    ask_idx = 0
                # If ask is exhausted, move to next ask
                elif best_ask["amount"] <= 0:
                    ask_idx += 1
            else:
                # If not profitable, move to next ask
                ask_idx += 1
                # If we've checked all asks for this bid, move to next bid
                if ask_idx >= len(global_asks):
                    bid_idx += 1
                    ask_idx = 0
        if len(arb_proposals) == 0:
            self.logger().info("No arbitrage opportunities found.")
            return
        # Apply slippage buffers to proposals
        await self.apply_slippage_buffers(arb_proposals)
        # Check if we have enough balance
        self.apply_budget_constraint(arb_proposals)
        # Execute the arbitrage trades
        await self.execute_arb_proposals(arb_proposals)

    async def apply_gateway_transaction_cancel_interval(self):
        # XXX (martin_kou): Concurrent cancellations are not supported before the nonce architecture is fixed.
        # See: https://app.shortcut.com/coinalpha/story/24553/nonce-architecture-in-current-amm-trade-and-evm-approve-apis-is-incorrect-and-causes-trouble-with-concurrent-requests
        gateway_connectors = []
        for market_info in self._market_infos:
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
                s_buffer = self._slippage_buffers[arb_side.market_info]
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
        # outstanding_orders = self.market_info_to_active_orders.get(self._market_info, [])
        for market_info in self._market_infos:
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
            buy_price = await market.get_quote_price(trading_pair, True, self._order_amount)
            sell_price = await market.get_quote_price(trading_pair, False, self._order_amount)

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
