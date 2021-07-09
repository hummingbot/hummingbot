import unittest
from decimal import Decimal
import asyncio

from hummingbot.strategy.amm_arb import utils
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

trading_pair = "HBOT-USDT"
base = trading_pair.split("-")[0]
quote = trading_pair.split("-")[1]


class MockConnector1(ConnectorBase):
    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        if is_buy:
            return Decimal("105")
        else:
            return Decimal("104")

    def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        return self.get_quote_price(trading_pair, is_buy, amount)


class MockConnector2(ConnectorBase):
    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        if is_buy:
            return Decimal("103")
        else:
            return Decimal("100")

    def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        return self.get_quote_price(trading_pair, is_buy, amount)


class AmmArbUtilsUnitTest(unittest.TestCase):

    def test_create_arb_proposals(self):
        asyncio.get_event_loop().run_until_complete(self._test_create_arb_proposals())

    async def _test_create_arb_proposals(self):
        market_info1 = MarketTradingPairTuple(MockConnector1(), trading_pair, base, quote)
        market_info2 = MarketTradingPairTuple(MockConnector2(), trading_pair, base, quote)
        arb_proposals = await utils.create_arb_proposals(market_info1, market_info2, Decimal("1"))
        # there are 2 proposal combination possible - (buy_1, sell_2) and (buy_2, sell_1)
        self.assertEqual(2, len(arb_proposals))
        # Each proposal has a buy and a sell proposal sides
        self.assertNotEqual(arb_proposals[0].first_side.is_buy, arb_proposals[0].second_side.is_buy)
        self.assertNotEqual(arb_proposals[1].first_side.is_buy, arb_proposals[1].second_side.is_buy)
        buy_1_sell_2_profit_pct = (Decimal("100") - Decimal("105")) / Decimal("105")
        self.assertEqual(buy_1_sell_2_profit_pct, arb_proposals[0].profit_pct())
        buy_2_sell_1_profit_pct = (Decimal("104") - Decimal("103")) / Decimal("103")
        self.assertEqual(buy_2_sell_1_profit_pct, arb_proposals[1].profit_pct())
