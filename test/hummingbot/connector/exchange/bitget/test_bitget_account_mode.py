import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, List
from unittest.mock import AsyncMock

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.bitget.bitget_constants as CONSTANTS
import hummingbot.connector.exchange.bitget.bitget_web_utils as web_utils
from hummingbot.connector.exchange.bitget import bitget_account
from hummingbot.connector.exchange.bitget.bitget_exchange import BitgetExchange
from hummingbot.core.data_type.common import OrderType, TradeType


class BitgetAccountModeTests(IsolatedAsyncioWrapperTestCase):
    """bitget serves both Classic and Unified Trading Accounts and tells them apart from the V3 answer."""

    level = 0

    def setUp(self) -> None:
        super().setUp()
        bitget_account.forget_all()
        self.log_records: List[Any] = []
        self.exchange = BitgetExchange(
            bitget_api_key="test_api_key",
            bitget_secret_key="test_secret_key",
            bitget_passphrase="test_passphrase",
            trading_pairs=["BTC-USDT"],
            trading_required=False,
        )
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)

    def tearDown(self) -> None:
        bitget_account.forget_all()
        super().tearDown()

    def handle(self, record: Any) -> None:
        self.log_records.append(record)

    def _is_logged(self, level: str, message: str) -> bool:
        return any(r.levelname == level and r.getMessage() == message for r in self.log_records)

    @staticmethod
    def _assets_url() -> re.Pattern:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ASSETS_ENDPOINT)
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

    @staticmethod
    def _requests_to(mock_api: aioresponses, endpoint: str) -> int:
        url = web_utils.private_rest_url(path_url=endpoint)
        return sum(len(calls) for (_, request_url), calls in mock_api.requests.items()
                   if str(request_url).startswith(url))

    @aioresponses()
    async def test_a_classic_account_is_detected_from_the_v3_refusal(self, mock_api):
        mock_api.get(self._assets_url(), status=400, body=json.dumps({
            "code": "40084", "msg": "You are in Classic Account mode, and the Unified Account API is not supported",
            "requestTime": 1746687063471, "data": None}))

        self.assertFalse(await self.exchange._is_unified_account())
        self.assertTrue(self._is_logged("INFO", "Bitget account mode: Classic."))

    @aioresponses()
    async def test_a_classic_refusal_reported_with_http_200_is_detected_too(self, mock_api):
        mock_api.get(self._assets_url(), body=json.dumps({"code": "40084", "msg": "Classic", "data": None}))

        self.assertFalse(await self.exchange._is_unified_account())

    @aioresponses()
    async def test_a_unified_trading_account_is_detected(self, mock_api):
        mock_api.get(self._assets_url(), body=json.dumps({"code": "00000", "msg": "success", "data": {"assets": []}}))

        self.assertTrue(await self.exchange._is_unified_account())
        self.assertTrue(self._is_logged("INFO", "Bitget account mode: Unified Trading Account."))

    @aioresponses()
    async def test_the_mode_is_read_once(self, mock_api):
        mock_api.get(self._assets_url(), body=json.dumps({"code": "00000", "msg": "success", "data": {"assets": []}}))

        await self.exchange._is_unified_account()
        await self.exchange._is_unified_account()

        self.assertEqual(1, self._requests_to(mock_api, CONSTANTS.ASSETS_ENDPOINT))

    @aioresponses()
    async def test_any_other_failure_is_raised_and_retried_later(self, mock_api):
        # The requestTime contains 40084, which must not be mistaken for the Classic refusal.
        mock_api.get(self._assets_url(), status=400, body=json.dumps({
            "code": "40006", "msg": "Invalid ACCESS_KEY", "requestTime": 1740084000000, "data": None}))
        mock_api.get(self._assets_url(), body=json.dumps({"code": "00000", "msg": "success", "data": {"assets": []}}))

        with self.assertRaises(IOError):
            await self.exchange._is_unified_account()
        self.assertIsNone(self.exchange._unified_account)

        self.assertTrue(await self.exchange._is_unified_account())

    @aioresponses()
    async def test_an_unexpected_code_is_raised(self, mock_api):
        mock_api.get(self._assets_url(), body=json.dumps({"code": "40099", "msg": "Unexpected", "data": None}))

        with self.assertRaises(IOError):
            await self.exchange._is_unified_account()
        self.assertIsNone(self.exchange._unified_account)

    def test_a_classic_account_has_no_account_group(self):
        self.exchange._unified_account = False
        self.assertIsNone(self.exchange.account_group_id)

        self.exchange._unified_account = True
        self.assertTrue(self.exchange.account_group_id.startswith("bitget_uta:"))

    @aioresponses()
    async def test_a_classic_account_places_orders_through_the_v2_api(self, mock_api):
        self.exchange._unified_account = False
        self.exchange._set_trading_pair_symbol_map(bidict({"BTCUSDT": "BTC-USDT"}))
        url = web_utils.private_rest_url(path_url=CONSTANTS.CLASSIC_PLACE_ORDER_ENDPOINT)
        mock_api.post(re.compile(f"^{url}".replace(".", r"\.")), body=json.dumps(
            {"code": "00000", "msg": "success", "data": {"orderId": "1", "clientOid": "OID1"}}))

        exchange_order_id, _ = await self.exchange._place_order(
            order_id="OID1", trading_pair="BTC-USDT", amount=Decimal("1"), trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT, price=Decimal("100"))

        self.assertEqual("1", exchange_order_id)
        self.assertEqual(1, self._requests_to(mock_api, CONSTANTS.CLASSIC_PLACE_ORDER_ENDPOINT))
        self.assertEqual(0, self._requests_to(mock_api, CONSTANTS.PLACE_ORDER_ENDPOINT))

    async def test_the_user_stream_listener_waits_out_a_failed_account_mode_read(self):
        self.exchange._sleep = AsyncMock()
        self.exchange._is_unified_account = AsyncMock(side_effect=[IOError("Read timed out"), False])
        self.exchange._classic_user_stream_event_listener = AsyncMock()

        await self.exchange._user_stream_event_listener()

        self.exchange._classic_user_stream_event_listener.assert_awaited_once()
        self.exchange._sleep.assert_awaited_once_with(CONSTANTS.ACCOUNT_MODE_RETRY_INTERVAL_SECONDS)
        self.assertTrue(self._is_logged(
            "WARNING", "Could not read the account mode; retrying before reading the user stream."))
