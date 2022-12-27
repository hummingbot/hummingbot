from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from decimal import Decimal


class Steamroller(ScriptStrategyBase):
    """
    This is a simple script that places bids or asks depending on
    the difference on exchanges based on liquidity.
    """
    liquid_exchange = "kucoin_paper_trade"
    less_liquid_exchange = "gate_io_paper_trade"
    reference_exchange = "binance_us_paper_trade"
    security = "BTC-USDT"
    max_order_age = 10
    order_amount_usd = Decimal("100")
    spread_threshold_percent = Decimal("0.5")
    markets = {
        liquid_exchange: {security},
        less_liquid_exchange: {security},
        reference_exchange: {security}
        }

    sell_order_placed = False
    buy_order_placed = False
    long_position = False
    short_position = False

    def on_tick(self):
        best_bid_liquid = self.connectors[self.liquid_exchange].get_price(self.security, False)
        best_bid_less_liquid = self.connectors[self.less_liquid_exchange].get_price(self.security, False)
        best_ask_liquid = self.connectors[self.liquid_exchange].get_price(self.security, True)
        best_ask_less_liquid = self.connectors[self.less_liquid_exchange].get_price(self.security, True)
        increment = self.connectors[self.less_liquid_exchange].get_order_price_quantum(self.security, Decimal("1"))
        conversion_rate = self.connectors[self.reference_exchange].get_price(self.security, False)
        maker_buy_price = best_bid_less_liquid + increment    # Place a buy one increment above the best bid
        maker_sell_price = best_ask_less_liquid - increment   # Place a sell one increment below the best ask
        sell_order_amount = self.order_amount_usd / conversion_rate
        buy_order_amount = self.order_amount_usd / conversion_rate

        if not self.buy_order_placed and (((best_bid_liquid - best_bid_less_liquid) / best_bid_less_liquid) * 100) >= self.spread_threshold_percent:
            self.logger().info(f"{buy_order_amount}")
            self.logger().info(f"{maker_buy_price}")
            buy_order = OrderCandidate(trading_pair=self.security, is_maker=True, order_type=OrderType.LIMIT, order_side=TradeType.BUY, amount=buy_order_amount, price=maker_buy_price)
            buy_order_adjusted = self.connectors[self.less_liquid_exchange].budget_checker.adjust_candidate(buy_order, all_or_none=True)
            self.buy(self.less_liquid_exchange, self.security, buy_order_adjusted.amount, buy_order_adjusted.order_type, buy_order_adjusted.price)
            self.buy_order_placed = True
            self.logger().info("Placed a buy")

        if not self.sell_order_placed and (((best_ask_less_liquid - best_ask_liquid) / best_ask_liquid) * 100) >= self.spread_threshold_percent:
            sell_order = OrderCandidate(trading_pair=self.security, is_maker=True, order_type=OrderType.LIMIT, order_side=TradeType.SELL, amount=sell_order_amount, price=maker_sell_price)
            sell_order_adjusted = self.connectors[self.less_liquid_exchange].budget_checker.adjust_candidate(sell_order, all_or_none=True)
            self.sell(self.less_liquid_exchange, self.security, sell_order_adjusted.amount, sell_order_adjusted.order_type, sell_order_adjusted.price)
            self.sell_order_placed = True
            self.logger().info("Placed a sell")

        # Canceling unfilled orders
        for order in self.get_active_orders(connector_name=self.less_liquid_exchange):
            cancel_timestamp = order.creation_timestamp / 1000000 + self.max_order_age
            self.logger().info(f"{cancel_timestamp}")
            self.logger().info(f"{order.creation_timestamp / 1000000 + self.max_order_age}")

            if order.is_buy:
                if cancel_timestamp < self.current_timestamp or (((best_bid_liquid - best_bid_less_liquid) / best_bid_less_liquid) * 100) < self.spread_threshold_percent:
                    self.cancel(self.less_liquid_exchange, order.trading_pair, order.client_order_id)
                    self.buy_order_placed = False
                    self.logger().info("Canceled a buy")

            else:
                if cancel_timestamp < self.current_timestamp or (((best_ask_less_liquid - best_ask_liquid) / best_ask_liquid) * 100) < self.spread_threshold_percent:
                    self.cancel(self.less_liquid_exchange, order.trading_pair, order.client_order_id)
                    self.sell_order_placed = False
                    self.logger().info("Canceled a sell")

        #
        if self.long_position and (((best_bid_liquid - best_bid_less_liquid) / best_bid_less_liquid) * 100) < self.spread_threshold_percent:
            sell_order = OrderCandidate(trading_pair=self.security, is_maker=True, order_type=OrderType.LIMIT, order_side=TradeType.SELL, amount=sell_order_amount, price=maker_sell_price)
            sell_order_adjusted = self.connectors[self.less_liquid_exchange].budget_checker.adjust_candidate(sell_order, all_or_none=True)
            self.sell(self.less_liquid_exchange, self.security, sell_order_adjusted.amount, sell_order_adjusted.order_type, sell_order_adjusted.price)
            self.logger().info("Closed the long position")
            self.long_position = False

        if self.short_position and (((best_ask_less_liquid - best_ask_liquid) / best_ask_liquid) * 100) < self.spread_threshold_percent:

            buy_order = OrderCandidate(trading_pair=self.security, is_maker=True, order_type=OrderType.LIMIT, order_side=TradeType.BUY, amount=buy_order_amount, price=maker_buy_price)
            buy_order_adjusted = self.connectors[self.less_liquid_exchange].budget_checker.adjust_candidate(buy_order, all_or_none=True)
            self.buy(self.less_liquid_exchange, self.security, buy_order_adjusted.amount, buy_order_adjusted.order_type, buy_order_adjusted.price)
            self.logger().info("Closed the short position")
            self.short_position = False

        return

    def is_active_maker_order(self, event: OrderFilledEvent):
        """
        Helper function that checks if order is an active order on the maker exchange
        """
        for order in self.get_active_orders(connector_name=self.less_liquid_exchange):
            if order.client_order_id == event.order_id:
                return True
        return False

    def did_fill_order(self, event: OrderFilledEvent):

        if event.trade_type == TradeType.BUY and self.is_active_maker_order(event):
            self.logger().info("Buy is filled")
            self.long_position = True
        else:
            if event.trade_type == TradeType.SELL and self.is_active_maker_order(event):
                self.logger().info("Sell is filled")
                self.short_position = True

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

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])
        market_status_df = self.get_market_status_df_with_depth()
        lines.extend(["", "  Market Status Data Frame:"] + ["    " + line for line in market_status_df.to_string(index=False).split("\n")])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)

    def get_market_status_df_with_depth(self):
        market_status_df = self.market_status_data_frame(self.get_market_trading_pair_tuples())
        market_status_df["Exchange"] = market_status_df.apply(lambda x: x["Exchange"].strip("PaperTrade") + "paper_trade", axis=1)
        market_status_df["Volume (+1%)"] = market_status_df.apply(lambda x: self.get_volume_for_percentage_from_mid_price(x, 0.01), axis=1)
        market_status_df["Volume (-1%)"] = market_status_df.apply(lambda x: self.get_volume_for_percentage_from_mid_price(x, -0.01), axis=1)
        return market_status_df

    def get_volume_for_percentage_from_mid_price(self, row, percentage):
        price = row["Mid Price"] * (1 + percentage)
        is_buy = percentage > 0
        result = self.connectors[row["Exchange"]].get_volume_for_price(row["Market"], is_buy, price)
        return result.result_volume
