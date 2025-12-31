import unittest
from decimal import Decimal

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.connector.exchange.backpack import backpack_utils as utils


class TestBackpackUtils(unittest.TestCase):
    def test_trading_pair_conversions(self):
        self.assertEqual("BTC_USDC", utils.convert_to_exchange_trading_pair("BTC-USDC"))
        self.assertEqual("BTC-USDC", utils.convert_from_exchange_trading_pair("BTC_USDC"))

    def test_get_base_quote_from_trading_pair(self):
        self.assertEqual(("BTC", "USDC"), utils.get_base_quote_from_trading_pair("BTC-USDC"))
        self.assertEqual(("ETH", "USDC"), utils.get_base_quote_from_trading_pair("ETH_USDC"))
        with self.assertRaises(ValueError):
            utils.get_base_quote_from_trading_pair("INVALID")

    def test_symbol_type_checks(self):
        self.assertTrue(utils.is_spot_symbol("BTC_USDC"))
        self.assertFalse(utils.is_spot_symbol("BTC_USDC_PERP"))
        self.assertTrue(utils.is_perpetual_symbol("BTC_USDC_PERP"))
        self.assertFalse(utils.is_perpetual_symbol("BTC_USDC"))

    def test_order_side_and_type_conversions(self):
        self.assertEqual("BUY", utils.parse_order_side(CONSTANTS.ORDER_SIDE_BID))
        self.assertEqual("SELL", utils.parse_order_side(CONSTANTS.ORDER_SIDE_ASK))
        self.assertEqual(CONSTANTS.ORDER_SIDE_BID, utils.to_exchange_order_side(True))
        self.assertEqual(CONSTANTS.ORDER_SIDE_ASK, utils.to_exchange_order_side(False))
        self.assertEqual("LIMIT", utils.parse_order_type("Limit"))
        self.assertEqual("MARKET", utils.parse_order_type("Market"))
        self.assertEqual("Limit", utils.to_exchange_order_type("LIMIT"))

    def test_decimal_to_str(self):
        self.assertEqual("1.23", utils.decimal_to_str(Decimal("1.2300"), precision=4))
        self.assertEqual("0", utils.decimal_to_str(None))

    def test_parse_balance_response(self):
        balance_data = {
            "USDC": {"available": "10", "locked": "2"},
            "BTC": {"available": "1.5", "locked": "0.5"},
        }
        balances = utils.parse_balance_response(balance_data)
        self.assertEqual((Decimal("10"), Decimal("12")), balances["USDC"])
        self.assertEqual((Decimal("1.5"), Decimal("2.0")), balances["BTC"])

    def test_parse_trading_rule(self):
        market_data = {
            "symbol": "SOL_USDC",
            "minOrderSize": "0.01",
            "tickSize": "0.1",
            "stepSize": "0.001",
            "minNotional": "5",
        }
        rule = utils.parse_trading_rule(market_data)
        self.assertEqual("SOL_USDC", rule["symbol"])
        self.assertEqual("SOL", rule["base_asset"])
        self.assertEqual("USDC", rule["quote_asset"])
        self.assertEqual(Decimal("0.01"), rule["min_order_size"])
        self.assertEqual(Decimal("0.1"), rule["min_price_increment"])
        self.assertEqual(Decimal("0.001"), rule["min_base_amount_increment"])
        self.assertEqual(Decimal("5"), rule["min_notional"])

    def test_ws_subscription_formatters(self):
        sub_msg = utils.format_ws_subscription_message("depth", "BTC_USDC")
        self.assertEqual({"method": "SUBSCRIBE", "params": ["depth.BTC_USDC"]}, sub_msg)
        unsub_msg = utils.format_ws_unsubscription_message("trade")
        self.assertEqual({"method": "UNSUBSCRIBE", "params": ["trade"]}, unsub_msg)


if __name__ == "__main__":
    unittest.main()
