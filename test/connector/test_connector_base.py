#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../")))
import unittest
from decimal import Decimal
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.event.events import OrderType, TradeType

from hummingbot.connector.connector_base import ConnectorBase


class InFightOrderTest(InFlightOrderBase):
    @property
    def is_done(self) -> bool:
        return False

    @property
    def is_cancelled(self) -> bool:
        return False

    @property
    def is_failure(self) -> bool:
        return False


class ConnectorBaseUnitTest(unittest.TestCase):

    def test_in_flight_asset_balances(self):
        connector = ConnectorBase(balance_limits={}, fee_estimates={})
        print(connector._account_balances)
        orders = {
            "1": InFightOrderTest(connector, "1", "A", "HBOT-USDT", OrderType.LIMIT, TradeType.BUY, 100, 1, "live"),
            "2": InFightOrderTest(connector, "2", "B", "HBOT-USDT", OrderType.LIMIT, TradeType.BUY, 100, 2, "live"),
            "3": InFightOrderTest(connector, "3", "C", "HBOT-USDT", OrderType.LIMIT, TradeType.SELL, 110,
                                  Decimal("1.5"), "live")
        }
        bals = connector.in_flight_asset_balances(orders)
        self.assertEqual(Decimal("300"), bals["USDT"])
        self.assertEqual(Decimal("1.5"), bals["HBOT"])
        print(bals)
