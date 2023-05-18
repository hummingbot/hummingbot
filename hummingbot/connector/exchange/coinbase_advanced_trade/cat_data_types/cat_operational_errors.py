import functools
import json
from typing import Any, Callable, Coroutine, Dict, Union

# Order Failure Reasons -> raise an exception
ORDER_FAILURES = {
    "UNKNOWN_FAILURE_REASON": True,
    "UNSUPPORTED_ORDER_CONFIGURATION": True,
    "ORDER_ENTRY_DISABLED": True,
    "INELIGIBLE_PAIR": True,
    "INVALID_REQUEST": True,
    "COMMANDER_REJECTED_NEW_ORDER": True,
    # Warn the user and wait for the condition to resolve itself
    "INVALID_NO_LIQUIDITY": False,
    "INVALID_SIDE": False,
    "INVALID_PRODUCT_ID": False,
    "INVALID_SIZE_PRECISION": False,
    "INVALID_PRICE_PRECISION": False,
    "INVALID_LEDGER_BALANCE": False,
    "INVALID_LIMIT_PRICE_POST_ONLY": False,
    "INVALID_LIMIT_PRICE": False,
    "INSUFFICIENT_FUND": False,
    "INSUFFICIENT_FUNDS": False
}

CANCEL_FAILURES = {
    "UNKNOWN_CANCEL_FAILURE_REASON": True,
    "INVALID_CANCEL_REQUEST": True,
    "COMMANDER_REJECTED_CANCEL_ORDER": True,
    # Warn the user and wait for the condition to resolve itself
    "UNKNOWN_CANCEL_ORDER": False,
    "DUPLICATE_CANCEL_REQUEST": False,
}

UNKNOWN_CANCEL_ORDER = "UNKNOWN_CANCEL_ORDER"


# Decorator to preprocess the operational errors from API calls (200 responses)
def cat_api_call_operational_error_handler(coro_func: Callable[..., Coroutine[Any, Any, Dict[str, Any]]]
                                           ) -> Callable[..., Coroutine[Any, Any, Dict[str, Any]]]:
    """
    Decorator to preprocess the operational errors from API calls.

    :param coro_func: The coroutine to be decorated.
    :return: The decorated coroutine.
    """

    @functools.wraps(coro_func)
    async def wrapper(*args, **kwargs):
        response: Union[str, Dict[str, Any]] = await coro_func(*args, **kwargs)
        if isinstance(response, str):
            if response == "":
                return {}
            response = json.loads(response)

        if isinstance(response, dict):
            if 'success' not in response:
                raise ValueError(f"Invalid Coinbase Advanced Trade API response: {response}")
            if not response['success']:
                failure_reason = response['failure_reason']
                error_response_json = response.get('error_response', '')
                if isinstance(error_response_json, str):
                    error_response_json = json.loads(response['error_response'])
                error_response = CoinbaseAdvancedTradeOperationalError.from_json(error_response_json)
                if ORDER_FAILURES.get(failure_reason, False):
                    raise CoinbaseAdvancedTradeOrderFailureError(failure_reason, error_response)
                elif CANCEL_FAILURES.get(failure_reason, False):
                    raise CoinbaseAdvancedTradeCancelFailureError(failure_reason, error_response)
                else:
                    raise error_response
        return response

    return wrapper


class CoinbaseAdvancedTradeOperationalError(Exception):
    """
    Exception class for operational errors from the Coinbase Advanced Trade API.

    :param error: The error message.
    :param code: The error code.
    :param message: The error description.
    :param details: Additional details about the error.
    """
    error: str
    code: int
    message: str
    details: dict

    def __init__(self, error: str, code: int, message: str, details: Dict[str, Any]):
        self.error = error
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"{error}: {message}")

    @staticmethod
    def from_json(json_data):
        """
        Creates an instance of `CoinbaseAdvancedTradeOperationalError` from JSON data.

        :param json_data: The JSON data representing the error.
        :return: An instance of `CoinbaseAdvancedTradeOperationalError`.
        """
        error = json_data.get('error', "")
        code = json_data.get('code', 0)
        message = json_data.get('message', "")
        details = json_data.get('details', {})
        return CoinbaseAdvancedTradeOperationalError(error, code, message, details)


class CoinbaseAdvancedTradeOrderFailureError(Exception):
    def __init__(self, failure_reason: str, error_response: CoinbaseAdvancedTradeOperationalError):
        self.failure_reason = failure_reason
        self.error_response = error_response
        super().__init__(f"Order failed due to: {failure_reason}. Error details: {error_response.message}")


class CoinbaseAdvancedTradeCancelFailureError(Exception):
    def __init__(self, failure_reason: str, error_response: CoinbaseAdvancedTradeOperationalError):
        self.failure_reason = failure_reason
        self.error_response = error_response
        super().__init__(f"Cancel failed due to: {failure_reason}. Error details: {error_response.message}")
