import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import patch

from aioresponses import CallbackResult, aioresponses

import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_constants as PERP_CONSTANTS
import hummingbot.connector.exchange.bitget.bitget_constants as CONSTANTS
import hummingbot.connector.exchange.bitget.bitget_web_utils as web_utils
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_derivative import BitgetPerpetualDerivative
from hummingbot.connector.exchange.bitget import bitget_account
from hummingbot.connector.exchange.bitget.bitget_exchange import BitgetExchange

API_KEY = "test_api_key"
SECRET_KEY = "test_secret_key"
PASSPHRASE = "test_passphrase"
USER_ID = "123456789"


class BitgetAccountGroupTests(IsolatedAsyncioWrapperTestCase):
    """
    Bitget's UTA is one cross-margined wallet read by both connectors, so both report the same
    funds. They advertise a shared account id to stop that wallet being counted twice.
    """

    def setUp(self) -> None:
        super().setUp()
        # The learned user ids are process-wide, so other tests must not leak into these.
        bitget_account.forget_all()

    def tearDown(self) -> None:
        bitget_account.forget_all()
        super().tearDown()

    @staticmethod
    def _spot(api_key=API_KEY):
        connector = BitgetExchange(
            bitget_api_key=api_key,
            bitget_secret_key=SECRET_KEY,
            bitget_passphrase=PASSPHRASE,
            trading_pairs=["BTC-USDT"],
            trading_required=False,
        )
        connector._unified_account = True
        connector._time_synchronizer.add_time_offset_ms_sample(0)
        return connector

    @staticmethod
    def _perpetual(api_key=API_KEY):
        connector = BitgetPerpetualDerivative(
            bitget_perpetual_api_key=api_key,
            bitget_perpetual_secret_key=SECRET_KEY,
            bitget_perpetual_passphrase=PASSPHRASE,
            trading_pairs=["BTC-USDT"],
            trading_required=False,
        )
        connector._unified_account = True
        connector._time_synchronizer.add_time_offset_ms_sample(0)
        return connector

    @staticmethod
    def _user_info_url() -> str:
        # Both connectors read the same account endpoint on the same host.
        assert CONSTANTS.USER_INFO_ENDPOINT == PERP_CONSTANTS.USER_INFO_ENDPOINT
        return web_utils.private_rest_url(path_url=CONSTANTS.USER_INFO_ENDPOINT)

    def _user_info_regex(self) -> re.Pattern:
        return re.compile(f"^{self._user_info_url()}".replace(".", r"\.").replace("?", r"\?"))

    @staticmethod
    def _user_info_body(user_id: str = USER_ID) -> str:
        return json.dumps({"code": "00000", "msg": "success", "requestTime": 1744617600000,
                           "data": {"userId": user_id, "parentId": None, "permType": "read_and_write"}})

    def _mock_user_id(self, mock_api: aioresponses, user_id: str = USER_ID, status: int = 200):
        mock_api.get(self._user_info_regex(), status=status, body=self._user_info_body(user_id))

    def _user_info_requests(self, mock_api: aioresponses) -> int:
        return sum(len(calls) for (method, url), calls in mock_api.requests.items()
                   if str(url).startswith(self._user_info_url()))

    def test_both_connectors_share_an_account_id_for_the_same_key(self):
        self.assertEqual(self._spot().account_group_id, self._perpetual().account_group_id)

    def test_different_api_keys_are_different_accounts_until_the_user_id_is_read(self):
        self.assertNotEqual(
            self._spot().account_group_id,
            self._spot(api_key="a_different_api_key").account_group_id,
        )

    def test_the_api_key_is_not_recoverable_from_the_id(self):
        group_id = self._spot().account_group_id

        self.assertNotIn(API_KEY, group_id)
        self.assertTrue(group_id.startswith("bitget_uta:"))

    def test_no_account_id_without_credentials(self):
        """The rate source builds connectors with no keys; they hold no account to group."""
        self.assertIsNone(self._spot(api_key="").account_group_id)

    @aioresponses()
    async def test_two_api_keys_of_one_account_share_an_id(self, mock_api):
        spot = self._spot(api_key="key_for_spot")
        perpetual = self._perpetual(api_key="key_for_perpetual")
        self._mock_user_id(mock_api)
        self._mock_user_id(mock_api)

        await spot._update_account_uid()
        await perpetual._update_account_uid()

        self.assertEqual(spot.account_group_id, perpetual.account_group_id)

    @aioresponses()
    async def test_different_accounts_have_different_ids(self, mock_api):
        main_account = self._spot(api_key="main_account_key")
        sub_account = self._spot(api_key="sub_account_key")
        self._mock_user_id(mock_api, user_id="111111111")
        self._mock_user_id(mock_api, user_id="222222222")

        await main_account._update_account_uid()
        await sub_account._update_account_uid()

        self.assertNotEqual(main_account.account_group_id, sub_account.account_group_id)

    @aioresponses()
    async def test_the_user_id_is_not_recoverable_from_the_id(self, mock_api):
        spot = self._spot()
        self._mock_user_id(mock_api)

        await spot._update_account_uid()

        self.assertNotIn(USER_ID, spot.account_group_id)
        self.assertNotIn(API_KEY, spot.account_group_id)
        self.assertTrue(spot.account_group_id.startswith("bitget_uta:"))

    @aioresponses()
    async def test_the_user_id_is_read_once_per_api_key(self, mock_api):
        spot = self._spot()
        perpetual = self._perpetual()
        self._mock_user_id(mock_api)

        await spot._update_account_uid()
        await spot._update_account_uid()
        await perpetual._update_account_uid()

        self.assertEqual(1, self._user_info_requests(mock_api))
        self.assertEqual(spot.account_group_id, perpetual.account_group_id)

    @aioresponses()
    async def test_same_key_connectors_match_when_only_one_read_succeeds(self, mock_api):
        """
        The balance command refreshes both connectors at once and the endpoint allows one call per
        second, so one read can be refused. The connector that failed must still match the other.
        """
        spot = self._spot()
        perpetual = self._perpetual()
        answered = []

        async def _refuse_the_first_read_while_the_second_goes_out(*args, **kwargs):
            answered.append(None)
            if len(answered) == 1:
                await asyncio.sleep(0)
                return CallbackResult(status=429, body=json.dumps({"code": "429", "msg": "Too Many Requests"}))
            return CallbackResult(status=200, body=self._user_info_body())

        mock_api.get(self._user_info_regex(), callback=_refuse_the_first_read_while_the_second_goes_out, repeat=True)

        await asyncio.gather(spot._update_account_uid(), perpetual._update_account_uid())

        self.assertEqual(2, self._user_info_requests(mock_api))
        self.assertEqual(USER_ID, bitget_account.known_user_id(API_KEY))
        self.assertEqual(spot.account_group_id, perpetual.account_group_id)
        self.assertNotEqual(self._spot(api_key="unrelated_key").account_group_id, spot.account_group_id)

    @aioresponses()
    async def test_a_failed_read_falls_back_to_the_api_key_and_retries_after_the_interval(self, mock_api):
        spot = self._spot()
        key_based_id = spot.account_group_id
        self._mock_user_id(mock_api, status=400)
        self._mock_user_id(mock_api)

        with patch.object(bitget_account, "_time", return_value=1000.0):
            await spot._update_account_uid()
            await spot._update_account_uid()

        self.assertEqual(key_based_id, spot.account_group_id)
        self.assertEqual(1, self._user_info_requests(mock_api))

        retry_at = 1000.0 + bitget_account.USER_ID_RETRY_INTERVAL_SECONDS
        with patch.object(bitget_account, "_time", return_value=retry_at):
            await spot._update_account_uid()

        self.assertEqual(2, self._user_info_requests(mock_api))
        self.assertEqual(USER_ID, bitget_account.known_user_id(API_KEY))
        self.assertNotEqual(key_based_id, spot.account_group_id)

    @aioresponses()
    async def test_a_response_without_a_user_id_counts_as_a_failed_read(self, mock_api):
        spot = self._spot()
        key_based_id = spot.account_group_id
        mock_api.get(self._user_info_regex(), body=json.dumps({"code": "00000", "msg": "success", "data": {}}))

        with patch.object(bitget_account, "_time", return_value=1000.0):
            await spot._update_account_uid()
            await spot._update_account_uid()

        self.assertEqual(key_based_id, spot.account_group_id)
        self.assertEqual(1, self._user_info_requests(mock_api))

    @aioresponses()
    async def test_balance_updates_read_the_user_id_on_both_connectors(self, mock_api):
        """The balance command reads account_group_id right after _update_balances."""
        assets_body = json.dumps({"code": "00000", "msg": "success", "data": {"assets": [
            {"coin": "USDT", "available": "10", "locked": "0", "balance": "10"}]}})
        for api_key, connector, assets_endpoint in (
            ("key_for_spot", self._spot(api_key="key_for_spot"), CONSTANTS.ASSETS_ENDPOINT),
            ("key_for_perpetual", self._perpetual(api_key="key_for_perpetual"),
             PERP_CONSTANTS.ACCOUNTS_INFO_ENDPOINT),
        ):
            assets_url = web_utils.private_rest_url(path_url=assets_endpoint)
            mock_api.get(re.compile(f"^{assets_url}".replace(".", r"\.").replace("?", r"\?")), body=assets_body)
            self._mock_user_id(mock_api)

            await connector._update_balances()

            self.assertEqual(USER_ID, bitget_account.known_user_id(api_key))
            self.assertEqual(10, connector.get_balance("USDT"))
