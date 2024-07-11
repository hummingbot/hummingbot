from decimal import Decimal
from typing import List

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AdjustedMidPrice(ScriptStrategyBase):
    """
    BotCamp Cohort: Sept 2022
    Design Template: https://hummingbot-foundation.notion.site/PMM-with-Adjusted-Midpoint-4259e7aef7bf403dbed35d1ed90f36fe
    Video: -
    Description:
    This is an example of a pure market making strategy with an adjusted mid price.  The mid price is adjusted to
    the midpoint of a hypothetical buy and sell of a user defined {test_volume}.
    Example:
    let test_volume = 10 and the pair = BTC-USDT, then the new mid price will be the mid price of the following two points:
    1) the average fill price of a hypothetical market buy of 10 BTC
    2) the average fill price of a hypothetical market sell of 10 BTC
    """

    # The following strategy dictionary are parameters that the script operator can adjustS
    strategy = {
        "test_volume": 50,  # the amount in base currancy to make the hypothetical market buy and market sell.
        "bid_spread": .1,   # how far away from the mid price do you want to place the first bid order (1 indicated 1%)
        "ask_spread": .1,   # how far away from the mid price do you want to place the first bid order (1 indicated 1%)
        "amount": .1,       # the amount in base currancy you want to buy or sell
        "order_refresh_time": 60,
        "market": "binance_paper_trade",
        "pair": "BTC-USDT"
    }

    markets = {strategy["market"]: {strategy["pair"]}}

    @property
    def connector(self) -> ExchangeBase:
        return self.connectors[self.strategy["market"]]

    def on_tick(self):
        """
        Runs every tick_size seconds, this is the main operation of the strategy.
        This method does two things:
        - Refreshes the current bid and ask if they are set to None
        - Cancels the current bid or current ask if they are past their order_refresh_time
          The canceled orders will be refreshed next tic
        """
        ##
        # refresh order logic
        ##
        active_orders = self.get_active_orders(self.strategy["market"])
        # determine if we have an active bid and ask. We will only ever have 1 bid and 1 ask, so this logic would not work in the case of hanging orders
        active_bid = None
        active_ask = None
        for order in active_orders:
            if order.is_buy:
                active_bid = order
            else:
                active_ask = order
        proposal: List(OrderCandidate) = []
        if active_bid is None:
            proposal.append(self.create_order(True))
        if active_ask is None:
            proposal.append(self.create_order(False))
        if (len(proposal) > 0):
            # we have proposed orders to place
            # the next line will set the amount to 0 if we do not have the budget for the order and will quantize the amount if we have the budget
            adjusted_proposal: List(OrderCandidate) = self.connector.budget_checker.adjust_candidates(proposal, all_or_none=True)
            # we will set insufficient funds to true if any of the orders were set to zero
            insufficient_funds = False
            for order in adjusted_proposal:
                if (order.amount == 0):
                    insufficient_funds = True
            # do not place any orders if we have any insufficient funds and notify user
            if (insufficient_funds):
                self.logger().info("Insufficient funds. No more orders will be placed")
            else:
                # place orders
                for order in adjusted_proposal:
                    if order.order_side == TradeType.BUY:
                        self.buy(self.strategy["market"], order.trading_pair, Decimal(self.strategy['amount']), order.order_type, Decimal(order.price))
                    elif order.order_side == TradeType.SELL:
                        self.sell(self.strategy["market"], order.trading_pair, Decimal(self.strategy['amount']), order.order_type, Decimal(order.price))
        ##
        # cancel order logic
        # (canceled orders will be refreshed next tick)
        ##
        for order in active_orders:
            if (order.age() > self.strategy["order_refresh_time"]):
                self.cancel(self.strategy["market"], self.strategy["pair"], order.client_order_id)

    def create_order(self, is_bid: bool) -> OrderCandidate:
        """
         Create a propsal for the current bid or ask using the adjusted mid price.
         """
        mid_price = Decimal(self.adjusted_mid_price())
        bid_spread = Decimal(self.strategy["bid_spread"])
        ask_spread = Decimal(self.strategy["ask_spread"])
        bid_price = mid_price - mid_price * bid_spread * Decimal(.01)
        ask_price = mid_price + mid_price * ask_spread * Decimal(.01)
        price = bid_price if is_bid else ask_price
        price = self.connector.quantize_order_price(self.strategy["pair"], Decimal(price))
        order = OrderCandidate(
            trading_pair=self.strategy["pair"],
            is_maker=False,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY if is_bid else TradeType.SELL,
            amount=Decimal(self.strategy["amount"]),
            price=price)
        return order

    def adjusted_mid_price(self):
        """
        Returns the  price of a hypothetical buy and sell or the base asset where the amount is {strategy.test_volume}
        """
        ask_result = self.connector.get_quote_volume_for_base_amount(self.strategy["pair"], True, self.strategy["test_volume"])
        bid_result = self.connector.get_quote_volume_for_base_amount(self.strategy["pair"], False, self.strategy["test_volume"])
        average_ask = ask_result.result_volume / ask_result.query_volume
        average_bid = bid_result.result_volume / bid_result.query_volume
        return average_bid + ((average_ask - average_bid) / 2)

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))
        actual_mid_price = self.connector.get_mid_price(self.strategy["pair"])
        adjusted_mid_price = self.adjusted_mid_price()
        lines.extend(["", "  Adjusted mid price: " + str(adjusted_mid_price)] + ["  Actual mid price: " + str(actual_mid_price)])
        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])
        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
