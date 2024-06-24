import asyncio
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.cube import cube_constants as CONSTANTS
from hummingbot.connector.exchange.cube.cube_api_user_stream_data_source import CubeAPIUserStreamDataSource
from hummingbot.connector.exchange.cube.cube_auth import CubeAuth
from hummingbot.connector.exchange.cube.cube_exchange import CubeExchange
from hummingbot.connector.exchange.cube.cube_ws_protobufs import trade_pb2
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class CubeUserStreamDataSourceUnitTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "SOL"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = "live"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = CubeAuth(api_key="1111111111-11111-11111-11111-1111111111",
                             secret_key="111111111111111111111111111111")
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = CubeExchange(
            client_config_map=client_config_map,
            cube_api_key="1111111111-11111-11111-11111-1111111111",
            cube_api_secret="111111111111111111111111111111",
            cube_subaccount_id="1",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = CubeAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        exchange_market_info = {"result": {
            "assets": [{
                "assetId": 5,
                "symbol": "SOL",
                "decimals": 9,
                "displayDecimals": 2,
                "settles": "true",
                "assetType": "Crypto",
                "sourceId": 3,
                "metadata": {},
                "status": 1
            }, {
                "assetId": 7,
                "symbol": "USDC",
                "decimals": 6,
                "displayDecimals": 2,
                "settles": "true",
                "assetType": "Crypto",
                "sourceId": 3,
                "metadata": {
                    "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                },
                "status": 1
            }],
            "markets": [
                {
                    "marketId": 100006,
                    "symbol": "SOLUSDC",
                    "baseAssetId": 5,
                    "baseLotSize": "10000000",
                    "quoteAssetId": 7,
                    "quoteLotSize": "100",
                    "priceDisplayDecimals": 2,
                    "protectionPriceLevels": 1000,
                    "priceBandBidPct": 25,
                    "priceBandAskPct": 400,
                    "priceTickSize": "0.01",
                    "quantityTickSize": "0.01",
                    "status": 1,
                    "feeTableId": 2
                }
            ]
        }}

        self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_market_info)

        trading_rule = TradingRule(
            self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("10000000") / (10 ** 9),
            min_notional_size=Decimal("100") / (10 ** 6),
        )

        self.connector._trading_rules[self.trading_pair] = trading_rule

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 2):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _error_response(self) -> Dict[str, Any]:
        resp = {
            "code": "ERROR CODE",
            "msg": "ERROR MESSAGE"
        }

        return resp

    def _boostrap_positions_event(self):
        # Boostrap message
        position = trade_pb2.AssetPosition(
            subaccount_id=11111,
            asset_id=5,
            total=trade_pb2.RawUnits(
                word0=7168273,
            ),
            available=trade_pb2.RawUnits(
                word0=7168273,
            )
        )

        positions = trade_pb2.AssetPositions(
            positions=[position]
        )

        boostrap = trade_pb2.Bootstrap(
            position=positions
        )
        return boostrap.SerializeToString()

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_get_user_update_event(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value, message=self._boostrap_positions_event(),
            message_type=aiohttp.WSMsgType.BINARY
        )

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        msg = self.async_run_with_timeout(msg_queue.get())
        self.assertEqual(self._boostrap_positions_event(), msg)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_connection_failed(self, mock_ws):
        mock_ws.side_effect = lambda *arg, **kwars: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR."))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_iter_message_throws_exception(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = (lambda *args, **kwargs:
                                                    self._create_exception_and_unlock_test_with_event(
                                                        Exception("TEST ERROR")))
        mock_ws.close.return_value = None

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
