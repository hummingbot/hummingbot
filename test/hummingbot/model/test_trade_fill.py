import time
from decimal import Decimal
from unittest import TestCase

from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import (
    OrderType,
    TradeType,
)
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
            "position", ]

        self.assertEqual(expected_attributes, TradeFill.attribute_names_for_file_export())

    def test_attribute_names_for_file_export_are_valid(self):
        trade_fill = TradeFill(
            config_file_path=self.config_file_path,
            strategy=self.strategy_name,
            market=self.display_name,
            symbol=self.symbol,
            base_asset=self.base,
            quote_asset=self.quote,
            timestamp=int(time.time()),
            order_id="OID1",
            trade_type=TradeType.BUY.name,
            order_type=OrderType.LIMIT.name,
            price=Decimal(1000),
            amount=Decimal(1),
            leverage=1,
            trade_fee=AddedToCostTradeFee().to_json(),
            exchange_trade_id="EOID1",
            position="NILL")

        values = [getattr(trade_fill, attribute) for attribute in TradeFill.attribute_names_for_file_export()]

        expected_values = [
            trade_fill.exchange_trade_id,
            trade_fill.config_file_path,
            trade_fill.strategy,
            trade_fill.market,
            trade_fill.symbol,
            trade_fill.base_asset,
            trade_fill.quote_asset,
            trade_fill.timestamp,
            trade_fill.order_id,
            trade_fill.trade_type,
            trade_fill.order_type,
            trade_fill.price,
            trade_fill.amount,
            trade_fill.leverage,
            trade_fill.trade_fee,
            trade_fill.position,
        ]

        self.assertEqual(expected_values, values)
