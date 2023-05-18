import asyncio
import json
import unittest

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_operational_errors import (
    CoinbaseAdvancedTradeCancelFailureError,
    CoinbaseAdvancedTradeOperationalError,
    CoinbaseAdvancedTradeOrderFailureError,
    cat_api_call_operational_error_handler,
)


class TestCoinbaseAdvancedTradeAPIErrors(unittest.TestCase):
    async def async_test_func(self):
        return {"success": True}

    @cat_api_call_operational_error_handler
    async def decorated_async_test_func(self):
        return {"success": True}

    @cat_api_call_operational_error_handler
    async def decorated_async_test_func_with_failure(self):
        return {"success": False, "failure_reason": "INVALID_REQUEST", "error_response": json.dumps(
            {"error": "invalid_request", "code": 400, "message": "Invalid request", "details": {}})}

    def test_cat_api_call_operational_error_handler(self):
        # Test when the decorated function returns a successful response
        response = asyncio.run(self.decorated_async_test_func())
        self.assertEqual(response, {"success": True})

        # Test when the decorated function returns a failure response
        with self.assertRaises(CoinbaseAdvancedTradeOrderFailureError):
            asyncio.run(self.decorated_async_test_func_with_failure())

    def test_coinbase_advanced_trade_operational_error(self):
        # Test instantiation of CoinbaseAdvancedTradeOperationalError
        error = CoinbaseAdvancedTradeOperationalError("invalid_request", 400, "Invalid request", {})
        self.assertEqual(error.error, "invalid_request")
        self.assertEqual(error.code, 400)
        self.assertEqual(error.message, "Invalid request")
        self.assertEqual(error.details, {})

        # Test from_json method
        error = CoinbaseAdvancedTradeOperationalError.from_json(
            {"error": "invalid_request", "code": 400, "message": "Invalid request", "details": {}})
        self.assertEqual(error.error, "invalid_request")
        self.assertEqual(error.code, 400)
        self.assertEqual(error.message, "Invalid request")
        self.assertEqual(error.details, {})

    def test_coinbase_advanced_trade_order_failure_error(self):
        # Test instantiation of CoinbaseAdvancedTradeOrderFailureError
        operational_error = CoinbaseAdvancedTradeOperationalError("invalid_request", 400, "Invalid request", {})
        error = CoinbaseAdvancedTradeOrderFailureError("Invalid request", operational_error)
        self.assertEqual(error.failure_reason, "Invalid request")
        self.assertEqual(error.error_response, operational_error)

    def test_coinbase_advanced_trade_cancel_failure_error(self):
        # Test instantiation of CoinbaseAdvancedTradeCancelFailureError
        operational_error = CoinbaseAdvancedTradeOperationalError("invalid_request", 400, "Invalid request", {})
        error = CoinbaseAdvancedTradeCancelFailureError("Invalid request", operational_error)
        self.assertEqual(error.failure_reason, "Invalid request")
        self.assertEqual(error.error_response, operational_error)

    @cat_api_call_operational_error_handler
    async def decorated_async_test_func_with_unknown_failure(self):
        return {"success": False, "failure_reason": "UNKNOWN_FAILURE_REASON", "error_response": json.dumps(
            {"error": "unknown_failure", "code": 999, "message": "Unknown failure", "details": {}})}

    @cat_api_call_operational_error_handler
    async def decorated_async_test_func_with_invalid_response(self):
        return {"invalid_response": True}

    def test_cat_api_call_operational_error_handler_corner_cases(self):
        # Test when the decorated function returns a failure response with an unknown failure reason
        with self.assertRaises(CoinbaseAdvancedTradeOrderFailureError):
            asyncio.run(self.decorated_async_test_func_with_unknown_failure())

        # Test when the decorated function returns an invalid response
        with self.assertRaises(ValueError):
            asyncio.run(self.decorated_async_test_func_with_invalid_response())

    def test_coinbase_advanced_trade_operational_error_from_json_corner_cases(self):
        # Test instantiation from JSON with missing fields
        error = CoinbaseAdvancedTradeOperationalError.from_json(
            {"error": "invalid_request", "message": "Invalid request", "details": {}})
        self.assertEqual(error.error, "invalid_request")
        self.assertEqual(error.code, 0)  # default value
        self.assertEqual(error.message, "Invalid request")
        self.assertEqual(error.details, {})

        # Test instantiation from JSON with extra fields
        error = CoinbaseAdvancedTradeOperationalError.from_json(
            {"error": "invalid_request", "code": 400, "message": "Invalid request", "details": {},
             "extra_field": "extra_value"})
        self.assertEqual(error.error, "invalid_request")
        self.assertEqual(error.code, 400)
        self.assertEqual(error.message, "Invalid request")
        self.assertEqual(error.details, {})


if __name__ == '__main__':
    unittest.main()
