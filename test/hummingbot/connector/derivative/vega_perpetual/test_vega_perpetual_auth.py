import asyncio
import json
import unittest

# from difflib import SequenceMatcher
from typing import Any, Awaitable, Dict

import hummingbot.connector.derivative.vega_perpetual.vega_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_auth import VegaPerpetualAuth
from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_data import VegaTimeInForce
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class VegaPerpetualAuthUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.public_key = "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece"  # noqa: mock
        cls.mnemonic = "liberty unfair next zero business small okay insane juice reject veteran random pottery model matter giant artist during six napkin pilot bike immune rigid"  # noqa: mock

    def setUp(self) -> None:
        super().setUp()
        self.emulated_time = 1697586789.042
        self.auth = VegaPerpetualAuth(
            public_key=self.public_key,
            mnemonic=self.mnemonic)

    def _get_order_submission_payload_mock(self) -> Dict[str, Any]:
        order_payload = {
            "market_id": "4941400d60f61c48fe1d14d4307ad1111a29a9bf8d0bb578b38958e607f2c21e",  # noqa: mock
            "price": "2815927079",
            "size": 1000,
            "side": CONSTANTS.HummingbotToVegaIntSide[TradeType.BUY],
            "time_in_force": VegaTimeInForce.TIME_IN_FORCE_GTC.value,
            "expires_at": 0,
            "type": CONSTANTS.HummingbotToVegaIntOrderType[OrderType.LIMIT],
            "reference": "BBPTC607eb5e88e39e599da3e5b0be3a",  # noqa: mock
            "pegged_order": None,
            "post_only": False,
            "reduce_only": False,
        }
        return order_payload

    def _get_signed_payload_from_mock(self) -> bytes:
        return "CocBCMjPgdQkEITWkgfKPnkKQDQ5NDE0MDBkNjBmNjFjNDhmZTFkMTRkNDMwN2FkMTExMWEyOWE5YmY4ZDBiYjU3OGIzODk1OGU2MDdmMmMyMWUSCjI4MTU5MjcwNzkY6AcgASgBOAFCIEJCUFRDNjA3ZWI1ZTg4ZTM5ZTU5OWRhM2U1YjBiZTNhEpMBCoABN2YxOTQ3NmYwNDk2MmM1OGY1MjE4ZWI3ZWUzNzkwOWViODkxMzRmYzE4MzcyODhlMzlhNzk5NzIzNmU4MWRlYzNlY2Q2NzIyNGUxZTBmZjliMmE2ZDlmZTk4OGRiNWUzN2Y3MGJjYmEwYzVhNzQ4MGIxMTVjZDc3Mzg3ZTA5MGISDHZlZ2EvZWQyNTUxORgB0j5AZjg4MmU5M2U2M2VhNjYyYjlkZGVlNmI2MWRlMTczNDVkNDQxYWRlMDY0NzU3ODg1NjFlNmQ0NzBiZWJjOWVjZYB9A8K7ASYKIDdkMTQzMDJmNDMyNTQ5NjVhNzllZjljYjBlMGEyOTU0EKSmAg==".encode("utf-8")  # noqa: mock

    def _get_raw_tx_send_mock(self) -> Dict[str, Any]:
        data = {"tx": str(self._get_signed_payload_from_mock().decode("utf-8")), "type": "TYPE_SYNC"}
        return data

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def time(self):
        # Implemented to emulate a TimeSynchronizer
        return self.emulated_time

    def test_confirm_pub_key_matches_generated(self):
        self.assertTrue(self.auth.confirm_pub_key_matches_generated())
        self.auth._mnemonic = ""
        self.assertFalse(self.auth.confirm_pub_key_matches_generated())

    # def test_sign_payload(self):

    #     signed_transaction = self.auth.sign_payload(self._get_order_submission_payload_mock(), 'order_submission')
    #     similar = SequenceMatcher(None, signed_transaction, self._get_signed_payload_from_mock()).ratio()
    #     self.assertGreaterEqual(similar, 0.4)

    def test_rest_authenticate_parameters_provided(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.GET, url="/TEST_PATH_URL", params={"TEST": "TEST_PARAM"}, is_auth_required=True
        )

        signed_request: RESTRequest = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertEqual(signed_request, request)

    def test_rest_authenticate_data_provided(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.POST, url="/TEST_PATH_URL", data=json.dumps(self._get_raw_tx_send_mock()), is_auth_required=True
        )

        signed_request: RESTRequest = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertEqual(signed_request, request)

    def test_ws_authenticate(self):
        request: WSJSONRequest = WSJSONRequest(
            throttler_limit_id="TEST_LIMIT_ID", payload={"TEST": "TEST_PAYLOAD"}, is_auth_required=True
        )

        signed_request: WSJSONRequest = self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(request, signed_request)
