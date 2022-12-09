from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.strategy.utils import order_age


class StrategyUtilsTests(TestCase):

    @patch("hummingbot.strategy.utils._time")
    def test_order_age(self, time_mock):
        time_mock.return_value = 1640001112.223
        order = LimitOrder(
            client_order_id="OID1",
            trading_pair="COINALPHA-HBOT",
            is_buy=True,
            base_currency="COINALPHA",
            quote_currency="HBOT",
            price=Decimal(1000),
            quantity=Decimal(1),
            creation_timestamp=1640001110000000)

        age = order_age(order)
        self.assertEqual(int(time_mock.return_value - 1640001110), age)
