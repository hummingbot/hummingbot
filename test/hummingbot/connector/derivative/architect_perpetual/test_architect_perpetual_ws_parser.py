import unittest
from decimal import Decimal

from hummingbot.core.data_type.common import TradeType

from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_ws_parser import (
    build_ws_subscribe_request,
    parse_depth_update_message,
    parse_trade_message,
)


class ArchitectPerpetualWsParserTests(unittest.TestCase):

    def test_build_ws_subscribe_request(self):
        req = build_ws_subscribe_request(["btcusdt@trade", "btcusdt@depth@100ms"], request_id=7)
        self.assertEqual({"method": "SUBSCRIBE", "params": ["btcusdt@trade", "btcusdt@depth@100ms"], "id": 7}, req)

    def test_parse_depth_update_message_valid(self):
        raw = {
            "e": "depthUpdate",
            "E": 1700000000123,
            "u": 123,
            "b": [["100.0", "1.5"], ["99.5", "0"]],
            "a": [["100.5", "2"], ["101.0", "3.0"]],
        }
        diff = parse_depth_update_message(raw, trading_pair="BTC-USDT")
        self.assertIsNotNone(diff)
        self.assertEqual(123, diff.update_id)
        self.assertEqual([(Decimal("100.0"), Decimal("1.5")), (Decimal("99.5"), Decimal("0"))], diff.bids)
        self.assertEqual([(Decimal("100.5"), Decimal("2")), (Decimal("101.0"), Decimal("3.0"))], diff.asks)
        self.assertAlmostEqual(1700000000.123, diff.timestamp)

    def test_parse_trade_message_buy_sell_semantics(self):
        raw_buy = {"e": "trade", "t": 1, "p": "100", "q": "0.1", "T": 1700000000000, "m": False}
        trade_buy = parse_trade_message(raw_buy, trading_pair="BTC-USDT")
        self.assertEqual(TradeType.BUY, trade_buy.trade_type)

        raw_sell = {"e": "trade", "t": 2, "p": "101", "q": "0.2", "T": 1700000001000, "m": True}
        trade_sell = parse_trade_message(raw_sell, trading_pair="BTC-USDT")
        self.assertEqual(TradeType.SELL, trade_sell.trade_type)
