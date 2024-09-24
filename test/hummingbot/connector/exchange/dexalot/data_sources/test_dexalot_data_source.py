import asyncio
from decimal import Decimal
from typing import Awaitable
from unittest import TestCase
from unittest.mock import patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.dexalot.data_sources.dexalot_data_source import DexalotClient
from hummingbot.connector.exchange.dexalot.dexalot_exchange import DexalotExchange
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import OrderType, TradeType


class DexalotClientTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all")
    def setUp(self, _) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.async_tasks = []
        asyncio.set_event_loop(self.async_loop)
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.api_key = "someKey"
        self.base_asset = "AVAX"
        self.quote_asset = "USDC"  # linear
        self.trading_pair = "AVAX-USDC"

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.exchange = DexalotExchange(
            client_config_map=client_config_map,
            dexalot_api_key=self.api_key,
            dexalot_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        self.exchange._evm_params[self.trading_pair] = {
            "base_coin": self.base_asset,
            "quote_coin": self.quote_asset,
            "base_evmdecimals": Decimal(6),
            "quote_evmdecimals": Decimal(18),
        }
        self._tx_client = DexalotClient(
            self.api_secret,
            self.exchange
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def create_task(self, coroutine: Awaitable) -> asyncio.Task:
        task = self.async_loop.create_task(coroutine)
        self.async_tasks.append(task)
        return task

    @property
    def _order_cancelation_request_successful_mock_response(self):
        return "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659"  # noqa: mock

    @property
    def order_creation_request_successful_mock_response(self):
        return "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659"  # noqa: mock

    @patch(
        "hummingbot.connector.exchange.dexalot.data_sources.dexalot_data_source.DexalotClient._build_and_send_tx")
    def test_cancel_order(self, send_tx_sync_mode_mock):
        send_tx_sync_mode_mock.return_value = self._order_cancelation_request_successful_mock_response
        order = GatewayInFlightOrder(
            client_order_id="0xbdd7b2516b6da27e0f6ad078d4542154",  # noqa: mock
            exchange_order_id="0x000000000000000000000000000000000000000000000000000000006c04243c",  # noqa: mock
            trading_pair="AVAX-USDC",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=123123123,
            amount=Decimal("10"),
            price=Decimal("100"),
        )
        result = self.async_run_with_timeout(self._tx_client.cancel_order_list([order]))
        self.assertEqual("79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659", result)  # noqa: mock

    @patch(
        "hummingbot.connector.exchange.dexalot.data_sources.dexalot_data_source.DexalotClient._build_and_send_tx")
    def test_place_order(self, send_tx_sync_mode_mock):
        send_tx_sync_mode_mock.return_value = self.order_creation_request_successful_mock_response
        order = GatewayInFlightOrder(
            client_order_id="0xbdd7b2516b6da27e0f6ad078d4542154",  # noqa: mock
            trading_pair="AVAX-USDC",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=123123123,
            amount=Decimal("10"),
            price=Decimal("100"),
        )
        result = self.async_run_with_timeout(self._tx_client.add_order_list([order]))
        self.assertEqual("79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659", result)  # noqa: mock
