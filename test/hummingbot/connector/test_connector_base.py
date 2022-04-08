import unittest
import unittest.mock
from decimal import Decimal

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee


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
    @classmethod
    def setUpClass(cls):
        cls._patcher = unittest.mock.patch("hummingbot.connector.connector_base.estimate_fee")
        cls._url_mock = cls._patcher.start()
        cls._url_mock.return_value = AddedToCostTradeFee(percent=Decimal("0"), flat_fees=[])

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patcher.stop()

    def test_in_flight_asset_balances(self):
        connector = ConnectorBase()
        connector.real_time_balance_update = True
        print(connector._account_balances)
        orders = {
            "1": InFightOrderTest("1", "A", "HBOT-USDT", OrderType.LIMIT, TradeType.BUY, 100, 1, 1640001112.0, "live"),
            "2": InFightOrderTest("2", "B", "HBOT-USDT", OrderType.LIMIT, TradeType.BUY, 100, 2, 1640001112.0, "live"),
            "3": InFightOrderTest("3", "C", "HBOT-USDT", OrderType.LIMIT, TradeType.SELL, 110,
                                  Decimal("1.5"), 1640001112.0, "live")
        }
        bals = connector.in_flight_asset_balances(orders)
        self.assertEqual(Decimal("300"), bals["USDT"])
        self.assertEqual(Decimal("1.5"), bals["HBOT"])
        print(bals)
