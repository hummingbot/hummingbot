import time
from decimal import Decimal
from typing import List

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

CONNECTOR = "bybit"
BASE = "ETH"
QUOTE = "BTC"
TRADING_PAIR = combine_to_hb_trading_pair(base=BASE, quote=QUOTE)
AMOUNT = Decimal("0.003")
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
            self.place_two_orders_with_one_zero_amount_that_will_fail()
        self.script_phase += 1

    def place_two_orders_successfully(self):
        orders_to_create = [
            MarketOrder(
                order_id="",
                trading_pair=TRADING_PAIR,
                is_buy=True,
                base_asset=BASE,
                quote_asset=QUOTE,
                amount=AMOUNT,
                timestamp=time.time(),
            ),
            MarketOrder(
                order_id="",
                trading_pair=TRADING_PAIR,
                is_buy=False,
                base_asset=BASE,
                quote_asset=QUOTE,
                amount=AMOUNT,
                timestamp=time.time(),
            ),
        ]

        market_pair = self._market_trading_pair_tuple(connector_name=CONNECTOR, trading_pair=TRADING_PAIR)
        market = market_pair.market

        submitted_orders: List[LimitOrder, MarketOrder] = market.batch_order_create(
            orders_to_create=orders_to_create,
        )

        for order in submitted_orders:
            self.start_tracking_market_order(
                market_pair=market_pair,
                order_id=order.order_id,
                is_buy=order.is_buy,
                quantity=order.amount,
            )

    def place_two_orders_with_one_zero_amount_that_will_fail(self):
        orders_to_create = [
            MarketOrder(
                order_id="",
                trading_pair=TRADING_PAIR,
                is_buy=True,
                base_asset=BASE,
                quote_asset=QUOTE,
                amount=AMOUNT,
                timestamp=time.time(),
            ),
            MarketOrder(
                order_id="",
                trading_pair=TRADING_PAIR,
                is_buy=True,
                base_asset=BASE,
                quote_asset=QUOTE,
                amount=Decimal("0"),
                timestamp=time.time(),
            ),
        ]

        market_pair = self._market_trading_pair_tuple(connector_name=CONNECTOR, trading_pair=TRADING_PAIR)
        market = market_pair.market

        submitted_orders: List[LimitOrder, MarketOrder] = market.batch_order_create(
            orders_to_create=orders_to_create,
        )

        for order in submitted_orders:
            self.start_tracking_market_order(
                market_pair=market_pair,
                order_id=order.order_id,
                is_buy=order.is_buy,
                quantity=order.amount,
            )
