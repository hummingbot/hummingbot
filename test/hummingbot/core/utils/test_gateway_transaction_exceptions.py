"""
Unit tests for test_check_transaction_exceptions
"""

from decimal import Decimal
from typing import Dict, Any
import unittest.mock

from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway import check_transaction_exceptions


class CheckTransactionExceptionsTest(unittest.TestCase):
    def test_check_transaction_exceptions(self):
        """
        Unit tests for hummingbot.core.gateway.check_transaction_exceptions
        """

        # create transactions data that should result in no warnings
        transaction_args: Dict[Any] = {
            "allowances": {"WBTC": Decimal(1000)},
            "balances": {"ETH": Decimal(1000)},
            "base_asset": "ETH",
            "quote_asset": "WBTC",
            "amount": Decimal(1000),
            "side": TradeType.BUY,
            "gas_limit": 22000,
            "gas_cost": Decimal(90),
            "gas_asset": "ETH",
            "swaps_count": 2
        }
        self.assertEqual(check_transaction_exceptions(**transaction_args), [])

        # ETH balance less than gas_cost
        invalid_transaction_1 = transaction_args.copy()
        invalid_transaction_1["balances"] = {"ETH": Decimal(10)}
        self.assertRegexpMatches(
            check_transaction_exceptions(**invalid_transaction_1)[0], r"^Insufficient ETH balance to cover gas"
        )

        # Gas limit set too low, gas_limit is less than 21000
        invalid_transaction_2 = transaction_args.copy()
        invalid_transaction_2["gas_limit"] = 10000
        self.assertRegexpMatches(check_transaction_exceptions(**invalid_transaction_2)[0], r"^Gas limit")

        # Insufficient token allowance, allowance of quote less than amount
        invalid_transaction_3 = transaction_args.copy()
        invalid_transaction_3["allowances"] = {"WBTC": Decimal(500)}
        self.assertRegexpMatches(check_transaction_exceptions(**invalid_transaction_3)[0], r"^Insufficient")
