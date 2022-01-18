import unittest

from hummingbot.connector.exchange.gate_io.gate_io_utils import (
    GateIORESTRequest
)
from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class GateIORESTRequestTest(unittest.TestCase):
    def test_get_auth_url(self):
        endpoint = CONSTANTS.SYMBOL_PATH_URL
        request = GateIORESTRequest(method=RESTMethod.GET, endpoint=endpoint)

        auth_url = request.auth_url

        self.assertEqual(f"{CONSTANTS.REST_URL_AUTH}/{endpoint}", auth_url)

    def test_get_auth_url_raises_on_no_endpoint(self):
        endpoint = CONSTANTS.SYMBOL_PATH_URL
        request = GateIORESTRequest(
            method=RESTMethod.GET, url=f"{CONSTANTS.REST_URL}/{endpoint}"
        )

        with self.assertRaises(ValueError):
            _ = request.auth_url
