from unittest import TestCase

from hummingbot.model.trade_fill import TradeFill


class TradeFillTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.display_name = "test_market"
        self.config_file_path = "test_config"
        self.strategy_name = "test_strategy"

        self.symbol = "COINALPHAHBOT"
        self.base = "COINALPHA"
        self.quote = "HBOT"
        self.trading_pair = f"{self.base}-{self.quote}"

    def test_attribute_names_for_file_export(self):
        expected_attributes = [
            "exchange_trade_id",
            "config_file_path",
            "strategy",
            "market",
            "symbol",
            "base_asset",
            "quote_asset",
            "timestamp",
            "order_id",
            "trade_type",
            "order_type",
            "price",
            "amount",
            "leverage",
            "trade_fee",
            "trade_fee_in_quote",
            "position", ]

        self.assertEqual(expected_attributes, TradeFill.attribute_names_for_file_export())
