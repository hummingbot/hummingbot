from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.lighter import lighter_api_utils as utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import OrderState


class LighterApiUtilsTests(TestCase):
    def test_spot_markets_from_exchange_info(self):
        exchange_info = {
            "spot_order_book_details": [
                {
                    "symbol": "ETH/USDC",
                    "market_id": 2048,
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

        markets = utils.spot_markets_from_exchange_info(exchange_info)

        self.assertEqual(1, len(markets))
        self.assertEqual("ETH/USDC", markets[0].exchange_symbol)
        self.assertEqual("ETH-USDC", markets[0].trading_pair)
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

    def test_extract_account_snapshot_by_l1_address(self):
        response = {
            "accounts": [
                {"index": 10, "l1_address": "0xabc", "assets": []},
            ]
        }

        account = utils.extract_account_snapshot(response, l1_address="0xAbC")

        self.assertEqual(10, utils.account_index_from_account(account))

    def test_extract_account_snapshot_by_l1_address_from_sub_accounts_response(self):
        response = {
            "code": 200,
            "l1_address": "0xe34167D92340c95A7775495d78bcc3Dc21cf11c0",
            "sub_accounts": [
                {
                    "code": 0,
                    "account_type": 0,
                    "index": 724450,
                    "l1_address": "0xe34167D92340c95A7775495d78bcc3Dc21cf11c0",
                    "available_balance": "",
                    "collateral": "50.000000",
                }
            ],
        }

        account = utils.extract_account_snapshot(
            response, l1_address="0xe34167D92340c95A7775495d78bcc3Dc21cf11c0"
        )

        self.assertEqual(724450, utils.account_index_from_account(account))

    def test_normalize_timestamp_to_seconds_infers_unit_from_magnitude(self):
        # Lighter mixes units: wall-clock fields are ms, transaction_time is us (live-API verified).
        self.assertAlmostEqual(1781056278.158, utils.normalize_timestamp_to_seconds("1781056278158"))       # ms
        self.assertAlmostEqual(1781056278.158263, utils.normalize_timestamp_to_seconds("1781056278158263"))  # us
        self.assertAlmostEqual(1781056278.0, utils.normalize_timestamp_to_seconds(1781056278))               # s
        self.assertAlmostEqual(1781056278.158263, utils.normalize_timestamp_to_seconds(1781056278158263158), places=4)  # ns
        self.assertEqual(0.0, utils.normalize_timestamp_to_seconds(None))
        self.assertEqual(0.0, utils.normalize_timestamp_to_seconds(0))

    def test_normalize_timestamp_milliseconds_not_parsed_as_1970(self):
        # Regression: an order's millisecond updated_at must not be read as microseconds (~1970).
        self.assertGreater(utils.normalize_timestamp_to_seconds("1640780000000"), 1_600_000_000)
