import unittest

from hummingbot.connector.derivative.gate_io_perpetual import (
    gate_io_perpetual_constants as CONSTANTS,
    gate_io_perpetual_web_utils as web_utils,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class GateIoPerpetualWebUtilsTest(unittest.TestCase):

    def test_public_rest_url(self):
        url = web_utils.public_rest_url(CONSTANTS.ORDER_BOOK_PATH_URL)
        self.assertEqual("https://api.gateio.ws/api/v4/futures/usdt/order_book", url)

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))
