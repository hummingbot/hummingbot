import unittest
import asyncio
from decimal import Decimal
from hummingbot.connector.connector.balancer.balancer_connector import BalancerConnector

trading_pair = "WETH-DAI"


class BalancerConnectorUnitTest(unittest.TestCase):

    async def _test_update_balances(self):
        balancer = BalancerConnector()
        await balancer._update_balances()
        for token, bal in balancer.get_all_balances().items():
            print(f"{token}: {bal}")

    def test_update_balances(self):
        asyncio.get_event_loop().run_until_complete(self._test_update_balances())

    def test_get_quote_price(self):
        balancer = BalancerConnector()
        buy_price = balancer.get_quote_price("WETH-DAI", True, Decimal("1"))
        self.assertTrue(buy_price > 0)
        sell_price = balancer.get_quote_price("WETH-DAI", False, Decimal("1"))
        self.assertTrue(sell_price > 0)
        self.assertTrue(buy_price != sell_price)
