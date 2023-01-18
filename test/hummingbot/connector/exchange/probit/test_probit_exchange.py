import asyncio
import unittest
from decimal import Decimal
from unittest.mock import patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.probit.probit_constants import MAX_ORDER_ID_LEN
from hummingbot.connector.exchange.probit.probit_exchange import ProbitExchange
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.event.events import OrderType


class TestProbitExchange(unittest.TestCase):
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
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.exchange = ProbitExchange(
            client_config_map=self.client_config_map,
            probit_api_key=self.api_key,
            probit_secret_key=self.api_secret_key,
            trading_pairs=[self.trading_pair]
        )

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 9

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True, trading_pair=self.trading_pair, max_id_len=MAX_ORDER_ID_LEN
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False, trading_pair=self.trading_pair, max_id_len=MAX_ORDER_ID_LEN
        )

        self.assertEqual(result, expected_client_order_id)
