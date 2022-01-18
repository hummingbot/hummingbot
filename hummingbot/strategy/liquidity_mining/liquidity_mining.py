from decimal import Decimal
import logging
import asyncio
from typing import Dict, List, Set
import pandas as pd
import numpy as np
from statistics import mean
from hummingbot.core.clock import Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from .data_types import Proposal, PriceSize
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.utils.estimate_fee import estimate_fee
from hummingbot.strategy.pure_market_making.inventory_skew_calculator import (
    calculate_bid_ask_ratios_from_base_asset_ratio
)
from hummingbot.connector.parrot import get_campaign_summary
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.utils import order_age

NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_nan = Decimal("NaN")
lms_logger = None


class LiquidityMiningStrategy(StrategyPyBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global lms_logger
        if lms_logger is None:
            lms_logger = logging.getLogger(__name__)
        return lms_logger

    def init_params(self,
                    exchange: ExchangeBase,
                    market_infos: Dict[str, MarketTradingPairTuple],
                    token: str,
                    order_amount: Decimal,
                    spread: Decimal,
                    inventory_skew_enabled: bool,
                    target_base_pct: Decimal,
                    order_refresh_time: float,
                    order_refresh_tolerance_pct: Decimal,
                    inventory_range_multiplier: Decimal = Decimal("1"),
                    volatility_interval: int = 60 * 5,
                    avg_volatility_period: int = 10,
                    volatility_to_spread_multiplier: Decimal = Decimal("1"),
                    max_spread: Decimal = Decimal("-1"),
                    max_order_age: float = 60. * 60.,
                    status_report_interval: float = 900,
                    hb_app_notification: bool = False):
        self._exchange = exchange
        self._market_infos = market_infos
        self._token = token
        self._order_amount = order_amount
        self._spread = spread
        self._order_refresh_time = order_refresh_time
        self._order_refresh_tolerance_pct = order_refresh_tolerance_pct
        self._inventory_skew_enabled = inventory_skew_enabled
        self._target_base_pct = target_base_pct
        self._inventory_range_multiplier = inventory_range_multiplier
        self._volatility_interval = volatility_interval
        self._avg_volatility_period = avg_volatility_period
        self._volatility_to_spread_multiplier = volatility_to_spread_multiplier
        self._max_spread = max_spread
        self._max_order_age = max_order_age
        self._ev_loop = asyncio.get_event_loop()
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._ready_to_trade = False
        self._refresh_times = {market: 0 for market in market_infos}
        self._token_balances = {}
        self._sell_budgets = {}
        self._buy_budgets = {}
        self._mid_prices = {market: [] for market in market_infos}
        self._volatility = {market: s_decimal_nan for market in self._market_infos}
        self._last_vol_reported = 0.
        self._hb_app_notification = hb_app_notification

        self.add_markets([exchange])

    @property
    def active_orders(self):
        """
        List active orders (they have been sent to the market and have not been cancelled yet)
        """
        limit_orders = self.order_tracker.active_limit_orders
        return [o[1] for o in limit_orders]

    @property
    def sell_budgets(self):
        return self._sell_budgets

    @property
    def buy_budgets(self):
        return self._buy_budgets

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self._ready_to_trade:
            # Check if there are restored orders, they should be canceled before strategy starts.
            self._ready_to_trade = self._exchange.ready and len(self._exchange.limit_orders) == 0
            if not self._exchange.ready:
                self.logger().warning(f"{self._exchange.name} is not ready. Please wait...")
                return
            else:
                self.logger().info(f"{self._exchange.name} is ready. Trading started.")
                self.create_budget_allocation()

        self.update_mid_prices()
        self.update_volatility()
        proposals = self.create_base_proposals()
        self._token_balances = self.adjusted_available_balances()
        if self._inventory_skew_enabled:
            self.apply_inventory_skew(proposals)
        self.apply_budget_constraint(proposals)
        self.cancel_active_orders(proposals)
        self.execute_orders_proposal(proposals)

        self._last_timestamp = timestamp

    async def active_orders_df(self) -> pd.DataFrame:
        """
        Return the active orders in a DataFrame.
        """
        size_q_col = f"Amt({self._token})" if self.is_token_a_quote_token() else "Amt(Quote)"
        columns = ["Market", "Side", "Price", "Spread", "Amount", size_q_col, "Age"]
        data = []
        for order in self.active_orders:
            mid_price = self._market_infos[order.trading_pair].get_mid_price()
            spread = 0 if mid_price == 0 else abs(order.price - mid_price) / mid_price
            size_q = order.quantity * mid_price
            age = order_age(order)
            # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
            age_txt = "n/a" if age <= 0. else pd.Timestamp(age, unit='s').strftime('%H:%M:%S')
            data.append([
                order.trading_pair,
                "buy" if order.is_buy else "sell",
                float(order.price),
                f"{spread:.2%}",
                float(order.quantity),
                float(size_q),
                age_txt
            ])
        df = pd.DataFrame(data=data, columns=columns)
        df.sort_values(by=["Market", "Side"], inplace=True)
        return df

    def budget_status_df(self) -> pd.DataFrame:
        """
        Return the trader's budget in a DataFrame
        """
        data = []
        columns = ["Market", f"Budget({self._token})", "Base bal", "Quote bal", "Base/Quote"]
        for market, market_info in self._market_infos.items():
            mid_price = market_info.get_mid_price()
            base_bal = self._sell_budgets[market]
            quote_bal = self._buy_budgets[market]
            total_bal_in_quote = (base_bal * mid_price) + quote_bal
            total_bal_in_token = total_bal_in_quote
            if not self.is_token_a_quote_token():
                total_bal_in_token = base_bal + (quote_bal / mid_price)
            base_pct = (base_bal * mid_price) / total_bal_in_quote if total_bal_in_quote > 0 else s_decimal_zero
            quote_pct = quote_bal / total_bal_in_quote if total_bal_in_quote > 0 else s_decimal_zero
            data.append([
                market,
                float(total_bal_in_token),
                float(base_bal),
                float(quote_bal),
                f"{base_pct:.0%} / {quote_pct:.0%}"
            ])
        df = pd.DataFrame(data=data, columns=columns).replace(np.nan, '', regex=True)
        df.sort_values(by=["Market"], inplace=True)
        return df

    def market_status_df(self) -> pd.DataFrame:
        """
        Return the market status (prices, volatility) in a DataFrame
        """
        data = []
        columns = ["Market", "Mid price", "Best bid", "Best ask", "Volatility"]
        for market, market_info in self._market_infos.items():
            mid_price = market_info.get_mid_price()
            best_bid = self._exchange.get_price(market, False)
            best_ask = self._exchange.get_price(market, True)
            best_bid_pct = abs(best_bid - mid_price) / mid_price
            best_ask_pct = (best_ask - mid_price) / mid_price
            data.append([
                market,
                float(mid_price),
                f"{best_bid_pct:.2%}",
                f"{best_ask_pct:.2%}",
                "" if self._volatility[market].is_nan() else f"{self._volatility[market]:.2%}",
            ])
        df = pd.DataFrame(data=data, columns=columns).replace(np.nan, '', regex=True)
        df.sort_values(by=["Market"], inplace=True)
        return df

    async def miner_status_df(self) -> pd.DataFrame:
        """
        Return the miner status (payouts, rewards, liquidity, etc.) in a DataFrame
        """
        data = []
        g_sym = RateOracle.global_token_symbol
        columns = ["Market", "Payout", "Reward/wk", "Liquidity", "Yield/yr", "Max spread"]
        campaigns = await get_campaign_summary(self._exchange.display_name, list(self._market_infos.keys()))
        for market, campaign in campaigns.items():
            reward = await RateOracle.global_value(campaign.payout_asset, campaign.reward_per_wk)
            data.append([
                market,
                campaign.payout_asset,
                f"{g_sym}{reward:.0f}",
                f"{g_sym}{campaign.liquidity_usd:.0f}",
                f"{campaign.apy:.2%}",
                f"{campaign.spread_max:.2%}%"
            ])
        df = pd.DataFrame(data=data, columns=columns).replace(np.nan, '', regex=True)
        df.sort_values(by=["Market"], inplace=True)
        return df

    async def format_status(self) -> str:
        """
        Return the budget, market, miner and order statuses.
        """
        if not self._ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(list(self._market_infos.values())))

        budget_df = self.budget_status_df()
        lines.extend(["", "  Budget:"] + ["    " + line for line in budget_df.to_string(index=False).split("\n")])

        market_df = self.market_status_df()
        lines.extend(["", "  Markets:"] + ["    " + line for line in market_df.to_string(index=False).split("\n")])

        miner_df = await self.miner_status_df()
        if not miner_df.empty:
            lines.extend(["", "  Miner:"] + ["    " + line for line in miner_df.to_string(index=False).split("\n")])

        # See if there are any open orders.
        if len(self.active_orders) > 0:
            df = await self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active maker orders."])

        warning_lines.extend(self.balance_warning(list(self._market_infos.values())))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)

    def start(self, clock: Clock, timestamp: float):
        restored_orders = self._exchange.limit_orders
        for order in restored_orders:
            self._exchange.cancel(order.trading_pair, order.client_order_id)

    def stop(self, clock: Clock):
        pass

    def create_base_proposals(self):
        """
        Each tick this strategy creates a set of proposals based on the market_info and the parameters from the
        constructor.
        """
        proposals = []
        for market, market_info in self._market_infos.items():
            spread = self._spread
            if not self._volatility[market].is_nan():
                # volatility applies only when it is higher than the spread setting.
                spread = max(spread, self._volatility[market] * self._volatility_to_spread_multiplier)
            if self._max_spread > s_decimal_zero:
                spread = min(spread, self._max_spread)
            mid_price = market_info.get_mid_price()
            buy_price = mid_price * (Decimal("1") - spread)
            buy_price = self._exchange.quantize_order_price(market, buy_price)
            buy_size = self.base_order_size(market, buy_price)
            sell_price = mid_price * (Decimal("1") + spread)
            sell_price = self._exchange.quantize_order_price(market, sell_price)
            sell_size = self.base_order_size(market, sell_price)
            proposals.append(Proposal(market, PriceSize(buy_price, buy_size), PriceSize(sell_price, sell_size)))
        return proposals

    def total_port_value_in_token(self) -> Decimal:
        """
        Total portfolio value in self._token amount
        """
        all_bals = self.adjusted_available_balances()
        port_value = all_bals.get(self._token, s_decimal_zero)
        for market, market_info in self._market_infos.items():
            base, quote = market.split("-")
            if self.is_token_a_quote_token():
                port_value += all_bals[base] * market_info.get_mid_price()
            else:
                port_value += all_bals[quote] / market_info.get_mid_price()
        return port_value

    def create_budget_allocation(self):
        """
        Create buy and sell budgets for every market
        """
        self._sell_budgets = {m: s_decimal_zero for m in self._market_infos}
        self._buy_budgets = {m: s_decimal_zero for m in self._market_infos}
        portfolio_value = self.total_port_value_in_token()
        market_portion = portfolio_value / len(self._market_infos)
        balances = self.adjusted_available_balances()
        for market, market_info in self._market_infos.items():
            base, quote = market.split("-")
            if self.is_token_a_quote_token():
                self._sell_budgets[market] = balances[base]
                buy_budget = market_portion - (balances[base] * market_info.get_mid_price())
                if buy_budget > s_decimal_zero:
                    self._buy_budgets[market] = buy_budget
            else:
                self._buy_budgets[market] = balances[quote]
                sell_budget = market_portion - (balances[quote] / market_info.get_mid_price())
                if sell_budget > s_decimal_zero:
                    self._sell_budgets[market] = sell_budget

    def base_order_size(self, trading_pair: str, price: Decimal = s_decimal_zero):
        base, quote = trading_pair.split("-")
        if self._token == base:
            return self._order_amount
        if price == s_decimal_zero:
            price = self._market_infos[trading_pair].get_mid_price()
        return self._order_amount / price

    def apply_budget_constraint(self, proposals: List[Proposal]):
        balances = self._token_balances.copy()
        for proposal in proposals:
            if balances[proposal.base()] < proposal.sell.size:
                proposal.sell.size = balances[proposal.base()]
            proposal.sell.size = self._exchange.quantize_order_amount(proposal.market, proposal.sell.size)
            balances[proposal.base()] -= proposal.sell.size

            quote_size = proposal.buy.size * proposal.buy.price
            quote_size = balances[proposal.quote()] if balances[proposal.quote()] < quote_size else quote_size
            buy_fee = estimate_fee(self._exchange.name, True)
            buy_size = quote_size / (proposal.buy.price * (Decimal("1") + buy_fee.percent))
            proposal.buy.size = self._exchange.quantize_order_amount(proposal.market, buy_size)
            balances[proposal.quote()] -= quote_size

    def is_within_tolerance(self, cur_orders: List[LimitOrder], proposal: Proposal):
        """
        False if there are no buys or sells or if the difference between the proposed price and current price is less
        than the tolerance. The tolerance value is strict max, cannot be equal.
        """
        cur_buy = [o for o in cur_orders if o.is_buy]
        cur_sell = [o for o in cur_orders if not o.is_buy]
        if (cur_buy and proposal.buy.size <= 0) or (cur_sell and proposal.sell.size <= 0):
            return False
        if cur_buy and \
                abs(proposal.buy.price - cur_buy[0].price) / cur_buy[0].price > self._order_refresh_tolerance_pct:
            return False
        if cur_sell and \
                abs(proposal.sell.price - cur_sell[0].price) / cur_sell[0].price > self._order_refresh_tolerance_pct:
            return False
        return True

    def cancel_active_orders(self, proposals: List[Proposal]):
        """
        Cancel any orders that have an order age greater than self._max_order_age or if orders are not within tolerance
        """
        for proposal in proposals:
            to_cancel = False
            cur_orders = [o for o in self.active_orders if o.trading_pair == proposal.market]
            if cur_orders and any(order_age(o) > self._max_order_age for o in cur_orders):
                to_cancel = True
            elif self._refresh_times[proposal.market] <= self.current_timestamp and \
                    cur_orders and not self.is_within_tolerance(cur_orders, proposal):
                to_cancel = True
            if to_cancel:
                for order in cur_orders:
                    self.cancel_order(self._market_infos[proposal.market], order.client_order_id)
                    # To place new order on the next tick
                    self._refresh_times[order.trading_pair] = self.current_timestamp + 0.1

    def execute_orders_proposal(self, proposals: List[Proposal]):
        """
        Execute a list of proposals if the current timestamp is less than its refresh timestamp.
        Update the refresh timestamp.
        """
        for proposal in proposals:
            maker_order_type: OrderType = self._exchange.get_maker_order_type()
            cur_orders = [o for o in self.active_orders if o.trading_pair == proposal.market]
            if cur_orders or self._refresh_times[proposal.market] > self.current_timestamp:
                continue
            mid_price = self._market_infos[proposal.market].get_mid_price()
            spread = s_decimal_zero
            if proposal.buy.size > 0:
                spread = abs(proposal.buy.price - mid_price) / mid_price
                self.logger().info(f"({proposal.market}) Creating a bid order {proposal.buy} value: "
                                   f"{proposal.buy.size * proposal.buy.price:.2f} {proposal.quote()} spread: "
                                   f"{spread:.2%}")
                self.buy_with_specific_market(
                    self._market_infos[proposal.market],
                    proposal.buy.size,
                    order_type=maker_order_type,
                    price=proposal.buy.price
                )
            if proposal.sell.size > 0:
                spread = abs(proposal.sell.price - mid_price) / mid_price
                self.logger().info(f"({proposal.market}) Creating an ask order at {proposal.sell} value: "
                                   f"{proposal.sell.size * proposal.sell.price:.2f} {proposal.quote()} spread: "
                                   f"{spread:.2%}")
                self.sell_with_specific_market(
                    self._market_infos[proposal.market],
                    proposal.sell.size,
                    order_type=maker_order_type,
                    price=proposal.sell.price
                )
            if proposal.buy.size > 0 or proposal.sell.size > 0:
                if not self._volatility[proposal.market].is_nan() and spread > self._spread:
                    adjusted_vol = self._volatility[proposal.market] * self._volatility_to_spread_multiplier
                    if adjusted_vol > self._spread:
                        self.logger().info(f"({proposal.market}) Spread is widened to {spread:.2%} due to high "
                                           f"market volatility")

                self._refresh_times[proposal.market] = self.current_timestamp + self._order_refresh_time

    def is_token_a_quote_token(self):
        """
        Check if self._token is a quote token
        """
        quotes = self.all_quote_tokens()
        if len(quotes) == 1 and self._token in quotes:
            return True
        return False

    def all_base_tokens(self) -> Set[str]:
        """
        Get the base token (left-hand side) from all markets in this strategy
        """
        tokens = set()
        for market in self._market_infos:
            tokens.add(market.split("-")[0])
        return tokens

    def all_quote_tokens(self) -> Set[str]:
        """
        Get the quote token (right-hand side) from all markets in this strategy
        """
        tokens = set()
        for market in self._market_infos:
            tokens.add(market.split("-")[1])
        return tokens

    def all_tokens(self) -> Set[str]:
        """
        Return a list of all tokens involved in this strategy (base and quote)
        """
        tokens = set()
        for market in self._market_infos:
            tokens.update(market.split("-"))
        return tokens

    def adjusted_available_balances(self) -> Dict[str, Decimal]:
        """
        Calculates all available balances, account for amount attributed to orders and reserved balance.
        :return: a dictionary of token and its available balance
        """
        tokens = self.all_tokens()
        adjusted_bals = {t: s_decimal_zero for t in tokens}
        total_bals = {t: s_decimal_zero for t in tokens}
        total_bals.update(self._exchange.get_all_balances())
        for token in tokens:
            adjusted_bals[token] = self._exchange.get_available_balance(token)
        for order in self.active_orders:
            base, quote = order.trading_pair.split("-")
            if order.is_buy:
                adjusted_bals[quote] += order.quantity * order.price
            else:
                adjusted_bals[base] += order.quantity
        return adjusted_bals

    def apply_inventory_skew(self, proposals: List[Proposal]):
        """
        Apply an inventory split between the quote and base asset
        """
        for proposal in proposals:
            buy_budget = self._buy_budgets[proposal.market]
            sell_budget = self._sell_budgets[proposal.market]
            mid_price = self._market_infos[proposal.market].get_mid_price()
            total_order_size = proposal.sell.size + proposal.buy.size
            bid_ask_ratios = calculate_bid_ask_ratios_from_base_asset_ratio(
                float(sell_budget),
                float(buy_budget),
                float(mid_price),
                float(self._target_base_pct),
                float(total_order_size * self._inventory_range_multiplier)
            )
            proposal.buy.size *= Decimal(bid_ask_ratios.bid_ratio)
            proposal.sell.size *= Decimal(bid_ask_ratios.ask_ratio)

    def did_fill_order(self, event):
        """
        Check if order has been completed, log it, notify the hummingbot application, and update budgets.
        """
        order_id = event.order_id
        market_info = self.order_tracker.get_shadow_market_pair_from_order_id(order_id)
        if market_info is not None:
            if event.trade_type is TradeType.BUY:
                msg = f"({market_info.trading_pair}) Maker BUY order (price: {event.price}) of {event.amount} " \
                      f"{market_info.base_asset} is filled."
                self.log_with_clock(logging.INFO, msg)
                self.notify_hb_app_with_timestamp(msg)
                self._buy_budgets[market_info.trading_pair] -= (event.amount * event.price)
                self._sell_budgets[market_info.trading_pair] += event.amount
            else:
                msg = f"({market_info.trading_pair}) Maker SELL order (price: {event.price}) of {event.amount} " \
                      f"{market_info.base_asset} is filled."
                self.log_with_clock(logging.INFO, msg)
                self.notify_hb_app_with_timestamp(msg)
                self._sell_budgets[market_info.trading_pair] -= event.amount
                self._buy_budgets[market_info.trading_pair] += (event.amount * event.price)

    def update_mid_prices(self):
        """
        Query asset markets for mid price
        """
        for market in self._market_infos:
            mid_price = self._market_infos[market].get_mid_price()
            self._mid_prices[market].append(mid_price)
            # To avoid memory leak, we store only the last part of the list needed for volatility calculation
            max_len = self._volatility_interval * self._avg_volatility_period
            self._mid_prices[market] = self._mid_prices[market][-1 * max_len:]

    def update_volatility(self):
        """
        Update volatility data from the market
        """
        self._volatility = {market: s_decimal_nan for market in self._market_infos}
        for market, mid_prices in self._mid_prices.items():
            last_index = len(mid_prices) - 1
            atr = []
            first_index = last_index - (self._volatility_interval * self._avg_volatility_period)
            first_index = max(first_index, 0)
            for i in range(last_index, first_index, self._volatility_interval * -1):
                prices = mid_prices[i - self._volatility_interval + 1: i + 1]
                if not prices:
                    break
                atr.append((max(prices) - min(prices)) / min(prices))
            if atr:
                self._volatility[market] = mean(atr)
        if self._last_vol_reported < self.current_timestamp - self._volatility_interval:
            for market, vol in self._volatility.items():
                if not vol.is_nan():
                    self.logger().info(f"{market} volatility: {vol:.2%}")
            self._last_vol_reported = self.current_timestamp

    def notify_hb_app(self, msg: str):
        """
        Send a message to the hummingbot application
        """
        if self._hb_app_notification:
            super().notify_hb_app(msg)
