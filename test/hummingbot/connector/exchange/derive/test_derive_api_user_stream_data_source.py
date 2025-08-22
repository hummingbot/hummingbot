import asyncio

# from datetime import datetime, timezone
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.connector.exchange.derive import derive_constants as CONSTANTS
from hummingbot.connector.exchange.derive.derive_api_user_stream_data_source import DeriveAPIUserStreamDataSource
from hummingbot.connector.exchange.derive.derive_auth import DeriveAuth
from hummingbot.connector.exchange.derive.derive_exchange import DeriveExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class TestDeriveAPIUserStreamDataSource(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.api_key = "someKey"  # noqa: mock
        cls.sub_id = 45686
        cls.domain = "derive_testnet"
        cls.account_type = "market_maker"
        cls.trading_required = False
        cls.api_secret_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"  # noqa: mock

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None

        # Mock Web3 account creation
        self.mock_wallet = MagicMock()
        self.mock_wallet.address = "0x1234567890123456789012345678901234567890"  # noqa: mock
        with patch('eth_account.Account.from_key', return_value=self.mock_wallet):
            # Mock components
            self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
            self.mock_time_provider = MagicMock()
            self.mock_time_provider.time.return_value = 1738096054575
            self.auth = DeriveAuth(
                api_key=self.api_key,
                api_secret=self.api_secret_key,
                sub_id=self.sub_id,
                trading_required=self.trading_required,
                domain=self.domain
            )
            self.time_synchronizer = TimeSynchronizer()
            self.time_synchronizer.add_time_offset_ms_sample(0)

            # Initialize connector and data source
            self.connector = DeriveExchange(
                derive_api_key=self.api_key,
                derive_api_secret=self.api_secret_key,
                sub_id=self.sub_id,
                account_type=self.account_type,
                trading_required=self.trading_required,
                domain=self.domain,
                trading_pairs=[]
            )
            self.connector._web_assistants_factory._auth = self.auth

            self.data_source = DeriveAPIUserStreamDataSource(
                auth=self.auth,
                trading_pairs=[self.trading_pair],
                connector=self.connector,
                api_factory=self.connector._web_assistants_factory
            )

            self.data_source.logger().addHandler(self)
            self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def get_ws_auth_payload(self):
        return {
            "accept": "application/json",
            "wallet": self.api_key,
            "timestamp": "1738096054575",
            "signature": "0x67e1aa8bde8ce8eadeb055587525274b00961d113bdaad226cf17ba43c7ae3556b79ef36506f2429be165874558237044108d2b6b00086b4a5e366c8a0e257371c"  # noqa: mock
        }

    async def get_token(self):
        return "be4ffcc9-2b2b-4c3e-9d47-68bf062cf651"

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.derive.derive_auth.DeriveAuth.get_ws_auth_payload")
    @patch("hummingbot.connector.exchange.derive.derive_api_user_stream_data_source.DeriveAPIUserStreamDataSource._time")
    @patch("hummingbot.connector.exchange.derive.derive_web_utils.utc_now_ms")
    async def test_listen_for_user_stream_subscribes_to_orders_and_balances_events(self, mock_utc_now, mock_timestamp, mock_auth, ws_connect_mock):
        mock_timestamp.return_value = 1738096054575
        mock_utc_now.return_value = 1738096054576
        mock_auth.return_value = self.get_ws_auth_payload()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        result_subscribe_login = {"id": str(mock_utc_now.return_value), "result": "success"}
        result_subscribe_orders = {'subaccount_id': 45686,
                                   'order_id': 'fc60cce3-4b89-4836-b280-5e3999b09cc4',  # noqa: mock
                                   'instrument_name': 'BTC-USDC', 'direction': 'buy', 'label': '0x6d72c6b30f6411655c91d8023e8f3126',  # noqa: mock
                                   'quote_id': None, 'creation_timestamp': 1737806900308, 'last_update_timestamp': 1737806948556, 'limit_price': '1.6474', 'amount': '20', 'filled_amount': '0', 'average_price': '0', 'order_fee': '0', 'order_type': 'limit', 'time_in_force': 'gtc', 'order_status': 'cancelled', 'max_fee': '1000', 'signature_expiry_sec': 2147483647, 'nonce': 17378068982400,
                                   'signer': '0xe34167D92340c95A7775495d78bcc3Dc21cf11c0',  # noqa: mock
                                   'signature': '0xc227fd7855ee7a9d1e1eabfad96ce2a5dc8938b4d6c46e15286d6b7f3fc28e036e73b3828b838d3cae30fc619e6e1354ff45cd23c0a5343d6b3a4108ffc52d371c',  # noqa: mock
                                   'cancel_reason': 'user_request', 'mmp': False, 'is_transfer': False, 'replaced_order_id': None, 'trigger_type': None, 'trigger_price_type': None, 'trigger_price': None, 'trigger_reject_message': None}
        result_subscribe_trades = {'subaccount_id': 45686,
                                   'order_id': 'a192db6d-3df4-4141-9d68-635f79c15f65',  # noqa: mock
                                   'instrument_name': 'BTC-USDC', 'direction': 'buy', 'label': '0xa483d0f3c4c2f38ca0a7f2ad280042d9',  # noqa: mock
                                   'quote_id': None,
                                   'trade_id': '5f249af2-2a84-47b2-946e-2552f886f0a8',  # noqa: mock
                                   'timestamp': 1737810932869, 'mark_price': '1.667960602579197952', 'index_price': '1.667960602579197952', 'trade_price': '1.6682', 'trade_amount': '20', 'liquidity_role': 'maker', 'realized_pnl': '0', 'realized_pnl_excl_fees': '0', 'is_transfer': False, 'tx_status': 'requested', 'trade_fee': '0.05003881807737593856', 'tx_hash': None,
                                   'transaction_id': '23455412-476e-4fe0-992a-2c1e2042ceee'  # noqa: mock
                                   }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_login))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        output_queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(3, len(sent_subscription_messages))
        auth_responce = self.get_ws_auth_payload()
        expected_login_subscription = {
            "method": "public/login",
            "params": auth_responce,
            "id": str(mock_utc_now.return_value),
        }
        self.assertEqual(expected_login_subscription, sent_subscription_messages[0])
        expected_orders_subscription = {
            "method": "subscribe",
            "params": {
                "channels": [f"{self.sub_id}.orders"],
            }
        }
        self.assertEqual(expected_orders_subscription, sent_subscription_messages[1])
        expected_trades_subscription = {
            "method": "subscribe",
            "params": {
                "channels": [f"{self.sub_id}.trades"],
            }
        }
        self.assertEqual(expected_trades_subscription, sent_subscription_messages[2])
        # self.assertTrue(self._is_logged(
        #     "INFO",
        #     "Subscribed to private order and trades changes channels..."
        # ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_connection_failed(self, sleep_mock, mock_ws):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        msg_queue = asyncio.Queue()
        try:
            await self.data_source.listen_for_user_stream(msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    # @unittest.skip("Test with error")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_iter_message_throws_exception(self, sleep_mock, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        try:
            await self.data_source.listen_for_user_stream(msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
