from collections import defaultdict
from decimal import Decimal
from typing import List

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

CONNECTOR = "dexalot_avalanche_dexalot"
BASE = "AVAX"
QUOTE = "USDC"
TRADING_PAIR = combine_to_hb_trading_pair(base=BASE, quote=QUOTE)
AMOUNT = Decimal("0.5")
ORDERS_INTERVAL = 20
PRICE_OFFSET_RATIO = Decimal("0.1")  # 10%


class BatchOrderUpdate(ScriptStrategyBase):
    markets = {CONNECTOR: {TRADING_PAIR}}
    pingpong = 0

    script_phase = 0

    def on_tick(self):
        if self.script_phase == 0:
            self.place_two_orders_successfully()
        elif self.script_phase == ORDERS_INTERVAL:
            self.cancel_orders()
        elif self.script_phase == ORDERS_INTERVAL * 2:
            self.place_two_orders_with_one_zero_amount_that_will_fail()
        elif self.script_phase == ORDERS_INTERVAL * 3:
            self.cancel_orders()
        self.script_phase += 1

    def place_two_orders_successfully(self):
        price = self.connectors[CONNECTOR].get_price(trading_pair=TRADING_PAIR, is_buy=True)
        orders_to_create = [
            LimitOrder(
                client_order_id="",
                trading_pair=TRADING_PAIR,
                is_buy=True,
                base_currency=BASE,
                quote_currency=QUOTE,
                price=price * (1 - PRICE_OFFSET_RATIO),
                quantity=AMOUNT,
            ),
            LimitOrder(
                client_order_id="",
                trading_pair=TRADING_PAIR,
                is_buy=False,
                base_currency=BASE,
                quote_currency=QUOTE,
                price=price * (1 + PRICE_OFFSET_RATIO),
                quantity=AMOUNT,
            ),
        ]

        market_pair = self._market_trading_pair_tuple(connector_name=CONNECTOR, trading_pair=TRADING_PAIR)
        market = market_pair.market

        submitted_orders: List[LimitOrder] = market.batch_order_create(
            orders_to_create=orders_to_create,
        )

        for order in submitted_orders:
            self.start_tracking_limit_order(
                market_pair=market_pair,
                order_id=order.client_order_id,
                is_buy=order.is_buy,
                price=order.price,
                quantity=order.quantity,
            )

    def cancel_orders(self):
        exchanges_to_orders = defaultdict(lambda: [])
        exchanges_dict = {}

        for exchange, order in self.order_tracker.active_limit_orders:
            exchanges_to_orders[exchange.name].append(order)
            exchanges_dict[exchange.name] = exchange

        for exchange_name, orders_to_cancel in exchanges_to_orders.items():
            exchanges_dict[exchange_name].batch_order_cancel(orders_to_cancel=orders_to_cancel)

    def place_two_orders_with_one_zero_amount_that_will_fail(self):
        price = self.connectors[CONNECTOR].get_price(trading_pair=TRADING_PAIR, is_buy=True)
        orders_to_create = [
            LimitOrder(
                client_order_id="",
                trading_pair=TRADING_PAIR,
                is_buy=True,
                base_currency=BASE,
                quote_currency=QUOTE,
                price=price * (1 - PRICE_OFFSET_RATIO),
                quantity=AMOUNT,
            ),
            LimitOrder(
                client_order_id="",
                trading_pair=TRADING_PAIR,
                is_buy=False,
                base_currency=BASE,
                quote_currency=QUOTE,
                price=price * (1 + PRICE_OFFSET_RATIO),
                quantity=Decimal("0"),
            ),
        ]

        market_pair = self._market_trading_pair_tuple(connector_name=CONNECTOR, trading_pair=TRADING_PAIR)
        market = market_pair.market

        submitted_orders: List[LimitOrder] = market.batch_order_create(
            orders_to_create=orders_to_create,
        )

        for order in submitted_orders:
            self.start_tracking_limit_order(
                market_pair=market_pair,
                order_id=order.client_order_id,
                is_buy=order.is_buy,
                price=order.price,
                quantity=order.quantity,
            )
