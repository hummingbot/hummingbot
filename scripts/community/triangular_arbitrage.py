import logging
import math

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.strategy.script_strategy_base import Decimal, OrderType, ScriptStrategyBase


class TriangularArbitrage(ScriptStrategyBase):
    """
    BotCamp Cohort: Sept 2022
    Design Template: https://hummingbot-foundation.notion.site/Triangular-Arbitrage-07ef29ee97d749e1afa798a024813c88
    Video: https://www.loom.com/share/b6781130251945d4b51d6de3f8434047
    Description:
    This script executes arbitrage trades on 3 markets of the same exchange when a price discrepancy
    among those markets found.

    - All orders are executed linearly. That is the second order is placed after the first one is
    completely filled and the third order is placed after the second.
    - The script allows you to hold mainly one asset in your inventory (holding_asset).
    - It always starts trades round by selling the holding asset and ends by buying it.
    - There are 2 possible arbitrage trades directions: "direct" and "reverse".
        Example with USDT holding asset:
        1. Direct: buy ADA-USDT > sell ADA-BTC > sell BTC-USDT
        2. Reverse: buy BTC-USDT > buy ADA-BTC > sell ADA-USDT
    - The order amount is fixed and set in holding asset
    - The strategy has 2nd and 3d orders creation check and makes several trials if there is a failure
    - Profit is calculated each round and total profit is checked for the kill_switch to prevent from excessive losses
    - !!! Profitability calculation doesn't take into account trading fees, set min_profitability to at least 3 * fee
    """
    # Config params
    connector_name: str = "kucoin"
    first_pair: str = "ADA-USDT"
    second_pair: str = "ADA-BTC"
    third_pair: str = "BTC-USDT"
    holding_asset: str = "USDT"

    min_profitability: Decimal = Decimal("0.5")
    order_amount_in_holding_asset: Decimal = Decimal("20")

    kill_switch_enabled: bool = True
    kill_switch_rate = Decimal("-2")

    # Class params
    status: str = "NOT_INIT"
    trading_pair: dict = {}
    order_side: dict = {}
    profit: dict = {}
    order_amount: dict = {}
    profitable_direction: str = ""
    place_order_trials_count: int = 0
    place_order_trials_limit: int = 10
    place_order_failure: bool = False
    order_candidate = None
    initial_spent_amount = Decimal("0")
    total_profit = Decimal("0")
    total_profit_pct = Decimal("0")

    markets = {connector_name: {first_pair, second_pair, third_pair}}

    @property
    def connector(self):
        """
        The only connector in this strategy, define it here for easy access
        """
        return self.connectors[self.connector_name]

    def on_tick(self):
        """
        Every tick the strategy calculates the profitability of both direct and reverse direction.
        If the profitability of any direction is large enough it starts the arbitrage by creating and processing
        the first order candidate.
        """
        if self.status == "NOT_INIT":
            self.init_strategy()

        if self.arbitrage_started():
            return

        if not self.ready_for_new_orders():
            return

        self.profit["direct"], self.order_amount["direct"] = self.calculate_profit(self.trading_pair["direct"],
                                                                                   self.order_side["direct"])
        self.profit["reverse"], self.order_amount["reverse"] = self.calculate_profit(self.trading_pair["reverse"],
                                                                                     self.order_side["reverse"])
        self.log_with_clock(logging.INFO, f"Profit direct: {round(self.profit['direct'], 2)}, "
                                          f"Profit reverse: {round(self.profit['reverse'], 2)}")

        if self.profit["direct"] < self.min_profitability and self.profit["reverse"] < self.min_profitability:
            return

        self.profitable_direction = "direct" if self.profit["direct"] > self.profit["reverse"] else "reverse"
        self.start_arbitrage(self.trading_pair[self.profitable_direction],
                             self.order_side[self.profitable_direction],
                             self.order_amount[self.profitable_direction])

    def init_strategy(self):
        """
        Initializes strategy once before the start.
        """
        self.status = "ACTIVE"
        self.check_trading_pair()
        self.set_trading_pair()
        self.set_order_side()

    def check_trading_pair(self):
        """
        Checks if the pairs specified in the config are suitable for the triangular arbitrage.
        They should have only 3 common assets with holding_asset among them.
        """
        base_1, quote_1 = split_hb_trading_pair(self.first_pair)
        base_2, quote_2 = split_hb_trading_pair(self.second_pair)
        base_3, quote_3 = split_hb_trading_pair(self.third_pair)
        all_assets = {base_1, base_2, base_3, quote_1, quote_2, quote_3}
        if len(all_assets) != 3 or self.holding_asset not in all_assets:
            self.status = "NOT_ACTIVE"
            self.log_with_clock(logging.WARNING, f"Pairs {self.first_pair}, {self.second_pair}, {self.third_pair} "
                                                 f"are not suited for triangular arbitrage!")

    def set_trading_pair(self):
        """
        Rearrange trading pairs so that the first and last pair contains holding asset.
        We start trading round by selling holding asset and finish by buying it.
        Makes 2 tuples for "direct" and "reverse" directions and assigns them to the corresponding dictionary.
        """
        if self.holding_asset not in self.first_pair:
            pairs_ordered = (self.second_pair, self.first_pair, self.third_pair)
        elif self.holding_asset not in self.second_pair:
            pairs_ordered = (self.first_pair, self.second_pair, self.third_pair)
        else:
            pairs_ordered = (self.first_pair, self.third_pair, self.second_pair)

        self.trading_pair["direct"] = pairs_ordered
        self.trading_pair["reverse"] = pairs_ordered[::-1]

    def set_order_side(self):
        """
        Sets order sides (1 = buy, 0 = sell) for already ordered trading pairs.
        Makes 2 tuples for "direct" and "reverse" directions and assigns them to the corresponding dictionary.
        """
        base_1, quote_1 = split_hb_trading_pair(self.trading_pair["direct"][0])
        base_2, quote_2 = split_hb_trading_pair(self.trading_pair["direct"][1])
        base_3, quote_3 = split_hb_trading_pair(self.trading_pair["direct"][2])

        order_side_1 = 0 if base_1 == self.holding_asset else 1
        order_side_2 = 0 if base_1 == base_2 else 1
        order_side_3 = 1 if base_3 == self.holding_asset else 0

        self.order_side["direct"] = (order_side_1, order_side_2, order_side_3)
        self.order_side["reverse"] = (1 - order_side_3, 1 - order_side_2, 1 - order_side_1)

    def arbitrage_started(self) -> bool:
        """
        Checks for an unfinished arbitrage round.
        If there is a failure in placing 2nd or 3d order tries to place an order again
        until place_order_trials_limit reached.
        """
        if self.status == "ARBITRAGE_STARTED":
            if self.order_candidate and self.place_order_failure:
                if self.place_order_trials_count <= self.place_order_trials_limit:
                    self.log_with_clock(logging.INFO, f"Failed to place {self.order_candidate.trading_pair} "
                                                      f"{self.order_candidate.order_side} order. Trying again!")
                    self.process_candidate(self.order_candidate, True)
                else:
                    msg = f"Error placing {self.order_candidate.trading_pair} {self.order_candidate.order_side} order"
                    self.notify_hb_app_with_timestamp(msg)
                    self.log_with_clock(logging.WARNING, msg)
                    self.status = "NOT_ACTIVE"
            return True

        return False

    def ready_for_new_orders(self) -> bool:
        """
        Checks if we are ready for new orders:
        - Current status check
        - Holding asset balance check
        Return boolean True if we are ready and False otherwise
        """
        if self.status == "NOT_ACTIVE":
            return False

        if self.connector.get_available_balance(self.holding_asset) < self.order_amount_in_holding_asset:
            self.log_with_clock(logging.INFO,
                                f"{self.connector_name} {self.holding_asset} balance is too low. Cannot place order.")
            return False

        return True

    def calculate_profit(self, trading_pair, order_side):
        """
        Calculates profitability and order amounts for 3 trading pairs based on the orderbook depth.
        """
        exchanged_amount = self.order_amount_in_holding_asset
        order_amount = [0, 0, 0]

        for i in range(3):
            order_amount[i] = self.get_order_amount_from_exchanged_amount(trading_pair[i], order_side[i],
                                                                          exchanged_amount)
            # Update exchanged_amount for the next cycle
            if order_side[i]:
                exchanged_amount = order_amount[i]
            else:
                exchanged_amount = self.connector.get_quote_volume_for_base_amount(trading_pair[i], order_side[i],
                                                                                   order_amount[i]).result_volume
        start_amount = self.order_amount_in_holding_asset
        end_amount = exchanged_amount
        profit = (end_amount / start_amount - 1) * 100

        return profit, order_amount

    def get_order_amount_from_exchanged_amount(self, pair, side, exchanged_amount) -> Decimal:
        """
        Calculates order amount using the amount that we want to exchange.
        - If the side is buy then exchanged asset is a quote asset. Get base amount using the orderbook
        - If the side is sell then exchanged asset is a base asset.
        """
        if side:
            orderbook = self.connector.get_order_book(pair)
            order_amount = self.get_base_amount_for_quote_volume(orderbook.ask_entries(), exchanged_amount)
        else:
            order_amount = exchanged_amount

        return order_amount

    def get_base_amount_for_quote_volume(self, orderbook_entries, quote_volume) -> Decimal:
        """
        Calculates base amount that you get for the quote volume using the orderbook entries
        """
        cumulative_volume = 0.
        cumulative_base_amount = 0.
        quote_volume = float(quote_volume)

        for order_book_row in orderbook_entries:
            row_amount = order_book_row.amount
            row_price = order_book_row.price
            row_volume = row_amount * row_price
            if row_volume + cumulative_volume >= quote_volume:
                row_volume = quote_volume - cumulative_volume
                row_amount = row_volume / row_price
            cumulative_volume += row_volume
            cumulative_base_amount += row_amount
            if cumulative_volume >= quote_volume:
                break

        return Decimal(cumulative_base_amount)

    def start_arbitrage(self, trading_pair, order_side, order_amount):
        """
        Starts arbitrage by creating and processing the first order candidate
        """
        first_candidate = self.create_order_candidate(trading_pair[0], order_side[0], order_amount[0])
        if first_candidate:
            if self.process_candidate(first_candidate, False):
                self.status = "ARBITRAGE_STARTED"

    def create_order_candidate(self, pair, side, amount):
        """
        Creates order candidate. Checks the quantized amount
        """
        side = TradeType.BUY if side else TradeType.SELL
        price = self.connector.get_price_for_volume(pair, side, amount).result_price
        price_quantize = self.connector.quantize_order_price(pair, Decimal(price))
        amount_quantize = self.connector.quantize_order_amount(pair, Decimal(amount))

        if amount_quantize == Decimal("0"):
            self.log_with_clock(logging.INFO, f"Order amount on {pair} is too low to place an order")
            return None

        return OrderCandidate(
            trading_pair=pair,
            is_maker=False,
            order_type=OrderType.MARKET,
            order_side=side,
            amount=amount_quantize,
            price=price_quantize)

    def process_candidate(self, order_candidate, multiple_trials_enabled) -> bool:
        """
        Checks order candidate balance and either places an order or sets a failure for the next trials
        """
        order_candidate_adjusted = self.connector.budget_checker.adjust_candidate(order_candidate, all_or_none=True)
        if math.isclose(order_candidate.amount, Decimal("0"), rel_tol=1E-6):
            self.logger().info(f"Order adjusted amount: {order_candidate.amount} on {order_candidate.trading_pair}, "
                               f"too low to place an order")
            if multiple_trials_enabled:
                self.place_order_trials_count += 1
                self.place_order_failure = True
            return False
        else:
            is_buy = True if order_candidate.order_side == TradeType.BUY else False
            self.place_order(self.connector_name,
                             order_candidate.trading_pair,
                             is_buy,
                             order_candidate_adjusted.amount,
                             order_candidate.order_type,
                             order_candidate_adjusted.price)
            return True

    def place_order(self,
                    connector_name: str,
                    trading_pair: str,
                    is_buy: bool,
                    amount: Decimal,
                    order_type: OrderType,
                    price=Decimal("NaN"),
                    ):
        if is_buy:
            self.buy(connector_name, trading_pair, amount, order_type, price)
        else:
            self.sell(connector_name, trading_pair, amount, order_type, price)

    # Events
    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        self.log_with_clock(logging.INFO, f"Buy order is created on the market {event.trading_pair}")
        if self.order_candidate:
            if self.order_candidate.trading_pair == event.trading_pair:
                self.reset_order_candidate()

    def did_create_sell_order(self, event: SellOrderCreatedEvent):
        self.log_with_clock(logging.INFO, f"Sell order is created on the market {event.trading_pair}")
        if self.order_candidate:
            if self.order_candidate.trading_pair == event.trading_pair:
                self.reset_order_candidate()

    def reset_order_candidate(self):
        """
        Deletes order candidate variable and resets counter
        """
        self.order_candidate = None
        self.place_order_trials_count = 0
        self.place_order_failure = False

    def did_fail_order(self, event: MarketOrderFailureEvent):
        if self.order_candidate:
            self.place_order_failure = True

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        msg = f"Buy {round(event.base_asset_amount, 6)} {event.base_asset} " \
              f"for {round(event.quote_asset_amount, 6)} {event.quote_asset} is completed"
        self.notify_hb_app_with_timestamp(msg)
        self.log_with_clock(logging.INFO, msg)
        self.process_next_pair(event)

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        msg = f"Sell {round(event.base_asset_amount, 6)} {event.base_asset} " \
              f"for {round(event.quote_asset_amount, 6)} {event.quote_asset} is completed"
        self.notify_hb_app_with_timestamp(msg)
        self.log_with_clock(logging.INFO, msg)
        self.process_next_pair(event)

    def process_next_pair(self, order_event):
        """
        Processes 2nd or 3d order and finalizes the arbitrage
        - Gets the completed order index
        - Calculates order amount
        - Creates and processes order candidate
        - Finalizes arbitrage if the 3d order was completed
        """
        event_pair = f"{order_event.base_asset}-{order_event.quote_asset}"
        trading_pair = self.trading_pair[self.profitable_direction]
        order_side = self.order_side[self.profitable_direction]

        event_order_index = trading_pair.index(event_pair)

        if order_side[event_order_index]:
            exchanged_amount = order_event.base_asset_amount
        else:
            exchanged_amount = order_event.quote_asset_amount

        # Save initial amount spent for further profit calculation
        if event_order_index == 0:
            self.initial_spent_amount = order_event.quote_asset_amount if order_side[event_order_index] \
                else order_event.base_asset_amount

        if event_order_index < 2:
            order_amount = self.get_order_amount_from_exchanged_amount(trading_pair[event_order_index + 1],
                                                                       order_side[event_order_index + 1],
                                                                       exchanged_amount)
            self.order_candidate = self.create_order_candidate(trading_pair[event_order_index + 1],
                                                               order_side[event_order_index + 1], order_amount)
            if self.order_candidate:
                self.process_candidate(self.order_candidate, True)
        else:
            self.finalize_arbitrage(exchanged_amount)

    def finalize_arbitrage(self, final_exchanged_amount):
        """
        Finalizes arbitrage
        - Calculates trading round profit
        - Updates total profit
        - Checks the kill switch threshold
        """
        order_profit = round(final_exchanged_amount - self.initial_spent_amount, 6)
        order_profit_pct = round(100 * order_profit / self.initial_spent_amount, 2)
        msg = f"*** Arbitrage completed! Profit: {order_profit} {self.holding_asset} ({order_profit_pct})%"
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

        self.total_profit += order_profit
        self.total_profit_pct = round(100 * self.total_profit / self.order_amount_in_holding_asset, 2)
        self.status = "ACTIVE"
        if self.kill_switch_enabled and self.total_profit_pct < self.kill_switch_rate:
            self.status = "NOT_ACTIVE"
            self.log_with_clock(logging.INFO, "Kill switch threshold reached. Stop trading")
            self.notify_hb_app_with_timestamp("Kill switch threshold reached. Stop trading")

    def format_status(self) -> str:
        """
        Returns status of the current strategy, total profit, current profitability of possible trades and balances.
        This function is called when status command is issued.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        lines.extend(["", "  Strategy status:"] + ["    " + self.status])

        lines.extend(["", "  Total profit:"] + ["    " + f"{self.total_profit} {self.holding_asset}"
                                                         f"({self.total_profit_pct}%)"])

        for direction in self.trading_pair:
            pairs_str = [f"{'buy' if side else 'sell'} {pair}"
                         for side, pair in zip(self.order_side[direction], self.trading_pair[direction])]
            pairs_str = " > ".join(pairs_str)
            profit_str = str(round(self.profit[direction], 2))
            lines.extend(["", f"  {direction.capitalize()}:", f"    {pairs_str}", f"    profitability: {profit_str}%"])

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active orders."])

        if self.connector.get_available_balance(self.holding_asset) < self.order_amount_in_holding_asset:
            warning_lines.extend(
                [f"{self.connector_name} {self.holding_asset} balance is too low. Cannot place order."])

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)
