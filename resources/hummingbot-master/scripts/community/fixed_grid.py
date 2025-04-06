import logging
from decimal import Decimal
from typing import Dict, List

import numpy as np
import pandas as pd

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import BuyOrderCompletedEvent, OrderFilledEvent, SellOrderCompletedEvent
from hummingbot.core.utils import map_df_to_str
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class FixedGrid(ScriptStrategyBase):
    # Parameters to modify -----------------------------------------
    trading_pair = "ENJ-USDT"
    exchange = "ascend_ex"
    n_levels = 8
    grid_price_ceiling = Decimal(0.33)
    grid_price_floor = Decimal(0.3)
    order_amount = Decimal(18.0)
    # Optional ----------------------
    spread_scale_factor = Decimal(1.0)
    amount_scale_factor = Decimal(1.0)
    rebalance_order_type = "limit"
    rebalance_order_spread = Decimal(0.02)
    rebalance_order_refresh_time = 60.0
    grid_orders_refresh_time = 3600000.0
    price_source = PriceType.MidPrice
    # ----------------------------------------------------------------

    markets = {exchange: {trading_pair}}
    create_timestamp = 0
    price_levels = []
    base_inv_levels = []
    quote_inv_levels = []
    order_amount_levels = []
    quote_inv_levels_current_price = []
    current_level = -100
    grid_spread = (grid_price_ceiling - grid_price_floor) / (n_levels - 1)
    inv_correct = True
    rebalance_order_amount = Decimal(0.0)
    rebalance_order_buy = True

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)

        self.minimum_spread = (self.grid_price_ceiling - self.grid_price_floor) / (1 + 2 * sum([pow(self.spread_scale_factor, n) for n in range(1, int(self.n_levels / 2))]))
        self.price_levels.append(self.grid_price_floor)
        for i in range(2, int(self.n_levels / 2) + 1):
            price = self.grid_price_floor + self.minimum_spread * sum([pow(self.spread_scale_factor, int(self.n_levels / 2) - n) for n in range(1, i)])
            self.price_levels.append(price)
        for i in range(1, int(self.n_levels / 2) + 1):
            self.order_amount_levels.append(self.order_amount * pow(self.amount_scale_factor, int(self.n_levels / 2) - i))

        for i in range(int(self.n_levels / 2) + 1, self.n_levels + 1):
            price = self.price_levels[int(self.n_levels / 2) - 1] + self.minimum_spread * sum([pow(self.spread_scale_factor, n) for n in range(0, i - int(self.n_levels / 2))])
            self.price_levels.append(price)
            self.order_amount_levels.append(self.order_amount * pow(self.amount_scale_factor, i - int(self.n_levels / 2) - 1))

        for i in range(1, self.n_levels + 1):
            self.base_inv_levels.append(sum(self.order_amount_levels[i:self.n_levels]))
            self.quote_inv_levels.append(sum([self.price_levels[n] * self.order_amount_levels[n] for n in range(0, i - 1)]))
        for i in range(self.n_levels):
            self.quote_inv_levels_current_price.append(self.quote_inv_levels[i] / self.price_levels[i])

    def on_tick(self):
        proposal = None
        if self.create_timestamp <= self.current_timestamp:
            # If grid level not yet set, find it.
            if self.current_level == -100:
                price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
                # Find level closest to market
                min_diff = 1e8
                for i in range(self.n_levels):
                    if min(min_diff, abs(self.price_levels[i] - price)) < min_diff:
                        min_diff = abs(self.price_levels[i] - price)
                        self.current_level = i

                msg = (f"Current price {price}, Initial level {self.current_level+1}")
                self.log_with_clock(logging.INFO, msg)
                self.notify_hb_app_with_timestamp(msg)

                if price > self.grid_price_ceiling:
                    msg = ("WARNING: Current price is above grid ceiling")
                    self.log_with_clock(logging.WARNING, msg)
                    self.notify_hb_app_with_timestamp(msg)
                elif price < self.grid_price_floor:
                    msg = ("WARNING: Current price is below grid floor")
                    self.log_with_clock(logging.WARNING, msg)
                    self.notify_hb_app_with_timestamp(msg)

            market, trading_pair, base_asset, quote_asset = self.get_market_trading_pair_tuples()[0]
            base_balance = float(market.get_balance(base_asset))
            quote_balance = float(market.get_balance(quote_asset) / self.price_levels[self.current_level])

            if base_balance < self.base_inv_levels[self.current_level]:
                self.inv_correct = False
                msg = (f"WARNING: Insuffient {base_asset} balance for grid bot. Will attempt to rebalance")
                self.log_with_clock(logging.WARNING, msg)
                self.notify_hb_app_with_timestamp(msg)
                if base_balance + quote_balance < self.base_inv_levels[self.current_level] + self.quote_inv_levels_current_price[self.current_level]:
                    msg = (f"WARNING: Insuffient {base_asset} and {quote_asset} balance for grid bot. Unable to rebalance."
                           f"Please add funds or change grid parameters")
                    self.log_with_clock(logging.WARNING, msg)
                    self.notify_hb_app_with_timestamp(msg)
                    return
                else:
                    # Calculate additional base required with 5% tolerance
                    base_required = (Decimal(self.base_inv_levels[self.current_level]) - Decimal(base_balance)) * Decimal(1.05)
                    self.rebalance_order_buy = True
                    self.rebalance_order_amount = Decimal(base_required)
            elif quote_balance < self.quote_inv_levels_current_price[self.current_level]:
                self.inv_correct = False
                msg = (f"WARNING: Insuffient {quote_asset} balance for grid bot. Will attempt to rebalance")
                self.log_with_clock(logging.WARNING, msg)
                self.notify_hb_app_with_timestamp(msg)
                if base_balance + quote_balance < self.base_inv_levels[self.current_level] + self.quote_inv_levels_current_price[self.current_level]:
                    msg = (f"WARNING: Insuffient {base_asset} and {quote_asset} balance for grid bot. Unable to rebalance."
                           f"Please add funds or change grid parameters")
                    self.log_with_clock(logging.WARNING, msg)
                    self.notify_hb_app_with_timestamp(msg)
                    return
                else:
                    # Calculate additional quote required with 5% tolerance
                    quote_required = (Decimal(self.quote_inv_levels_current_price[self.current_level]) - Decimal(quote_balance)) * Decimal(1.05)
                    self.rebalance_order_buy = False
                    self.rebalance_order_amount = Decimal(quote_required)
            else:
                self.inv_correct = True

            if self.inv_correct is True:
                # Create proposals for Grid
                proposal = self.create_grid_proposal()
            else:
                # Create rebalance proposal
                proposal = self.create_rebalance_proposal()

            self.cancel_active_orders()
            if proposal is not None:
                self.execute_orders_proposal(proposal)

    def create_grid_proposal(self) -> List[OrderCandidate]:
        buys = []
        sells = []

        # Proposal will be created according to grid price levels
        for i in range(self.current_level):
            price = self.price_levels[i]
            size = self.order_amount_levels[i]
            if size > 0:
                buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                           order_side=TradeType.BUY, amount=size, price=price)
                buys.append(buy_order)

        for i in range(self.current_level + 1, self.n_levels):
            price = self.price_levels[i]
            size = self.order_amount_levels[i]
            if size > 0:
                sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                            order_side=TradeType.SELL, amount=size, price=price)
                sells.append(sell_order)

        return buys + sells

    def create_rebalance_proposal(self):
        buys = []
        sells = []

        # Proposal will be created according to start order spread.
        if self.rebalance_order_buy is True:
            ref_price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
            price = ref_price * (Decimal("100") - self.rebalance_order_spread) / Decimal("100")
            size = self.rebalance_order_amount

            msg = (f"Placing buy order to rebalance; amount: {size}, price: {price}")
            self.log_with_clock(logging.INFO, msg)
            self.notify_hb_app_with_timestamp(msg)
            if size > 0:
                if self.rebalance_order_type == "limit":
                    buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                               order_side=TradeType.BUY, amount=size, price=price)
                elif self.rebalance_order_type == "market":
                    buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.MARKET,
                                               order_side=TradeType.BUY, amount=size, price=price)
                buys.append(buy_order)

        if self.rebalance_order_buy is False:
            ref_price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
            price = ref_price * (Decimal("100") + self.rebalance_order_spread) / Decimal("100")
            size = self.rebalance_order_amount
            msg = (f"Placing sell order to rebalance; amount: {size}, price: {price}")
            self.log_with_clock(logging.INFO, msg)
            self.notify_hb_app_with_timestamp(msg)
            if size > 0:
                if self.rebalance_order_type == "limit":
                    sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                                order_side=TradeType.SELL, amount=size, price=price)
                elif self.rebalance_order_type == "market":
                    sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.MARKET,
                                                order_side=TradeType.SELL, amount=size, price=price)
                sells.append(sell_order)

        return buys + sells

    def did_fill_order(self, event: OrderFilledEvent):
        msg = (f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} {self.exchange} at {round(event.price, 2)}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        if self.inv_correct is False:
            self.create_timestamp = self.current_timestamp + float(1.0)

        if self.inv_correct is True:
            # Set the new level
            self.current_level -= 1
            # Add sell order above current level
            price = self.price_levels[self.current_level + 1]
            size = self.order_amount_levels[self.current_level + 1]
            proposal = [OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                       order_side=TradeType.SELL, amount=size, price=price)]
            self.execute_orders_proposal(proposal)

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        if self.inv_correct is False:
            self.create_timestamp = self.current_timestamp + float(1.0)

        if self.inv_correct is True:
            # Set the new level
            self.current_level += 1
            # Add buy order above current level
            price = self.price_levels[self.current_level - 1]
            size = self.order_amount_levels[self.current_level - 1]
            proposal = [OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                       order_side=TradeType.BUY, amount=size, price=price)]
            self.execute_orders_proposal(proposal)

    def execute_orders_proposal(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            self.place_order(connector_name=self.exchange, order=order)
        if self.inv_correct is False:
            next_cycle = self.current_timestamp + self.rebalance_order_refresh_time
            if self.create_timestamp <= self.current_timestamp:
                self.create_timestamp = next_cycle
        else:
            next_cycle = self.current_timestamp + self.grid_orders_refresh_time
            if self.create_timestamp <= self.current_timestamp:
                self.create_timestamp = next_cycle

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        elif order.order_side == TradeType.BUY:
            self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)

    def grid_assets_df(self) -> pd.DataFrame:
        market, trading_pair, base_asset, quote_asset = self.get_market_trading_pair_tuples()[0]
        price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
        base_balance = float(market.get_balance(base_asset))
        quote_balance = float(market.get_balance(quote_asset))
        available_base_balance = float(market.get_available_balance(base_asset))
        available_quote_balance = float(market.get_available_balance(quote_asset))
        base_value = base_balance * float(price)
        total_in_quote = base_value + quote_balance
        base_ratio = base_value / total_in_quote if total_in_quote > 0 else 0
        quote_ratio = quote_balance / total_in_quote if total_in_quote > 0 else 0
        data = [
            ["", base_asset, quote_asset],
            ["Total Balance", round(base_balance, 4), round(quote_balance, 4)],
            ["Available Balance", round(available_base_balance, 4), round(available_quote_balance, 4)],
            [f"Current Value ({quote_asset})", round(base_value, 4), round(quote_balance, 4)]
        ]
        data.append(["Current %", f"{base_ratio:.1%}", f"{quote_ratio:.1%}"])
        df = pd.DataFrame(data=data)
        return df

    def grid_status_data_frame(self) -> pd.DataFrame:
        grid_data = []
        grid_columns = ["Parameter", "Value"]

        market, trading_pair, base_asset, quote_asset = self.get_market_trading_pair_tuples()[0]
        base_balance = float(market.get_balance(base_asset))
        quote_balance = float(market.get_balance(quote_asset) / self.price_levels[self.current_level])

        grid_data.append(["Grid spread", round(self.grid_spread, 4)])
        grid_data.append(["Current grid level", self.current_level + 1])
        grid_data.append([f"{base_asset} required", round(self.base_inv_levels[self.current_level], 4)])
        grid_data.append([f"{quote_asset} required in {base_asset}", round(self.quote_inv_levels_current_price[self.current_level], 4)])
        grid_data.append([f"{base_asset} balance", round(base_balance, 4)])
        grid_data.append([f"{quote_asset} balance in {base_asset}", round(quote_balance, 4)])
        grid_data.append(["Correct inventory balance", self.inv_correct])

        return pd.DataFrame(data=grid_data, columns=grid_columns).replace(np.nan, '', regex=True)

    def format_status(self) -> str:
        """
         Displays the status of the fixed grid strategy
         Returns status of the current strategy on user balances and current active orders.
         """
        if not self.ready_to_trade:
            return "Market connectors are not ready."

        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        grid_df = map_df_to_str(self.grid_status_data_frame())
        lines.extend(["", "  Grid:"] + ["    " + line for line in grid_df.to_string(index=False).split("\n")])

        assets_df = map_df_to_str(self.grid_assets_df())

        first_col_length = max(*assets_df[0].apply(len))
        df_lines = assets_df.to_string(index=False, header=False,
                                       formatters={0: ("{:<" + str(first_col_length) + "}").format}).split("\n")
        lines.extend(["", "  Assets:"] + ["    " + line for line in df_lines])

        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)

    def cancel_active_orders(self):
        """
        Cancels active orders
        """
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)
