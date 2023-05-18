import asyncio
import json
import unittest
from typing import Any, Dict

import aiohttp
from aioresponses import aioresponses

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_errors import (
    CoinbaseAdvancedTradeAPIError,
    CoinbaseAdvancedTradeAPIException,
    CoinbaseAT2FAError,
    CoinbaseATBadRequestError,
    CoinbaseATForbiddenError,
    CoinbaseATInternalServerError,
    CoinbaseATNotFoundError,
    CoinbaseATRateLimitExceededError,
    CoinbaseATUnauthorizedError,
    cat_api_call_http_error_handler,
    cat_parse_error_response,
    cat_raise_exception,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant


class TestCoinbaseAdvancedTradeErrors(unittest.TestCase):
    def setUp(self):
        self.sample_error_data = [
            {"id": "param_required", "code": 400, "description": "Missing parameter"},
            {"id": "validation_error", "code": 400, "description": "Unable to validate POST/PUT"},
            {"id": "invalid_request", "code": 400, "description": "Invalid request"},
            {"id": "personal_details_required", "code": 400, "description": "User's personal detail required to "
                                                                            "complete this request"},
            {"id": "identity_verification_required", "code": 400, "description": "Identity verification is required "
                                                                                 "to complete this request"},
            {"id": "jumio_verification_required", "code": 400, "description": "Document verification is required to "
                                                                              "complete this request"},
            {"id": "jumio_face_match_verification_required", "code": 400, "description": "Document verification "
                                                                                         "including face match is "
                                                                                         "required to complete this "
                                                                                         "request"},
            {"id": "unverified_email", "code": 400, "description": "User has not verified their email"},
            {"id": "authentication_error", "code": 401, "description": "Invalid auth (generic)"},
            {"id": "two_factor_required", "code": 402, "description": "When sending money over 2fa limit"},
            {"id": "invalid_token", "code": 401, "description": "Invalid Oauth token"},
            {"id": "revoked_token", "code": 401, "description": "Revoked Oauth token"},
            {"id": "expired_token", "code": 401, "description": "Expired Oauth token"},
            {"id": "invalid_scope", "code": 403, "description": "User hasn't authenticated necessary scope"},
            {"id": "not_found", "code": 404, "description": "Resource not found"},
            {"id": "rate_limit_exceeded", "code": 429, "description": "Rate limit exceeded"},
            {"id": "internal_server_error", "code": 500, "description": "Internal server error"}
        ]

    @aioresponses()
    @cat_api_call_http_error_handler
    async def simplified_decorated_execute_request(self, mocked: aioresponses, error_json: Dict[str, Any]):
        url = "https://test.com"

        # Mock the response from the server
        mocked.get(url, status=400, payload=error_json)

        # Setup RESTAssistant
        connection = RESTConnection(aiohttp.ClientSession())
        assistant = RESTAssistant(
            connection=connection,
            throttler=AsyncThrottler(rate_limits=[]),
        )

        # Simplified execute_request
        request = RESTRequest(
            method=RESTMethod.GET,
            url=url,
        )
        response = await assistant.call(request=request, timeout=None)

        if 400 <= response.status:
            error_response = await response.json()
            return error_response
        result = await response.json()
        return result

    def test_parse_error_response_normal(self):
        for error in self.sample_error_data:
            error_json = json.dumps({"errors": [{"id": error["id"], "message": "Error message"}]})
            errors = cat_parse_error_response(error_json)

            self.assertEqual(1, len(errors))
            self.assertEqual(error["id"], errors[0].error_id)
            self.assertEqual(error["code"], errors[0].code)
            self.assertEqual(error["description"], errors[0].description)

    def test_parse_error_response_multiple(self):
        error_json = json.dumps({"errors": [{"id": "error1", "message": "Error message 1"},
                                            {"id": "error2", "message": "Error message 2"}]})
        errors = cat_parse_error_response(error_json)

        self.assertEqual(2, len(errors))
        self.assertEqual("error1", errors[0].error_id)
        self.assertEqual("error2", errors[1].error_id)

    def test_parse_error_response_no_json(self):
        errors = cat_parse_error_response("")
        self.assertEqual(0, len(errors))

    def test_parse_error_response(self):
        # Test with well-formed error JSON.
        for error in self.sample_error_data:
            error_json = json.dumps({"errors": [{"id": error["id"], "message": "Error message"}]})
            errors = cat_parse_error_response(error_json)
            self.assertEqual(1, len(errors))
            self.assertEqual(error["id"], errors[0].error_id)
            self.assertEqual(error["code"], errors[0].code)
            self.assertEqual(error["description"], errors[0].description)

        # Test with malformed error JSON.
        malformed_error_json = json.dumps({"errors": [{"id": "unknown", "message": "Error message"}]})
        errors = cat_parse_error_response(malformed_error_json)
        self.assertEqual(1, len(errors))
        self.assertEqual("unknown", errors[0].error_id)
        self.assertEqual(0, errors[0].code)  # Default value when error code is not found.
        self.assertEqual("", errors[0].description)  # Default value when description is not found.

        # Test with no errors in JSON.
        no_error_json = json.dumps({"errors": []})
        errors = cat_parse_error_response(no_error_json)
        self.assertEqual(0, len(errors))

        # Test with JSON without 'errors' key.
        no_errors_key_json = json.dumps({"message": "No errors here"})
        errors = cat_parse_error_response(no_errors_key_json)
        self.assertEqual(0, len(errors))

    def test_parse_error_response_with_dict(self):
        test_dict: Dict[str, Any] = {"errors": [{"id": "400", "message": "Bad request"}]}
        result = cat_parse_error_response(test_dict)
        self.assertIsInstance(result[0], CoinbaseAdvancedTradeAPIError)
        self.assertEqual(result[0].message, "Bad request")

    def test_parse_error_response_with_json_string(self):
        test_str = '{"errors": [{"id": "400", "message": "Bad request"}]}'
        result = cat_parse_error_response(test_str)
        self.assertIsInstance(result[0], CoinbaseAdvancedTradeAPIError)
        self.assertEqual(result[0].message, "Bad request")

    def test_parse_error_response_with_empty_string(self):
        test_str = ""
        result = cat_parse_error_response(test_str)
        self.assertEqual(result, [])

    def test_parse_error_response_with_non_json_string(self):
        test_str = "This is not a JSON string."
        result = cat_parse_error_response(test_str)
        self.assertEqual(result, [])

    def test_raise_exception(self):
        exception_map = {
            400: CoinbaseATBadRequestError,
            401: CoinbaseATUnauthorizedError,
            402: CoinbaseAT2FAError,
            403: CoinbaseATForbiddenError,
            404: CoinbaseATNotFoundError,
            429: CoinbaseATRateLimitExceededError,
            500: CoinbaseATInternalServerError
        }

        for error in self.sample_error_data:
            error_json = json.dumps({"errors": [{"id": error["id"], "message": "Error message"}]})
            errors = cat_parse_error_response(error_json)

            with self.assertRaises(exception_map[error["code"]]) as cm:
                cat_raise_exception(errors)

            self.assertEqual(error["id"], cm.exception.error.error_id)
            self.assertEqual(error["code"], cm.exception.error.code)

    def test_coinbase_advanced_trade_api_error(self):
        error_json = json.dumps({"errors": [{"id": "invalid_request", "message": "Error message"}]})
        errors = cat_parse_error_response(error_json)
        error = errors[0]

        self.assertEqual("invalid_request", error.error_id)
        self.assertEqual(400, error.code)
        self.assertEqual("Invalid request", error.description)
        self.assertIsNone(error.url)

    def test_coinbase_advanced_trade_api_exception(self):
        error_json = json.dumps({"errors": [{"id": "invalid_request", "message": "Error message"}]})
        errors = cat_parse_error_response(error_json)
        error = errors[0]
        exception = CoinbaseAdvancedTradeAPIException(error)

        self.assertEqual(error, exception.error)
        self.assertEqual("invalid_request: Error message", str(exception))

    def test_rest_assistant_with_error_response(self):
        error_map = {
            400: CoinbaseATBadRequestError,
            401: CoinbaseATUnauthorizedError,
            402: CoinbaseAT2FAError,
            403: CoinbaseATForbiddenError,
            404: CoinbaseATNotFoundError,
            429: CoinbaseATRateLimitExceededError,
            500: CoinbaseATInternalServerError,
        }
        for error in self.sample_error_data:
            # When the response is an error response, the RESTAssistant should pass the error message.
            error_json = json.dumps({"errors": [{"id": error["id"], "message": "Error message"}]})
            expected_error = error_map.get(error["code"], CoinbaseAdvancedTradeAPIException)
            with self.assertRaises(expected_error) as cm:
                # When the error message is received, the decorator intercept and raises the appropriate Exception
                asyncio.run(self.simplified_decorated_execute_request(error_json=error_json))
            self.assertEqual(f'{error["id"]}: Error message', cm.exception.args[0])


if __name__ == '__main__':
    unittest.main()
