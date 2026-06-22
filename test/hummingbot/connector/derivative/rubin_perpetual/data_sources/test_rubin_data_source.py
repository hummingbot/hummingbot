import asyncio
import time
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Awaitable
from unittest.mock import patch

from hummingbot.connector.derivative.rubin_perpetual import rubin_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.rubin_perpetual.data_sources.rubin_data_source import RubinPerpetualV4Client
from hummingbot.connector.derivative.rubin_perpetual.rubin_perpetual_derivative import RubinPerpetualDerivative


class RubinPerpetualV4ClientTests(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher.fetch_all")
    def setUp(self, _) -> None:
        super().setUp()
        self.async_tasks = []

        self.secret_phrase = "mirror actor skill push coach wait confirm orchard " \
                             "lunch mobile athlete gossip awake miracle matter " \
                             "bus reopen team ladder lazy list timber render wait"
        self._rubin_chain_address = "rubin14zzueazeh0hj67cghhf9jypslcf9sh2n5k6art"
        self.base_asset = "TRX"
        self.quote_asset = "USD"  # linear
        self.trading_pair = "TRX-USD"

        self.exchange = RubinPerpetualDerivative(
            rubin_perpetual_secret_phrase=self.secret_phrase,
            rubin_perpetual_chain_address=self._rubin_chain_address,
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
        self.v4_client = RubinPerpetualV4Client(
            self.secret_phrase,
            self._rubin_chain_address,
            self.exchange
        )
        # Pre-initialize account state so order-flow tests don't make a live gRPC
        # query_account call (unit tests must not depend on a network connection).
        self.v4_client._is_trading_account_initialized = True
        self.v4_client.sequence = 0
        self.v4_client.number = 33356

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
        result = RubinPerpetualV4Client.calculate_quantums(10, -2, 10)
        self.assertEqual(result, 1000)

    def test_calculate_subticks(self):
        result = RubinPerpetualV4Client.calculate_subticks(10, -2, -9, 1000000)
        self.assertEqual(result, 100000000000000)

    @patch(
        "hummingbot.connector.derivative.rubin_perpetual.data_sources.rubin_data_source.RubinPerpetualV4Client.send_tx_sync_mode")
    async def test_cancel_order(self, send_tx_sync_mode_mock):
        send_tx_sync_mode_mock.return_value = self._order_cancelation_request_successful_mock_response
        result = await (self.v4_client.cancel_order(
            client_id=11,
            clob_pair_id=15,
            order_flags=CONSTANTS.ORDER_FLAGS_LONG_TERM,
            good_til_block_time=int(time.time()) + CONSTANTS.ORDER_EXPIRATION
        ))

        self.assertIn("txhash", result)

    @patch(
        "hummingbot.connector.derivative.rubin_perpetual.data_sources.rubin_data_source.RubinPerpetualV4Client.send_tx_sync_mode")
    async def test_place_order(self, send_tx_sync_mode_mock):
        send_tx_sync_mode_mock.return_value = self.order_creation_request_successful_mock_response
        result = await (self.v4_client.place_order(
            market=self.trading_pair,
            type="LIMIT",
            side="BUY",
            price=10,
            size=1,
            client_id=11,
            post_only=False,
        ))

        self.assertIn("txhash", result)

    async def test_query_account(self):
        from unittest.mock import AsyncMock, MagicMock

        from google.protobuf.any_pb2 import Any as ProtoAny
        from ritbit_v4_proto.cosmos.auth.v1beta1.auth_pb2 import BaseAccount

        packed = ProtoAny()
        packed.Pack(BaseAccount(account_number=33356, sequence=0))
        response = MagicMock()
        response.account = packed
        self.v4_client.auth_client = MagicMock()
        self.v4_client.auth_client.Account = AsyncMock(return_value=response)

        sequence, acccount_number = await (self.v4_client.query_account())
        self.assertEqual(acccount_number, 33356)

    def test__init__without_secret(self):
        with self.assertRaises(ValueError) as e:
            self.v4_client = RubinPerpetualV4Client(
                '',
                self._rubin_chain_address,
                self.exchange
            )
            self.assertEqual(str(e.exception), "Mnemonic words count is not valid (0)")
