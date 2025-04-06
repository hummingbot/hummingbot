import itertools
import logging
from typing import (
    Any,
    Callable,
    Dict,
    NoReturn,
    Optional,
)

from eth_typing import (
    ABI,
    ABIFunction,
    HexStr,
    TypeStr,
)
from eth_utils import (
    abi_to_signature,
    filter_abi_by_type,
    function_abi_to_4byte_selector,
    is_0x_prefixed,
    is_binary_address,
    is_boolean,
    is_bytes,
    is_checksum_address,
    is_dict,
    is_hex_address,
    is_integer,
    is_list_like,
    is_string,
)
from eth_utils.curried import (
    apply_formatter_to_array,
)
from eth_utils.hexadecimal import (
    encode_hex,
)
from eth_utils.toolz import (
    compose,
    groupby,
    valfilter,
    valmap,
)

from ens.utils import (
    is_valid_ens_name,
)
from web3._utils.abi import (
    is_address_type,
    is_array_type,
    is_bool_type,
    is_bytes_type,
    is_int_type,
    is_recognized_type,
    is_string_type,
    is_uint_type,
    length_of_array_type,
    sub_type_of_array_type,
)
from web3._utils.formatters import (
    apply_error_formatters,
)
from web3.exceptions import (
    BadResponseFormat,
    InvalidAddress,
    MethodUnavailable,
    RequestTimedOut,
    TransactionNotFound,
    Web3RPCError,
    Web3TypeError,
    Web3ValueError,
)
from web3.types import (
    RPCResponse,
)


def _prepare_selector_collision_msg(duplicates: Dict[HexStr, ABIFunction]) -> str:
    dup_sel = valmap(apply_formatter_to_array(abi_to_signature), duplicates)
    joined_funcs = valmap(lambda funcs: ", ".join(funcs), dup_sel)
    func_sel_msg_list = [
        funcs + " have selector " + sel for sel, funcs in joined_funcs.items()
    ]
    return " and\n".join(func_sel_msg_list)


def validate_abi(abi: ABI) -> None:
    """
    Helper function for validating an ABI
    """
    if not is_list_like(abi):
        raise Web3ValueError("'abi' is not a list")

    if not all(is_dict(e) for e in abi):
        raise Web3ValueError("'abi' is not a list of dictionaries")

    if not all("type" in e for e in abi):
        raise Web3ValueError("'abi' must contain a list of elements each with a type")

    functions = filter_abi_by_type("function", abi)
    selectors = groupby(compose(encode_hex, function_abi_to_4byte_selector), functions)
    duplicates = valfilter(lambda funcs: len(funcs) > 1, selectors)
    if duplicates:
        raise Web3ValueError(
            "Abi contains functions with colliding selectors. "
            f"Functions {_prepare_selector_collision_msg(duplicates)}"
        )


def validate_abi_type(abi_type: TypeStr) -> None:
    """
    Helper function for validating an abi_type
    """
    if not is_recognized_type(abi_type):
        raise Web3ValueError(f"Unrecognized abi_type: {abi_type}")


def validate_abi_value(abi_type: TypeStr, value: Any) -> None:
    """
    Helper function for validating a value against the expected abi_type
    Note: abi_type 'bytes' must either be python3 'bytes' object or ''
    """
    if is_array_type(abi_type) and is_list_like(value):
        # validate length
        specified_length = length_of_array_type(abi_type)
        if specified_length is not None:
            if specified_length < 1:
                raise Web3TypeError(
                    f"Invalid abi-type: {abi_type}. Length of fixed sized "
                    "arrays must be greater than 0."
                )
            if specified_length != len(value):
                raise Web3TypeError(
                    "The following array length does not match the length specified "
                    f"by the abi-type, {abi_type}: {value}"
                )

        # validate sub_types
        sub_type = sub_type_of_array_type(abi_type)
        for v in value:
            validate_abi_value(sub_type, v)
        return
    elif is_bool_type(abi_type) and is_boolean(value):
        return
    elif is_uint_type(abi_type) and is_integer(value) and value >= 0:
        return
    elif is_int_type(abi_type) and is_integer(value):
        return
    elif is_address_type(abi_type):
        validate_address(value)
        return
    elif is_bytes_type(abi_type):
        if is_bytes(value):
            return
        elif is_string(value):
            if is_0x_prefixed(value):
                return
            else:
                raise Web3TypeError(
                    "ABI values of abi-type 'bytes' must be either"
                    "a python3 'bytes' object or an '0x' prefixed string."
                )
    elif is_string_type(abi_type) and is_string(value):
        return

    raise Web3TypeError(f"The following abi value is not a '{abi_type}': {value}")


def is_not_address_string(value: Any) -> bool:
    return (
        is_string(value)
        and not is_bytes(value)
        and not is_checksum_address(value)
        and not is_hex_address(value)
    )


def validate_address(value: Any) -> None:
    """
    Helper function for validating an address
    """
    if is_not_address_string(value):
        if not is_valid_ens_name(value):
            raise InvalidAddress(f"ENS name: '{value}' is invalid.")
        return
    if is_bytes(value):
        if not is_binary_address(value):
            raise InvalidAddress(
                "Address must be 20 bytes when input type is bytes", value
            )
        return

    if not isinstance(value, str):
        raise Web3TypeError(f"Address {value} must be provided as a string")
    if not is_hex_address(value):
        raise InvalidAddress(
            "Address must be 20 bytes, as a hex string with a 0x prefix", value
        )
    if not is_checksum_address(value):
        if value == value.lower():
            raise InvalidAddress(
                "web3.py only accepts checksum addresses. "
                "The software that gave you this non-checksum address should be "
                "considered unsafe, please file it as a bug on their platform. "
                "Try using an ENS name instead. Or, if you must accept lower safety, "
                "use Web3.to_checksum_address(lower_case_address).",
                value,
            )
        else:
            raise InvalidAddress(
                "Address has an invalid EIP-55 checksum. "
                "After looking up the address from the original source, try again.",
                value,
            )


def has_one_val(*args: Any, **kwargs: Any) -> bool:
    vals = itertools.chain(args, kwargs.values())
    not_nones = list(filter(lambda val: val is not None, vals))
    return len(not_nones) == 1


def assert_one_val(*args: Any, **kwargs: Any) -> None:
    if not has_one_val(*args, **kwargs):
        raise Web3TypeError(
            "Exactly one of the passed values can be specified. "
            f"Instead, values were: {args!r}, {kwargs!r}"
        )


# -- RPC Response Validation -- #

KNOWN_REQUEST_TIMEOUT_MESSAGING = {
    # Note: It's important to be very explicit here and not too broad. We don't want
    # to accidentally catch a message that is not for a request timeout. In the worst
    # case, we raise something more generic like `Web3RPCError`. JSON-RPC unfortunately
    # has not standardized error codes for request timeouts.
    "request timed out",  # go-ethereum
}
METHOD_NOT_FOUND = -32601


def _validate_subscription_fields(response: RPCResponse) -> None:
    params = response["params"]
    subscription = params["subscription"]
    if not isinstance(subscription, str) and not len(subscription) == 34:
        _raise_bad_response_format(
            response, "eth_subscription 'params' must include a 'subscription' field."
        )


def _raise_bad_response_format(response: RPCResponse, error: str = "") -> None:
    message = "The response was in an unexpected format and unable to be parsed."
    raw_response = f"The raw response is: {response}"

    if error is not None and error != "":
        error = error[:-1] if error.endswith(".") else error
        message = f"{message} {error}. {raw_response}"
    else:
        message = f"{message} {raw_response}"

    raise BadResponseFormat(message)


def raise_error_for_batch_response(
    response: RPCResponse,
    logger: Optional[logging.Logger] = None,
) -> NoReturn:
    error = response.get("error")
    if error is None:
        _raise_bad_response_format(
            response,
            "Batch response must be formatted as a list of responses or "
            "as a single JSON-RPC error response.",
        )
    validate_rpc_response_and_raise_if_error(
        response,
        None,
        is_subscription_response=False,
        logger=logger,
        params=[],
    )
    # This should not be reached, but if it is, raise a generic `BadResponseFormat`
    raise BadResponseFormat(
        "Batch response was in an unexpected format and unable to be parsed."
    )


def validate_rpc_response_and_raise_if_error(
    response: RPCResponse,
    error_formatters: Optional[Callable[..., Any]],
    is_subscription_response: bool = False,
    logger: Optional[logging.Logger] = None,
    params: Optional[Any] = None,
) -> None:
    if "jsonrpc" not in response or response["jsonrpc"] != "2.0":
        _raise_bad_response_format(
            response, 'The "jsonrpc" field must be present with a value of "2.0".'
        )

    response_id = response.get("id")
    if "id" in response:
        int_error_msg = (
            '"id" must be an integer or a string representation of an integer.'
        )
        if response_id is None and "error" in response:
            # errors can sometimes have null `id`, according to the JSON-RPC spec
            pass
        elif not isinstance(response_id, (str, int)):
            _raise_bad_response_format(response, int_error_msg)
        elif isinstance(response_id, str):
            try:
                int(response_id)
            except ValueError:
                _raise_bad_response_format(response, int_error_msg)
    elif is_subscription_response:
        # if `id` is not present, this must be a subscription response
        _validate_subscription_fields(response)
    else:
        _raise_bad_response_format(
            response,
            'Response must include an "id" field or be formatted as an '
            "`eth_subscription` response.",
        )

    if all(key in response for key in {"error", "result"}):
        _raise_bad_response_format(
            response, 'Response cannot include both "error" and "result".'
        )
    elif (
        not any(key in response for key in {"error", "result"})
        and not is_subscription_response
    ):
        _raise_bad_response_format(
            response, 'Response must include either "error" or "result".'
        )
    elif "error" in response:
        web3_rpc_error: Optional[Web3RPCError] = None
        error = response["error"]

        # raise the error when the value is a string
        if error is None or not isinstance(error, dict):
            _raise_bad_response_format(
                response,
                'response["error"] must be a valid object as defined by the '
                "JSON-RPC 2.0 specification.",
            )

        # errors must include a message
        error_message = error.get("message")
        if not isinstance(error_message, str):
            _raise_bad_response_format(
                response, 'error["message"] is required and must be a string value.'
            )
        elif error_message == "transaction not found":
            transaction_hash = params[0]
            web3_rpc_error = TransactionNotFound(
                repr(error),
                rpc_response=response,
                user_message=(f"Transaction with hash {transaction_hash!r} not found."),
            )

        # errors must include an integer code
        code = error.get("code")
        if not isinstance(code, int):
            _raise_bad_response_format(
                response, 'error["code"] is required and must be an integer value.'
            )
        elif code == METHOD_NOT_FOUND:
            web3_rpc_error = MethodUnavailable(
                repr(error),
                rpc_response=response,
                user_message=(
                    "This method is not available. Check your node provider or your "
                    "client's API docs to see what methods are supported and / or "
                    "currently enabled."
                ),
            )
        elif any(
            # parse specific timeout messages
            timeout_str in error_message.lower()
            for timeout_str in KNOWN_REQUEST_TIMEOUT_MESSAGING
        ):
            web3_rpc_error = RequestTimedOut(
                repr(error),
                rpc_response=response,
                user_message=(
                    "The request timed out. Check the connection to your node and "
                    "try again."
                ),
            )

        if web3_rpc_error is None:
            # if no condition was met above, raise a more generic `Web3RPCError`
            web3_rpc_error = Web3RPCError(repr(error), rpc_response=response)

        response = apply_error_formatters(error_formatters, response)
        if logger is not None:
            logger.debug(f"RPC error response: {response}")

        raise web3_rpc_error

    elif "result" not in response and not is_subscription_response:
        _raise_bad_response_format(response)
