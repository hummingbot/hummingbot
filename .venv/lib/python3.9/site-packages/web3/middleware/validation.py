from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
)

from eth_utils.curried import (
    apply_formatter_at_index,
    apply_formatter_if,
    apply_formatters_to_dict,
    is_null,
    is_string,
)
from eth_utils.toolz import (
    complement,
    compose,
    curry,
    dissoc,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.formatters import (
    hex_to_integer,
)
from web3._utils.rpc_abi import (
    RPC,
)
from web3.exceptions import (
    ExtraDataLengthError,
    Web3ValidationError,
)
from web3.middleware.formatting import (
    FormattingMiddlewareBuilder,
)
from web3.types import (
    Formatters,
    FormattersDict,
    RPCEndpoint,
    TxParams,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )

MAX_EXTRADATA_LENGTH = 32

is_not_null = complement(is_null)
to_integer_if_hex = apply_formatter_if(is_string, hex_to_integer)


@curry
def _validate_chain_id(web3_chain_id: int, chain_id: int) -> int:
    chain_id_int = to_integer_if_hex(chain_id)
    if chain_id_int == web3_chain_id:
        return chain_id
    else:
        raise Web3ValidationError(
            f"The transaction declared chain ID {chain_id_int!r}, "
            f"but the connected node is on {web3_chain_id!r}"
        )


def _check_extradata_length(val: Any) -> Any:
    if not isinstance(val, (str, int, bytes)):
        return val
    result = HexBytes(val)
    if len(result) > MAX_EXTRADATA_LENGTH:
        raise ExtraDataLengthError(
            f"The field extraData is {len(result)} bytes, but should be "
            f"{MAX_EXTRADATA_LENGTH}. It is quite likely that you are "
            "connected to a POA chain. Refer to "
            "http://web3py.readthedocs.io/en/stable/middleware.html#proof-of-authority "
            f"for more details. The full extraData is: {result!r}"
        )
    return val


def _transaction_normalizer(transaction: TxParams) -> TxParams:
    return dissoc(transaction, "chainId")


def _transaction_param_validator(web3_chain_id: int) -> Callable[..., Any]:
    transactions_params_validators = {
        "chainId": apply_formatter_if(
            # Bypass `validate_chain_id` if chainId can't be determined
            lambda _: is_not_null(web3_chain_id),
            _validate_chain_id(web3_chain_id),
        ),
    }
    return apply_formatter_at_index(
        apply_formatters_to_dict(transactions_params_validators), 0
    )


BLOCK_VALIDATORS = {
    "extraData": _check_extradata_length,
}
block_validator = apply_formatter_if(
    is_not_null, apply_formatters_to_dict(BLOCK_VALIDATORS)
)

METHODS_TO_VALIDATE = [
    RPC.eth_sendTransaction,
    RPC.eth_estimateGas,
    RPC.eth_call,
    RPC.eth_createAccessList,
]


def _chain_id_validator(web3_chain_id: int) -> Callable[..., Any]:
    return compose(
        apply_formatter_at_index(_transaction_normalizer, 0),
        _transaction_param_validator(web3_chain_id),
    )


def _build_formatters_dict(
    request_formatters: Dict[RPCEndpoint, Any]
) -> FormattersDict:
    return dict(
        request_formatters=request_formatters,
        result_formatters={
            RPC.eth_getBlockByHash: block_validator,
            RPC.eth_getBlockByNumber: block_validator,
        },
    )


# -- sync -- #


def build_method_validators(w3: "Web3", method: RPCEndpoint) -> FormattersDict:
    request_formatters = {}
    if RPCEndpoint(method) in METHODS_TO_VALIDATE:
        w3_chain_id = w3.eth.chain_id
        for method in METHODS_TO_VALIDATE:
            request_formatters[method] = _chain_id_validator(w3_chain_id)

    return _build_formatters_dict(request_formatters)


# -- async --- #


async def async_build_method_validators(
    async_w3: "AsyncWeb3", method: RPCEndpoint
) -> FormattersDict:
    request_formatters: Formatters = {}
    if RPCEndpoint(method) in METHODS_TO_VALIDATE:
        w3_chain_id = await async_w3.eth.chain_id
        for method in METHODS_TO_VALIDATE:
            request_formatters[method] = _chain_id_validator(w3_chain_id)

    return _build_formatters_dict(request_formatters)


ValidationMiddleware = FormattingMiddlewareBuilder.build(
    sync_formatters_builder=build_method_validators,
    async_formatters_builder=async_build_method_validators,
)
