from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual.grvt_exchange_info import (
    exchange_symbol_to_hb_trading_pair,
    extract_symbol_map,
    instrument_is_active,
)


class GrvtExchangeInfoTests(TestCase):
    def test_exchange_symbol_to_hb_trading_pair(self):
        self.assertEqual("BTC-USDC", exchange_symbol_to_hb_trading_pair("BTC/USDC"))

    def test_instrument_is_active(self):
        self.assertTrue(instrument_is_active({"status": "active"}))
        self.assertFalse(instrument_is_active({"status": "halted"}))

    def test_extract_symbol_map(self):
        mapping = extract_symbol_map([{"symbol": "BTC-USDC", "status": "active"}])
        self.assertIn("BTC-USDC", mapping)
