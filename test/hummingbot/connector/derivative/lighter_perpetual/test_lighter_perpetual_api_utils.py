from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_api_utils as utils,
    lighter_perpetual_constants as CONSTANTS,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import OrderState


class LighterPerpetualApiUtilsTests(TestCase):
    def test_perpetual_markets_from_exchange_info(self):
        exchange_info = {
            "order_book_details": [
                {
                    "symbol": "ETH",
                    "market_id": 5,
                    "status": "active",
                    "market_config": {"hidden": False},
                    "min_base_amount": "0.01",
                    "min_quote_amount": "10",
                    "supported_size_decimals": 3,
                    "supported_price_decimals": 2,
                    "maker_fee": "0.0001",
                    "taker_fee": "0.0004",
                }
            ]
        }

        markets = utils.perpetual_markets_from_exchange_info(exchange_info)

        self.assertEqual(1, len(markets))
        self.assertEqual("ETH", markets[0].exchange_symbol)
        self.assertEqual(f"ETH-{CONSTANTS.PERPETUAL_QUOTE_TOKEN}", markets[0].trading_pair)
        self.assertEqual(Decimal("0.0001"), markets[0].maker_fee)

    def test_order_state_from_order_data_partial_fill(self):
        order_data = {
            "status": "open",
            "filled_base_amount": "0.5",
        }

        order_state = utils.order_state_from_order_data(order_data)

        self.assertEqual(OrderState.PARTIALLY_FILLED, order_state)

    def test_own_trade_details_for_ask_and_bid(self):
        trade = {
            "ask_account_id": 10,
            "bid_account_id": 11,
            "ask_client_id_str": "a1",
            "ask_id_str": "o1",
            "bid_client_id_str": "b1",
            "bid_id_str": "o2",
            "is_maker_ask": True,
        }

        ask_details = utils.own_trade_details(trade=trade, account_index=10)
        bid_details = utils.own_trade_details(trade=trade, account_index=11)
        none_details = utils.own_trade_details(trade=trade, account_index=12)

        self.assertEqual((TradeType.SELL, "a1", "o1", True), ask_details)
        self.assertEqual((TradeType.BUY, "b1", "o2", False), bid_details)
        self.assertIsNone(none_details)
