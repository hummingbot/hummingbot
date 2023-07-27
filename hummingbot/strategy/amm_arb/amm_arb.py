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
from hummingbot.connector.gateway.gateway_price_shim import GatewayPriceShim
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
from hummingbot.strategy.amm_arb.utils import ArbProposal, create_arb_proposals
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

    _market_info_1: MarketTradingPairTuple
    _market_info_2: MarketTradingPairTuple
    _min_profitability: Decimal
    _order_amount: Decimal
    _market_1_slippage_buffer: Decimal
    _market_2_slippage_buffer: Decimal
    _concurrent_orders_submission: bool
    _last_no_arb_reported: float
    _arb_proposals: Optional[List[ArbProposal]]
    _all_markets_ready: bool
    _ev_loop: asyncio.AbstractEventLoop
    _main_task: Optional[asyncio.Task]
    _last_timestamp: float
    _status_report_interval: float
    _quote_eth_rate_fetch_loop_task: Optional[asyncio.Task]
    _market_1_quote_eth_rate: None          # XXX (martin_kou): Why are these here?
    _market_2_quote_eth_rate: None          # XXX (martin_kou): Why are these here?
    _rate_source: Optional[RateOracle]
    _cancel_outdated_orders_task: Optional[asyncio.Task]
    _gateway_transaction_cancel_interval: int

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global amm_logger
        if amm_logger is None:
            amm_logger = logging.getLogger(__name__)
        return amm_logger

    def init_params(self,
                    market_info_1: MarketTradingPairTuple,
                    market_info_2: MarketTradingPairTuple,
                    min_profitability: Decimal,
                    order_amount: Decimal,
                    market_1_slippage_buffer: Decimal = Decimal("0"),
                    market_2_slippage_buffer: Decimal = Decimal("0"),
                    concurrent_orders_submission: bool = True,
                    status_report_interval: float = 900,
                    gateway_transaction_cancel_interval: int = 600,
                    rate_source: Optional[RateOracle] = RateOracle.get_instance(),
                    ):
        """
        Assigns strategy parameters, this function must be called directly after init.
        The reason for this is to make the parameters discoverable on introspect (it is not possible on init of
        a Cython class).
        :param market_info_1: The first market
        :param market_info_2: The second market
        :param min_profitability: The minimum profitability for execute trades (e.g. 0.0003 for 0.3%)
        :param order_amount: The order amount
        :param market_1_slippage_buffer: The buffer for which to adjust order price for higher chance of
        the order getting filled. This is quite important for AMM which transaction takes a long time where a slippage
        is acceptable rather having the transaction get rejected. The submitted order price will be adjust higher
        for buy order and lower for sell order.
        :param market_2_slippage_buffer: The slipper buffer for market_2
        :param concurrent_orders_submission: whether to submit both arbitrage taker orders (buy and sell) simultaneously
        If false, the bot will wait for first exchange order filled before submitting the other order.
        :param status_report_interval: Amount of seconds to wait to refresh the status report
        :param gateway_transaction_cancel_interval: Amount of seconds to wait before trying to cancel orders that are
        blockchain transactions that have not been included in a block (they are still in the mempool).
        :param rate_source: The rate source to use for conversion rate - (RateOracle or FixedRateSource) - default is FixedRateSource
        """
        self._market_info_1 = market_info_1
        self._market_info_2 = market_info_2
        self._min_profitability = min_profitability
        self._order_amount = order_amount
        self._market_1_slippage_buffer = market_1_slippage_buffer
        self._market_2_slippage_buffer = market_2_slippage_buffer
        self._concurrent_orders_submission = concurrent_orders_submission
        self._last_no_arb_reported = 0
        self._all_arb_proposals = None
        self._all_markets_ready = False

        self._ev_loop = asyncio.get_event_loop()
        self._main_task = None

        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([market_info_1.market, market_info_2.market])
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
        return market_info.market.name in sorted(
            AllConnectorSettings.get_gateway_amm_connector_names()
        )

    @staticmethod
    @lru_cache(maxsize=10)
    def is_gateway_market_evm_compatible(market_info: MarketTradingPairTuple) -> bool:
        connector_spec: Dict[str, str] = GatewayConnectionSetting.get_connector_spec_from_market_name(market_info.market.name)
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
                        msg = ', '.join([k for k, v in market.status_dict.items() if v is False])
                        self.logger().warning(f"{market.name} not ready: waiting for {msg}.")
                return
            else:
                self.logger().info("Markets are ready. Trading started.")

        if self.ready_for_new_arb_trades():
            if self._main_task is None or self._main_task.done():
                self._main_task = safe_ensure_future(self.main())
        if self._cancel_outdated_orders_task is None or self._cancel_outdated_orders_task.done():
            self._cancel_outdated_orders_task = safe_ensure_future(self.apply_gateway_transaction_cancel_interval())

    async def main(self):
        """
        The main procedure for the arbitrage strategy. It first creates arbitrage proposals, filters for ones that meets
        min profitability required, applies the slippage buffer, applies budget constraint, then finally execute the
        arbitrage.
        """
        self._all_arb_proposals = await create_arb_proposals(
            market_info_1=self._market_info_1,
            market_info_2=self._market_info_2,
            market_1_extra_flat_fees=(
                [getattr(self._market_info_1.market, "network_transaction_fee")]
                if hasattr(self._market_info_1.market, "network_transaction_fee")
                else []
            ),
            market_2_extra_flat_fees=(
                [getattr(self._market_info_2.market, "network_transaction_fee")]
                if hasattr(self._market_info_2.market, "network_transaction_fee")
                else []
            ),
            order_amount=self._order_amount,
        )
        profitable_arb_proposals: List[ArbProposal] = [
            t.copy() for t in self._all_arb_proposals
            if t.profit_pct(
                rate_source=self._rate_source,
                account_for_fee=True,
            ) >= self._min_profitability
        ]
        if len(profitable_arb_proposals) == 0:
            if self._last_no_arb_reported < self.current_timestamp - 20.:
                self.logger().info("No arbitrage opportunity.\n" +
                                   "\n".join(self.short_proposal_msg(self._all_arb_proposals, False)))
                self._last_no_arb_reported = self.current_timestamp
            return
        await self.apply_slippage_buffers(profitable_arb_proposals)
        self.apply_budget_constraint(profitable_arb_proposals)
        await self.execute_arb_proposals(profitable_arb_proposals)

    async def apply_gateway_transaction_cancel_interval(self):
        # XXX (martin_kou): Concurrent cancellations are not supported before the nonce architecture is fixed.
        # See: https://app.shortcut.com/coinalpha/story/24553/nonce-architecture-in-current-amm-trade-and-evm-approve-apis-is-incorrect-and-causes-trouble-with-concurrent-requests
        gateway_connectors = []
        if self.is_gateway_market(self._market_info_1) and self.is_gateway_market_evm_compatible(self._market_info_1):
            gateway_connectors.append(cast(GatewayEVMAMM, self._market_info_1.market))
        if self.is_gateway_market(self._market_info_2) and self.is_gateway_market_evm_compatible(self._market_info_2):
            gateway_connectors.append(cast(GatewayEVMAMM, self._market_info_2.market))

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
                s_buffer = self._market_1_slippage_buffer if market == self._market_info_1.market \
                    else self._market_2_slippage_buffer
                if not arb_side.is_buy:
                    s_buffer *= Decimal("-1")
                arb_side.order_price *= Decimal("1") + s_buffer
                arb_side.order_price = market.quantize_order_price(arb_side.market_info.trading_pair,
                                                                   arb_side.order_price)

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
                    self.logger().info(f"Can't arbitrage, {market.display_name} "
                                       f"{token} balance "
                                       f"({balance}) is below required order amount ({required}).")
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
                self.log_with_clock(logging.INFO,
                                    f"Placing {side} order for {arb_side.amount} {arb_side.market_info.base_asset} "
                                    f"at {arb_side.market_info.market.display_name} at {arb_side.order_price} price")

                order_id: str = await self.place_arb_order(
                    arb_side.market_info,
                    arb_side.is_buy,
                    arb_side.amount,
                    arb_side.order_price
                )

                self._order_id_side_map.update({
                    order_id: arb_side
                })

                if not self._concurrent_orders_submission:
                    await arb_side.completed_event.wait()
                    if arb_side.is_failed:
                        self.log_with_clock(logging.ERROR,
                                            f"Order {order_id} seems to have failed in this arbitrage opportunity. "
                                            f"Dropping Arbitrage Proposal. ")
                        return

            await arb_proposal.wait()

    async def place_arb_order(
            self,
            market_info: MarketTradingPairTuple,
            is_buy: bool,
            amount: Decimal,
            order_price: Decimal) -> str:
        place_order_fn: Callable[[MarketTradingPairTuple, Decimal, OrderType, Decimal], str] = \
            cast(Callable, self.buy_with_specific_market if is_buy else self.sell_with_specific_market)

        # If I'm placing order under a gateway price shim, then the prices in the proposal are fake - I should fetch
        # the real prices before I make the order on the gateway side. Otherwise, the orders are gonna fail because
        # the limit price set for them will not match market prices.
        if self.is_gateway_market(market_info):
            slippage_buffer: Decimal = self._market_1_slippage_buffer
            if market_info == self._market_info_2:
                slippage_buffer = self._market_2_slippage_buffer
            slippage_buffer_factor: Decimal = Decimal(1) + slippage_buffer
            if not is_buy:
                slippage_buffer_factor = Decimal(1) - slippage_buffer
            market: GatewayEVMAMM = cast(GatewayEVMAMM, market_info.market)
            if GatewayPriceShim.get_instance().has_price_shim(
                    market.connector_name, market.chain, market.network, market_info.trading_pair):
                order_price = await market.get_order_price(market_info.trading_pair, is_buy, amount, ignore_shim=True)
                order_price *= slippage_buffer_factor

        return place_order_fn(market_info, amount, market_info.market.get_taker_order_type(), order_price)

    def ready_for_new_arb_trades(self) -> bool:
        """
        Returns True if there is no outstanding unfilled order.
        """
        # outstanding_orders = self.market_info_to_active_orders.get(self._market_info, [])
        for market_info in [self._market_info_1, self._market_info_2]:
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
            lines.append(f"{'    ' if indented else ''}{side1} at {market_1_name}"
                         f", {side2} at {market_2_name}: "
                         f"{profit_pct:.2%}")
        return lines

    def get_fixed_rates_df(self):
        columns = ["Pair", "Rate"]
        quotes_pair: str = f"{self._market_info_2.quote_asset}-{self._market_info_1.quote_asset}"
        bases_pair: str = f"{self._market_info_2.base_asset}-{self._market_info_1.base_asset}"
        data = [[quotes_pair, PerformanceMetrics.smart_round(self._rate_source.get_pair_rate(quotes_pair))],
                [bases_pair, PerformanceMetrics.smart_round(self._rate_source.get_pair_rate(bases_pair))]]
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
            buy_price = PerformanceMetrics.smart_round(Decimal(str(buy_price)), 8) if buy_price is not None else '-'
            sell_price = PerformanceMetrics.smart_round(Decimal(str(sell_price)), 8) if sell_price is not None else '-'
            mid_price = PerformanceMetrics.smart_round(((buy_price + sell_price) / 2), 8) if '-' not in [buy_price, sell_price] else '-'

            data.append([
                market.display_name,
                trading_pair,
                sell_price,
                buy_price,
                mid_price
            ])
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
                ["", "  Network Fees:"] +
                ["    " + line for line in network_fees_df.to_string(index=False).split("\n")]
            )

        assets_df = self.wallet_balance_data_frame([self._market_info_1, self._market_info_2])
        lines.extend(["", "  Assets:"] +
                     ["    " + line for line in str(assets_df).split("\n")])

        lines.extend(["", "  Profitability:"] + self.short_proposal_msg(self._all_arb_proposals))

        fixed_rates_df = self.get_fixed_rates_df()
        lines.extend(["", f"  Exchange Rates: ({str(self._rate_source)})"] +
                     ["    " + line for line in str(fixed_rates_df).split("\n")])

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
        self.notify_hb_app_with_timestamp(f"Bought {order_completed_event.base_asset_amount:.8f} "
                                          f"{order_completed_event.base_asset}-{order_completed_event.quote_asset} "
                                          f"on {market_info.market.name}.")

    def did_complete_sell_order(self, order_completed_event: SellOrderCompletedEvent):
        self.set_order_completed(order_id=order_completed_event.order_id)

        market_info: MarketTradingPairTuple = self.order_tracker.get_market_pair_from_order_id(
            order_completed_event.order_id
        )
        log_msg: str = f"Sell order completed on {market_info.market.name}: {order_completed_event.order_id}."
        if self.is_gateway_market(market_info):
            log_msg += f" txHash: {order_completed_event.exchange_order_id}"
        self.log_with_clock(logging.INFO, log_msg)
        self.notify_hb_app_with_timestamp(f"Sold {order_completed_event.base_asset_amount:.8f} "
                                          f"{order_completed_event.base_asset}-{order_completed_event.quote_asset} "
                                          f"on {market_info.market.name}.")

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
