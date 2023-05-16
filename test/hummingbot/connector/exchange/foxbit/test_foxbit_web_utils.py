import unittest

from hummingbot.connector.exchange.foxbit import (
    foxbit_constants as CONSTANTS,
    foxbit_utils as utils,
    foxbit_web_utils as web_utils,
)


class FoxbitUtilTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        path_url = "TEST_PATH"
        domain = "com.br"
        expected_url = f"https://{CONSTANTS.REST_URL}/rest/{CONSTANTS.PUBLIC_API_VERSION}/{path_url}"
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url, domain))

    def test_private_rest_url(self):
        path_url = "TEST_PATH"
        domain = "com.br"
        expected_url = f"https://{CONSTANTS.REST_URL}/rest/{CONSTANTS.PRIVATE_API_VERSION}/{path_url}"
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url, domain))

    def test_rest_endpoint_url(self):
        path_url = "TEST_PATH"
        domain = "com.br"
        expected_url = f"/rest/{CONSTANTS.PRIVATE_API_VERSION}/{path_url}"
        public_url = web_utils.public_rest_url(path_url, domain)
        private_url = web_utils.private_rest_url(path_url, domain)
        self.assertEqual(expected_url, web_utils.rest_endpoint_url(public_url))
        self.assertEqual(expected_url, web_utils.rest_endpoint_url(private_url))

    def test_websocket_url(self):
        expected_url = f"wss://{CONSTANTS.WSS_URL}/"
        self.assertEqual(expected_url, web_utils.websocket_url())

    def test_format_ws_header(self):
        header = utils.get_ws_message_frame(
            endpoint=CONSTANTS.WS_AUTHENTICATE_USER,
            msg_type=CONSTANTS.WS_MESSAGE_FRAME_TYPE["Request"]
        )
        retValue = web_utils.format_ws_header(header)
        self.assertEqual(retValue, web_utils.format_ws_header(header))

    def test_create_throttler(self):
        self.assertIsNotNone(web_utils.create_throttler())
