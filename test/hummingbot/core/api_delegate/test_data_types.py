import json
import unittest

from hummingbot.core.api_delegate.data_types import RESTMethod, RESTResponse


class DataTypesTest(unittest.TestCase):
    def test_rest_method_to_str(self):
        method = RESTMethod.GET
        method_str = str(method)

        self.assertEqual("GET", method_str)

    def test_rest_response_body_loading(self):
        body = {"one": 1}
        body_str = json.dumps(body)
        body_bytes = body_str.encode()

        response = RESTResponse(
            url="some/url", method=RESTMethod.GET, status=200, body=body_bytes
        )

        self.assertEqual(body_str, response.text())
        self.assertEqual(body, response.json())
