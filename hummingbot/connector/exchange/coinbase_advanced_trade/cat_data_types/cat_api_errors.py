import functools
import json
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

CAT_ERROR_CODES = {
    "param_required": {"code": 400, "description": "Missing parameter"},
    "validation_error": {"code": 400, "description": "Unable to validate POST/PUT"},
    "invalid_request": {"code": 400, "description": "Invalid request"},
    "personal_details_required": {"code": 400,
                                  "description": "User's personal detail required to complete this request"},
    "identity_verification_required": {"code": 400, "description": "Identity verification is required to complete "
                                                                   "this request"},
    "jumio_verification_required": {"code": 400, "description": "Document verification is required to complete this "
                                                                "request"},
    "jumio_face_match_verification_required": {"code": 400, "description": "Document verification including face "
                                                                           "match is required to complete this "
                                                                           "request"},
    "unverified_email": {"code": 400, "description": "User has not verified their email"},
    "authentication_error": {"code": 401, "description": "Invalid auth (generic)"},
    "invalid_token": {"code": 401, "description": "Invalid Oauth token"},
    "revoked_token": {"code": 401, "description": "Revoked Oauth token"},
    "expired_token": {"code": 401, "description": "Expired Oauth token"},
    "two_factor_required": {"code": 402, "description": "When sending money over 2fa limit"},
    "invalid_scope": {"code": 403, "description": "User hasn't authenticated necessary scope"},
    "not_found": {"code": 404, "description": "Resource not found"},
    "rate_limit_exceeded": {"code": 429, "description": "Rate limit exceeded"},
    "internal_server_error": {"code": 500, "description": "Internal server error"}
}


def cat_raise_exception(api_errors: List["CoinbaseAdvancedTradeAPIError"]):
    """
    Raise exceptions based on the given API errors.

    :param api_errors: A list of CoinbaseAdvancedTradeAPIError objects.
    """
    for error in api_errors:
        if error.code == 400:
            raise CoinbaseATBadRequestError(error)
        elif error.code == 401:
            raise CoinbaseATUnauthorizedError(error)
        elif error.code == 402:
            raise CoinbaseAT2FAError(error)
        elif error.code == 403:
            raise CoinbaseATForbiddenError(error)
        elif error.code == 404:
            raise CoinbaseATNotFoundError(error)
        elif error.code == 429:
            raise CoinbaseATRateLimitExceededError(error)
        elif error.code == 500:
            raise CoinbaseATInternalServerError(error)
        else:
            raise CoinbaseAdvancedTradeAPIException(error)


def cat_parse_error_response(json_input: Union[str, Dict[str, Any]]) -> List["CoinbaseAdvancedTradeAPIError"]:
    """
    Parse the given JSON string into a list of CoinbaseAdvancedTradeAPIError objects.

    :param json_input: A JSON string or a dictionary.
    :return: A list of CoinbaseAdvancedTradeAPIError objects.
    """
    try:
        if isinstance(json_input, str) and json_input:
            json_data = json.loads(json_input)
            return CoinbaseAdvancedTradeAPIError.from_json(json_data)
        elif isinstance(json_input, dict):
            return CoinbaseAdvancedTradeAPIError.from_json(json_input)
    except JSONDecodeError:
        pass

    return []


# Decorator preprocessing the API calls for non-200 requests
def cat_api_call_http_error_handler(coro_func: Callable[..., Coroutine[Any, Any, Dict[str, Any]]]
                                    ) -> Callable[..., Coroutine[Any, Any, Dict[str, Any]]]:
    """
    Decorator preprocessing the API calls for non-200 requests. It checks the response for any errors and raises
    the appropriate exceptions.

    :param coro_func: The coroutine function to be decorated.
    :return: The decorated coroutine function.
    """

    @functools.wraps(coro_func)
    async def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        response: Union[str, Dict[str, Any]] = await coro_func(*args, **kwargs)
        if "errors" in response:
            api_errors: List[CoinbaseAdvancedTradeAPIError] = cat_parse_error_response(response)
            cat_raise_exception(api_errors)
        return response

    return wrapper


@dataclass(frozen=True)
class CoinbaseAdvancedTradeAPIError:
    """
    Represents an error returned by the Coinbase Advanced Trade API.

    :param error_id: The unique identifier of the error.
    :param code: The error code.
    :param message: The error message.
    :param description: A description of the error.
    :param url: The URL associated with the error, if available.
    """
    error_id: str
    code: int
    message: str
    description: str
    url: Optional[str] = None

    @staticmethod
    def from_json(json_data: Dict[str, List[Dict[str, str]]]) -> List["CoinbaseAdvancedTradeAPIError"]:
        """
        Parses a JSON response and creates a list of `CoinbaseAdvancedTradeAPIError` instances.

        :param json_data: The JSON response data.
        :return: A list of `CoinbaseAdvancedTradeAPIError` instances.
        """
        errors: List[CoinbaseAdvancedTradeAPIError] = []
        if 'errors' in json_data:
            for error in json_data['errors']:
                error_id: str = error['id']
                code: int = CAT_ERROR_CODES.get(error_id, {}).get('code', 0)
                message: str = error['message']
                description: str = CAT_ERROR_CODES.get(error_id, {}).get('description', '')
                url: Optional[str] = error.get('url', None)
                errors.append(CoinbaseAdvancedTradeAPIError(error_id, code, message, description, url))
        return errors


# Exception classes that match APIError
class CoinbaseAdvancedTradeAPIException(Exception):
    """
    Exception raised for Coinbase Advanced Trade API errors.

    :param error: The `CoinbaseAdvancedTradeAPIError` instance representing the error.
    """

    def __init__(self, error: CoinbaseAdvancedTradeAPIError):
        self.error: CoinbaseAdvancedTradeAPIError = error
        super().__init__(f"{error.error_id}: {error.message}")


class CoinbaseATBadRequestError(CoinbaseAdvancedTradeAPIException):
    pass


class CoinbaseATUnauthorizedError(CoinbaseAdvancedTradeAPIException):
    pass


class CoinbaseAT2FAError(CoinbaseAdvancedTradeAPIException):
    pass


class CoinbaseATForbiddenError(CoinbaseAdvancedTradeAPIException):
    pass


class CoinbaseATNotFoundError(CoinbaseAdvancedTradeAPIException):
    pass


class CoinbaseATRateLimitExceededError(CoinbaseAdvancedTradeAPIException):
    pass


class CoinbaseATInternalServerError(CoinbaseAdvancedTradeAPIException):
    pass
