#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../")))

from decimal import Decimal
import unittest
from hummingbot.connector.other.celo.celo_cli import CeloCLI, CELO_BASE, CELO_QUOTE


celo_address = "0x1640eb9C393630d5BC42Ff3f4e81A07912FC0fdd"
celo_password = "b"


class CeloCLIUnitTest(unittest.TestCase):

    def test_unlock_account(self):
        # test invalid password
        result = CeloCLI.unlock_account(celo_address, "XXX")
        print(result)
        self.assertNotEqual(result, None)
        # test invalid address
        result = CeloCLI.unlock_account("XXX", celo_password)
        print(result)
        self.assertNotEqual(result, None)

        result = CeloCLI.unlock_account(celo_address, celo_password)
        self.assertEqual(result, None)

    def test_balances(self):
        result = CeloCLI.unlock_account(celo_address, celo_password)
        self.assertEqual(result, None)
        results = CeloCLI.balances()
        self.assertTrue(results[CELO_BASE].total > 0)
        self.assertTrue(results[CELO_BASE].available() > 0)
        self.assertTrue(results[CELO_QUOTE].total > 0)
        self.assertTrue(results[CELO_QUOTE].available() > 0)

    def test_exchange_rate(self):
        rates = CeloCLI.exchange_rate(Decimal("1"))
        for rate in rates:
            print(rate)
        self.assertTrue(all(r.from_token in (CELO_BASE, CELO_QUOTE) and r.to_token in (CELO_BASE, CELO_QUOTE)
                            and r.from_token != r.to_amount for r in rates))
        self.assertTrue(all(r.from_amount > 0 and r.to_amount > 0 for r in rates))

    def test_sell_cgld(self):
        sell_amount = Decimal("1")
        result = CeloCLI.unlock_account(celo_address, celo_password)
        self.assertEqual(result, None)
        rates = CeloCLI.exchange_rate(sell_amount)
        sell_rate = [r for r in rates if r.from_token == CELO_BASE][0]
        tx_hash = CeloCLI.sell_cgld(sell_amount)
        self.assertTrue(len(tx_hash) > 0)
        tx_hash = CeloCLI.sell_cgld(sell_amount, sell_rate.to_amount * Decimal("0.999"))
        self.assertTrue(len(tx_hash) > 0)
        # set forAtLeast amount to 20% more than what was quoted should raise excecption
        with self.assertRaises(Exception) as context:
            tx_hash = CeloCLI.sell_cgld(sell_amount, sell_rate.to_amount * Decimal("1.2"))
        print(str(context.exception))

    def test_buy_cgld(self):
        # exchange atm is about 1.64, so let's buy about 2 USD
        buy_amount = Decimal("2")
        result = CeloCLI.unlock_account(celo_address, celo_password)
        self.assertEqual(result, None)
        rates = CeloCLI.exchange_rate(buy_amount)
        buy_rate = [r for r in rates if r.from_token == CELO_QUOTE][0]
        tx_hash = CeloCLI.buy_cgld(buy_amount)
        self.assertTrue(len(tx_hash) > 0)
        tx_hash = CeloCLI.buy_cgld(buy_amount, buy_rate.to_amount * Decimal("0.999"))
        self.assertTrue(len(tx_hash) > 0)
        # set forAtLeast amount to 20% more than what was quoted should raise excecption
        with self.assertRaises(Exception) as context:
            tx_hash = CeloCLI.buy_cgld(buy_amount, buy_rate.to_amount * Decimal("1.2"))
        print(str(context.exception))

    def test_validate_node_synced(self):
        err_msg = CeloCLI.validate_node_synced()
        self.assertEqual(None, err_msg)
