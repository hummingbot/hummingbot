from unittest import TestCase
from unittest.mock import patch

from hummingbot.core.event.events import (
    TradeType
)

from hummingbot.connector.exchange.huobi import huobi_utils as utils


class HuobiUtilsTests(TestCase):

    @patch('hummingbot.connector.exchange.huobi.huobi_utils.get_tracking_nonce')
    def test_client_order_id_creation(self, nonce_provider_mock):
        nonce_provider_mock.return_value = 1000000000000000
        self.assertEqual("AAc484720a-buy-ETH-USDT-1000000000000000", utils.get_new_client_order_id(TradeType.BUY, "ETH-USDT"))
        self.assertEqual("AAc484720a-sell-ETH-USDT-1000000000000000", utils.get_new_client_order_id(TradeType.SELL, "ETH-USDT"))
