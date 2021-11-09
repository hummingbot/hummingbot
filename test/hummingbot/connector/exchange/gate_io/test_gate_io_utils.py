import json
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

    def test_constructs_url_from_endpoint(self):
        endpoint = CONSTANTS.SYMBOL_PATH_URL
        request = GateIORESTRequest(method=RESTMethod.GET, endpoint=endpoint)

        url = request.url

        self.assertEqual(f"{CONSTANTS.REST_URL}/{endpoint}", url)

    def test_raises_on_no_url_and_no_endpoint(self):
        with self.assertRaises(ValueError):
            GateIORESTRequest(method=RESTMethod.GET)

    def test_raises_on_params_supplied_to_post_request(self):
        endpoint = CONSTANTS.SYMBOL_PATH_URL
        params = {"one": 1}

        with self.assertRaises(ValueError):
            GateIORESTRequest(
                method=RESTMethod.POST,
                endpoint=endpoint,
                params=params,
            )

    def test_data_to_str(self):
        endpoint = CONSTANTS.SYMBOL_PATH_URL
        data = {"one": 1}

        request = GateIORESTRequest(
            method=RESTMethod.POST,
            endpoint=endpoint,
            data=data,
        )

        self.assertIsInstance(request.data, str)
        self.assertEqual(data, json.loads(request.data))

    def test_raises_on_data_supplied_to_non_post_request(self):
        endpoint = CONSTANTS.SYMBOL_PATH_URL
        data = {"one": 1}

        with self.assertRaises(ValueError):
            GateIORESTRequest(
                method=RESTMethod.GET,
                endpoint=endpoint,
                data=data,
            )
