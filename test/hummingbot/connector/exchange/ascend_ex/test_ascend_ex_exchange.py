import asyncio
import unittest
from decimal import Decimal

from hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange import (
    AscendExExchange,
    AscendExTradingRule,
    AscendExCommissionType,
)
from hummingbot.core.event.events import OrderType, TradeType


class TestAscendExExchange(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()
        self.exchange = AscendExExchange(self.api_key, self.api_secret_key, trading_pairs=[self.trading_pair])

    def simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: AscendExTradingRule(
                trading_pair=self.trading_pair,
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
                min_notional_size=Decimal("0.001"),
                max_notional_size=Decimal("99999999"),
                commission_type=AscendExCommissionType.QUOTE,
                commission_reserve_rate=Decimal("0.002"),
            ),
        }

    def test_get_fee(self):
        self.simulate_trading_rules_initialized()
        trading_rule: AscendExTradingRule = self.exchange._trading_rules[self.trading_pair]
        amount = Decimal("1")
        price = Decimal("2")
        trading_rule.commission_reserve_rate = Decimal("0.002")

        trading_rule.commission_type = AscendExCommissionType.QUOTE
        buy_fee = self.exchange.get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, amount, price)
        sell_fee = self.exchange.get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.SELL, amount, price)

        self.assertEqual(Decimal("0.002"), buy_fee.percent)
        self.assertEqual(Decimal("0"), sell_fee.percent)

        trading_rule.commission_type = AscendExCommissionType.BASE
        buy_fee = self.exchange.get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, amount, price)
        sell_fee = self.exchange.get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.SELL, amount, price)

        self.assertEqual(Decimal("0"), buy_fee.percent)
        self.assertEqual(Decimal("0.002"), sell_fee.percent)

        trading_rule.commission_type = AscendExCommissionType.RECEIVED
        buy_fee = self.exchange.get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, amount, price)
        sell_fee = self.exchange.get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.SELL, amount, price)

        self.assertEqual(Decimal("0"), buy_fee.percent)
        self.assertEqual(Decimal("0"), sell_fee.percent)
