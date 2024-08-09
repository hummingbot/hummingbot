import asyncio
import time
from decimal import Decimal
from typing import Awaitable
from unittest import TestCase
from unittest.mock import patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.dydx_v4_perpetual import dydx_v4_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.dydx_v4_perpetual.data_sources.dydx_v4_data_source import DydxPerpetualV4Client
from hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_derivative import DydxV4PerpetualDerivative


class DydxPerpetualV4ClientTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all")
    def setUp(self, _) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.async_tasks = []
        asyncio.set_event_loop(self.async_loop)

        self.secret_phrase = "mirror actor skill push coach wait confirm orchard " \
                             "lunch mobile athlete gossip awake miracle matter " \
                             "bus reopen team ladder lazy list timber render wait"
        self._dydx_v4_chain_address = "dydx14zzueazeh0hj67cghhf9jypslcf9sh2n5k6art"
        self.base_asset = "TRX"
        self.quote_asset = "USD"  # linear
        self.trading_pair = "TRX-USD"

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.exchange = DydxV4PerpetualDerivative(
            client_config_map,
            self.secret_phrase,
            self._dydx_v4_chain_address,
            trading_pairs=[self.trading_pair],
        )
        self.exchange._margin_fractions[self.trading_pair] = {
            "initial": Decimal(0.1),
            "maintenance": Decimal(0.05),
            "clob_pair_id": "15",
            "atomicResolution": -4,
            "stepBaseQuantums": 1000000,
            "quantumConversionExponent": -9,
            "subticksPerTick": 1000000,
        }
        self.v4_client = DydxPerpetualV4Client(
            self.secret_phrase,
            self._dydx_v4_chain_address,
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
        return {"txhash": "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659",  # noqa: mock
                "raw_log": "[]"}  # noqa: mock

    @property
    def order_creation_request_successful_mock_response(self):
        return {"txhash": "017C130E3602A48E5C9D661CAC657BF1B79262D4B71D5C25B1DA62DE2338DA0E",  # noqa: mock
                "raw_log": "[]"}  # noqa: mock

    def test_calculate_quantums(self):
        result = DydxPerpetualV4Client.calculate_quantums(10, -2, 10)
        self.assertEqual(result, 1000)

    def test_calculate_subticks(self):
        result = DydxPerpetualV4Client.calculate_subticks(10, -2, -9, 1000000)
        self.assertEqual(result, 100000000000000)

    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.data_sources.dydx_v4_data_source.DydxPerpetualV4Client.send_tx_sync_mode")
    def test_cancel_order(self, send_tx_sync_mode_mock):
        send_tx_sync_mode_mock.return_value = self._order_cancelation_request_successful_mock_response
        result = self.async_run_with_timeout(self.v4_client.cancel_order(
            client_id=11,
            clob_pair_id=15,
            order_flags=CONSTANTS.ORDER_FLAGS_LONG_TERM,
            good_til_block_time=int(time.time()) + CONSTANTS.ORDER_EXPIRATION
        ))

        self.assertIn("txhash", result)

    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.data_sources.dydx_v4_data_source.DydxPerpetualV4Client.send_tx_sync_mode")
    def test_place_order(self, send_tx_sync_mode_mock):
        send_tx_sync_mode_mock.return_value = self.order_creation_request_successful_mock_response
        result = self.async_run_with_timeout(self.v4_client.place_order(
            market=self.trading_pair,
            type="LIMIT",
            side="BUY",
            price=10,
            size=1,
            client_id=11,
            post_only=False,
        ))

        self.assertIn("txhash", result)

    def test_query_account(self):
        sequence, acccount_number = self.async_run_with_timeout(self.v4_client.query_account())
        self.assertEqual(acccount_number, 33356)
