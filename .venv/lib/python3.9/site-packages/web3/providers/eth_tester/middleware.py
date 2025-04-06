import operator
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Optional,
)

from eth_typing import (
    ChecksumAddress,
)
from eth_utils import (
    is_dict,
    is_hex,
    is_string,
)
from eth_utils.curried import (
    apply_formatter_if,
    apply_formatters_to_dict,
)
from eth_utils.toolz import (
    assoc,
    complement,
    compose,
    curry,
    identity,
    partial,
    pipe,
)

from web3._utils.formatters import (
    apply_formatters_to_args,
    apply_key_map,
    hex_to_integer,
    integer_to_hex,
    is_array_of_dicts,
    static_return,
)
from web3._utils.method_formatters import (
    apply_list_to_array_formatter,
)
from web3.middleware.base import (
    Web3Middleware,
)
from web3.middleware.formatting import (
    FormattingMiddlewareBuilder,
)
from web3.types import (
    RPCEndpoint,
    TxParams,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )


def is_named_block(value: Any) -> bool:
    return value in {"latest", "earliest", "safe", "finalized"}


def is_hexstr(value: Any) -> bool:
    return is_string(value) and is_hex(value)


to_integer_if_hex = apply_formatter_if(is_hexstr, hex_to_integer)
is_not_named_block = complement(is_named_block)

# --- Request Mapping --- #

TRANSACTION_REQUEST_KEY_MAPPING = {
    "blobVersionedHashes": "blob_versioned_hashes",
    "gasPrice": "gas_price",
    "maxFeePerBlobGas": "max_fee_per_blob_gas",
    "maxFeePerGas": "max_fee_per_gas",
    "maxPriorityFeePerGas": "max_priority_fee_per_gas",
    "accessList": "access_list",
    "chainId": "chain_id",
}
transaction_request_remapper = apply_key_map(TRANSACTION_REQUEST_KEY_MAPPING)


TRANSACTION_REQUEST_FORMATTERS = {
    "chainId": to_integer_if_hex,
    "gas": to_integer_if_hex,
    "gasPrice": to_integer_if_hex,
    "value": to_integer_if_hex,
    "nonce": to_integer_if_hex,
    "maxFeePerGas": to_integer_if_hex,
    "maxPriorityFeePerGas": to_integer_if_hex,
    "accessList": apply_list_to_array_formatter(
        apply_key_map({"storageKeys": "storage_keys"})
    ),
}
transaction_request_formatter = apply_formatters_to_dict(TRANSACTION_REQUEST_FORMATTERS)

transaction_request_transformer = compose(
    transaction_request_remapper,
    transaction_request_formatter,
)

FILTER_REQUEST_KEY_MAPPING = {
    "fromBlock": "from_block",
    "toBlock": "to_block",
}
filter_request_remapper = apply_key_map(FILTER_REQUEST_KEY_MAPPING)


FILTER_REQUEST_FORMATTERS = {
    "from_block": to_integer_if_hex,
    "to_block": to_integer_if_hex,
}
filter_request_formatter = apply_formatters_to_dict(FILTER_REQUEST_FORMATTERS)

filter_request_transformer = compose(
    filter_request_formatter,
    filter_request_remapper,
)


# --- Result Mapping --- #

TRANSACTION_RESULT_KEY_MAPPING = {
    "access_list": "accessList",
    "blob_versioned_hashes": "blobVersionedHashes",
    "block_hash": "blockHash",
    "block_number": "blockNumber",
    "chain_id": "chainId",
    "gas_price": "gasPrice",
    "max_fee_per_blob_gas": "maxFeePerBlobGas",
    "max_fee_per_gas": "maxFeePerGas",
    "max_priority_fee_per_gas": "maxPriorityFeePerGas",
    "transaction_hash": "transactionHash",
    "transaction_index": "transactionIndex",
    "data": "input",
}
transaction_result_remapper = apply_key_map(TRANSACTION_RESULT_KEY_MAPPING)


TRANSACTION_RESULT_FORMATTERS = {
    "to": apply_formatter_if(partial(operator.eq, ""), static_return(None)),
    "access_list": apply_list_to_array_formatter(
        apply_key_map({"storage_keys": "storageKeys"}),
    ),
}
transaction_result_formatter = apply_formatters_to_dict(TRANSACTION_RESULT_FORMATTERS)


LOG_RESULT_KEY_MAPPING = {
    "log_index": "logIndex",
    "transaction_index": "transactionIndex",
    "transaction_hash": "transactionHash",
    "block_hash": "blockHash",
    "block_number": "blockNumber",
}
log_result_remapper = apply_key_map(LOG_RESULT_KEY_MAPPING)


RECEIPT_RESULT_KEY_MAPPING = {
    "block_hash": "blockHash",
    "block_number": "blockNumber",
    "contract_address": "contractAddress",
    "gas_used": "gasUsed",
    "cumulative_gas_used": "cumulativeGasUsed",
    "effective_gas_price": "effectiveGasPrice",
    "transaction_hash": "transactionHash",
    "transaction_index": "transactionIndex",
    "blob_gas_used": "blobGasUsed",
    "blob_gas_price": "blobGasPrice",
}
receipt_result_remapper = apply_key_map(RECEIPT_RESULT_KEY_MAPPING)


BLOCK_RESULT_KEY_MAPPING = {
    "gas_limit": "gasLimit",
    "sha3_uncles": "sha3Uncles",
    "transactions_root": "transactionsRoot",
    "parent_hash": "parentHash",
    "logs_bloom": "logsBloom",
    "state_root": "stateRoot",
    "receipts_root": "receiptsRoot",
    "total_difficulty": "totalDifficulty",
    "extra_data": "extraData",
    "gas_used": "gasUsed",
    "base_fee_per_gas": "baseFeePerGas",
    "mix_hash": "mixHash",
    # eth-tester changed the miner key to coinbase since
    # there is no longer any mining happening, but the current
    # JSON-RPC spec still says miner
    "coinbase": "miner",
    "withdrawals_root": "withdrawalsRoot",
    "parent_beacon_block_root": "parentBeaconBlockRoot",
    "blob_gas_used": "blobGasUsed",
    "excess_blob_gas": "excessBlobGas",
}
block_result_remapper = apply_key_map(BLOCK_RESULT_KEY_MAPPING)

BLOCK_RESULT_FORMATTERS = {
    "withdrawals": apply_list_to_array_formatter(
        apply_key_map({"validator_index": "validatorIndex"}),
    ),
}
block_result_formatter = apply_formatters_to_dict(BLOCK_RESULT_FORMATTERS)


RECEIPT_RESULT_FORMATTERS = {
    "logs": apply_list_to_array_formatter(log_result_remapper),
}
receipt_result_formatter = apply_formatters_to_dict(RECEIPT_RESULT_FORMATTERS)


fee_history_result_remapper = apply_key_map(
    {
        "oldest_block": "oldestBlock",
        "base_fee_per_gas": "baseFeePerGas",
        "gas_used_ratio": "gasUsedRatio",
    }
)


request_formatters = {
    # Eth
    RPCEndpoint("eth_getBlockByNumber"): apply_formatters_to_args(
        apply_formatter_if(is_not_named_block, to_integer_if_hex),
    ),
    RPCEndpoint("eth_getFilterChanges"): apply_formatters_to_args(hex_to_integer),
    RPCEndpoint("eth_getFilterLogs"): apply_formatters_to_args(hex_to_integer),
    RPCEndpoint("eth_getTransactionCount"): apply_formatters_to_args(
        identity,
        apply_formatter_if(is_not_named_block, to_integer_if_hex),
    ),
    RPCEndpoint("eth_getBlockTransactionCountByNumber"): apply_formatters_to_args(
        apply_formatter_if(is_not_named_block, to_integer_if_hex),
    ),
    RPCEndpoint("eth_getUncleCountByBlockNumber"): apply_formatters_to_args(
        apply_formatter_if(is_not_named_block, to_integer_if_hex),
    ),
    RPCEndpoint("eth_getTransactionByBlockHashAndIndex"): apply_formatters_to_args(
        identity,
        to_integer_if_hex,
    ),
    RPCEndpoint("eth_getTransactionByBlockNumberAndIndex"): apply_formatters_to_args(
        apply_formatter_if(is_not_named_block, to_integer_if_hex),
        to_integer_if_hex,
    ),
    RPCEndpoint("eth_getUncleByBlockNumberAndIndex"): apply_formatters_to_args(
        apply_formatter_if(is_not_named_block, to_integer_if_hex),
        to_integer_if_hex,
    ),
    RPCEndpoint("eth_newFilter"): apply_formatters_to_args(
        filter_request_transformer,
    ),
    RPCEndpoint("eth_getLogs"): apply_formatters_to_args(
        filter_request_transformer,
    ),
    RPCEndpoint("eth_sendTransaction"): apply_formatters_to_args(
        transaction_request_transformer,
    ),
    RPCEndpoint("eth_estimateGas"): apply_formatters_to_args(
        transaction_request_transformer,
    ),
    RPCEndpoint("eth_call"): apply_formatters_to_args(
        transaction_request_transformer,
        apply_formatter_if(is_not_named_block, to_integer_if_hex),
    ),
    RPCEndpoint("eth_createAccessList"): apply_formatters_to_args(
        transaction_request_transformer,
        apply_formatter_if(is_not_named_block, to_integer_if_hex),
    ),
    RPCEndpoint("eth_uninstallFilter"): apply_formatters_to_args(hex_to_integer),
    RPCEndpoint("eth_getCode"): apply_formatters_to_args(
        identity,
        apply_formatter_if(is_not_named_block, to_integer_if_hex),
    ),
    RPCEndpoint("eth_getBalance"): apply_formatters_to_args(
        identity,
        apply_formatter_if(is_not_named_block, to_integer_if_hex),
    ),
    RPCEndpoint("eth_feeHistory"): apply_formatters_to_args(
        to_integer_if_hex,
        apply_formatter_if(is_not_named_block, to_integer_if_hex),
    ),
    # EVM
    RPCEndpoint("evm_revert"): apply_formatters_to_args(hex_to_integer),
}

result_formatters: Optional[Dict[RPCEndpoint, Callable[..., Any]]] = {
    RPCEndpoint("eth_getBlockByHash"): apply_formatter_if(
        is_dict, compose(block_result_remapper, block_result_formatter)
    ),
    RPCEndpoint("eth_getBlockByNumber"): apply_formatter_if(
        is_dict, compose(block_result_remapper, block_result_formatter)
    ),
    RPCEndpoint("eth_getBlockTransactionCountByHash"): apply_formatter_if(
        is_dict,
        transaction_result_remapper,
    ),
    RPCEndpoint("eth_getBlockTransactionCountByNumber"): apply_formatter_if(
        is_dict,
        transaction_result_remapper,
    ),
    RPCEndpoint("eth_getTransactionByHash"): apply_formatter_if(
        is_dict,
        compose(transaction_result_remapper, transaction_result_formatter),
    ),
    RPCEndpoint("eth_getTransactionReceipt"): apply_formatter_if(
        is_dict,
        compose(receipt_result_remapper, receipt_result_formatter),
    ),
    RPCEndpoint("eth_newFilter"): integer_to_hex,
    RPCEndpoint("eth_newBlockFilter"): integer_to_hex,
    RPCEndpoint("eth_newPendingTransactionFilter"): integer_to_hex,
    RPCEndpoint("eth_getLogs"): apply_formatter_if(
        is_array_of_dicts,
        apply_list_to_array_formatter(log_result_remapper),
    ),
    RPCEndpoint("eth_getFilterChanges"): apply_formatter_if(
        is_array_of_dicts,
        apply_list_to_array_formatter(log_result_remapper),
    ),
    RPCEndpoint("eth_getFilterLogs"): apply_formatter_if(
        is_array_of_dicts,
        apply_list_to_array_formatter(log_result_remapper),
    ),
    RPCEndpoint("eth_feeHistory"): apply_formatter_if(
        is_dict, fee_history_result_remapper
    ),
    # EVM
    RPCEndpoint("evm_snapshot"): integer_to_hex,
}


def guess_from(w3: "Web3", _: TxParams) -> ChecksumAddress:
    if w3.eth.accounts and len(w3.eth.accounts) > 0:
        return w3.eth.accounts[0]

    return None


@curry
def fill_default(
    field: str, guess_func: Callable[..., Any], w3: "Web3", transaction: TxParams
) -> TxParams:
    # type ignored b/c TxParams keys must be string literal types
    if field in transaction and transaction[field] is not None:  # type: ignore
        return transaction
    else:
        guess_val = guess_func(w3, transaction)
        return assoc(transaction, field, guess_val)


# --- async --- #


async def async_guess_from(
    async_w3: "AsyncWeb3", _: TxParams
) -> Optional[ChecksumAddress]:
    accounts = await async_w3.eth.accounts
    if accounts is not None and len(accounts) > 0:
        return accounts[0]
    return None


@curry
async def async_fill_default(
    field: str,
    guess_func: Callable[..., Any],
    async_w3: "AsyncWeb3",
    transaction: TxParams,
) -> TxParams:
    # type ignored b/c TxParams keys must be string literal types
    if field in transaction and transaction[field] is not None:  # type: ignore
        return transaction
    else:
        guess_val = await guess_func(async_w3, transaction)
        return assoc(transaction, field, guess_val)


# --- define middleware --- #


class DefaultTransactionFieldsMiddleware(Web3Middleware):
    def request_processor(self, method: "RPCEndpoint", params: Any) -> Any:
        if method in (
            "eth_call",
            "eth_estimateGas",
            "eth_sendTransaction",
            "eth_createAccessList",
        ):
            fill_default_from = fill_default("from", guess_from, self._w3)
            filled_transaction = pipe(
                params[0],
                fill_default_from,
            )
            params = [filled_transaction] + list(params)[1:]
        return method, params

    # --- async --- #

    async def async_request_processor(self, method: "RPCEndpoint", params: Any) -> Any:
        if method in (
            "eth_call",
            "eth_estimateGas",
            "eth_sendTransaction",
            "eth_createAccessList",
        ):
            filled_transaction = await async_fill_default(
                "from", async_guess_from, self._w3, params[0]
            )
            params = [filled_transaction] + list(params)[1:]

        return method, params


ethereum_tester_middleware = FormattingMiddlewareBuilder.build(
    request_formatters=request_formatters, result_formatters=result_formatters
)
default_transaction_fields_middleware = DefaultTransactionFieldsMiddleware
