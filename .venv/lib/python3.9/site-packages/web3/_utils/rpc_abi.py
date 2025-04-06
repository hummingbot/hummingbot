from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Sequence,
    Tuple,
    Union,
)

from eth_typing import (
    TypeStr,
)
from eth_utils import (
    to_dict,
)
from eth_utils.curried import (
    apply_formatter_at_index,
)
from eth_utils.toolz import (
    curry,
)

from web3._utils.abi import (
    map_abi_data,
)
from web3.exceptions import (
    Web3TypeError,
)
from web3.types import (
    RPCEndpoint,
)


class RPC:
    # admin
    admin_addPeer = RPCEndpoint("admin_addPeer")
    admin_datadir = RPCEndpoint("admin_datadir")
    admin_nodeInfo = RPCEndpoint("admin_nodeInfo")
    admin_peers = RPCEndpoint("admin_peers")
    admin_startHTTP = RPCEndpoint("admin_startHTTP")
    admin_startWS = RPCEndpoint("admin_startWS")
    admin_stopHTTP = RPCEndpoint("admin_stopHTTP")
    admin_stopWS = RPCEndpoint("admin_stopWS")
    # deprecated
    admin_startRPC = RPCEndpoint("admin_startRPC")
    admin_stopRPC = RPCEndpoint("admin_stopRPC")

    # eth
    eth_accounts = RPCEndpoint("eth_accounts")
    eth_blobBaseFee = RPCEndpoint("eth_blobBaseFee")
    eth_blockNumber = RPCEndpoint("eth_blockNumber")
    eth_call = RPCEndpoint("eth_call")
    eth_simulateV1 = RPCEndpoint("eth_simulateV1")
    eth_createAccessList = RPCEndpoint("eth_createAccessList")
    eth_chainId = RPCEndpoint("eth_chainId")
    eth_estimateGas = RPCEndpoint("eth_estimateGas")
    eth_feeHistory = RPCEndpoint("eth_feeHistory")
    eth_maxPriorityFeePerGas = RPCEndpoint("eth_maxPriorityFeePerGas")
    eth_gasPrice = RPCEndpoint("eth_gasPrice")
    eth_getBalance = RPCEndpoint("eth_getBalance")
    eth_getBlockByHash = RPCEndpoint("eth_getBlockByHash")
    eth_getBlockByNumber = RPCEndpoint("eth_getBlockByNumber")
    eth_getBlockReceipts = RPCEndpoint("eth_getBlockReceipts")
    eth_getBlockTransactionCountByHash = RPCEndpoint(
        "eth_getBlockTransactionCountByHash"
    )
    eth_getBlockTransactionCountByNumber = RPCEndpoint(
        "eth_getBlockTransactionCountByNumber"
    )
    eth_getCode = RPCEndpoint("eth_getCode")
    eth_getFilterChanges = RPCEndpoint("eth_getFilterChanges")
    eth_getFilterLogs = RPCEndpoint("eth_getFilterLogs")
    eth_getLogs = RPCEndpoint("eth_getLogs")
    eth_getProof = RPCEndpoint("eth_getProof")
    eth_getRawTransactionByHash = RPCEndpoint("eth_getRawTransactionByHash")
    eth_getStorageAt = RPCEndpoint("eth_getStorageAt")
    eth_getTransactionByBlockHashAndIndex = RPCEndpoint(
        "eth_getTransactionByBlockHashAndIndex"
    )
    eth_getTransactionByBlockNumberAndIndex = RPCEndpoint(
        "eth_getTransactionByBlockNumberAndIndex"
    )
    eth_getRawTransactionByBlockHashAndIndex = RPCEndpoint(
        "eth_getRawTransactionByBlockHashAndIndex"
    )
    eth_getRawTransactionByBlockNumberAndIndex = RPCEndpoint(
        "eth_getRawTransactionByBlockNumberAndIndex"
    )
    eth_getTransactionByHash = RPCEndpoint("eth_getTransactionByHash")
    eth_getTransactionCount = RPCEndpoint("eth_getTransactionCount")
    eth_getTransactionReceipt = RPCEndpoint("eth_getTransactionReceipt")
    eth_getUncleByBlockHashAndIndex = RPCEndpoint("eth_getUncleByBlockHashAndIndex")
    eth_getUncleByBlockNumberAndIndex = RPCEndpoint("eth_getUncleByBlockNumberAndIndex")
    eth_getUncleCountByBlockHash = RPCEndpoint("eth_getUncleCountByBlockHash")
    eth_getUncleCountByBlockNumber = RPCEndpoint("eth_getUncleCountByBlockNumber")
    eth_getWork = RPCEndpoint("eth_getWork")
    eth_newBlockFilter = RPCEndpoint("eth_newBlockFilter")
    eth_newFilter = RPCEndpoint("eth_newFilter")
    eth_newPendingTransactionFilter = RPCEndpoint("eth_newPendingTransactionFilter")
    eth_protocolVersion = RPCEndpoint("eth_protocolVersion")
    eth_sendRawTransaction = RPCEndpoint("eth_sendRawTransaction")
    eth_sendTransaction = RPCEndpoint("eth_sendTransaction")
    eth_sign = RPCEndpoint("eth_sign")
    eth_signTransaction = RPCEndpoint("eth_signTransaction")
    eth_signTypedData = RPCEndpoint("eth_signTypedData")
    eth_submitHashrate = RPCEndpoint("eth_submitHashrate")
    eth_submitWork = RPCEndpoint("eth_submitWork")
    eth_syncing = RPCEndpoint("eth_syncing")
    eth_uninstallFilter = RPCEndpoint("eth_uninstallFilter")
    eth_subscribe = RPCEndpoint("eth_subscribe")
    eth_unsubscribe = RPCEndpoint("eth_unsubscribe")

    # evm
    evm_mine = RPCEndpoint("evm_mine")
    evm_reset = RPCEndpoint("evm_reset")
    evm_revert = RPCEndpoint("evm_revert")
    evm_snapshot = RPCEndpoint("evm_snapshot")

    # net
    net_listening = RPCEndpoint("net_listening")
    net_peerCount = RPCEndpoint("net_peerCount")
    net_version = RPCEndpoint("net_version")

    # testing
    testing_timeTravel = RPCEndpoint("testing_timeTravel")

    # trace
    trace_block = RPCEndpoint("trace_block")
    trace_call = RPCEndpoint("trace_call")
    trace_filter = RPCEndpoint("trace_filter")
    trace_rawTransaction = RPCEndpoint("trace_rawTransaction")
    trace_replayBlockTransactions = RPCEndpoint("trace_replayBlockTransactions")
    trace_replayTransaction = RPCEndpoint("trace_replayTransaction")
    trace_transaction = RPCEndpoint("trace_transaction")

    # txpool
    txpool_content = RPCEndpoint("txpool_content")
    txpool_inspect = RPCEndpoint("txpool_inspect")
    txpool_status = RPCEndpoint("txpool_status")

    # web3
    web3_clientVersion = RPCEndpoint("web3_clientVersion")

    # debug
    debug_traceTransaction = RPCEndpoint("debug_traceTransaction")


TRANSACTION_PARAMS_ABIS = {
    "data": "bytes",
    "from": "address",
    "gas": "uint",
    "gasPrice": "uint",
    "maxFeePerBlobGas": "uint",
    "maxFeePerGas": "uint",
    "maxPriorityFeePerGas": "uint",
    "nonce": "uint",
    "to": "address",
    "value": "uint",
    "chainId": "uint",
}

FILTER_PARAMS_ABIS = {
    "to": "address",
    "address": "address[]",
}

TRACE_FILTER_PARAM_ABIS = {
    "fromBlock": "uint",
    "toBlock": "uint",
    "fromAddress": "address[]",
    "toAddress": "address[]",
    "after": "int",
    "count": "int",
}

RPC_ABIS: Dict[str, Union[Sequence[Any], Dict[str, str]]] = {
    # eth
    "eth_call": TRANSACTION_PARAMS_ABIS,
    "eth_createAccessList": TRANSACTION_PARAMS_ABIS,
    "eth_estimateGas": TRANSACTION_PARAMS_ABIS,
    "eth_getBalance": ["address", None],
    "eth_getBlockByHash": ["bytes32", "bool"],
    "eth_getBlockTransactionCountByHash": ["bytes32"],
    "eth_getCode": ["address", None],
    "eth_getLogs": FILTER_PARAMS_ABIS,
    "eth_getRawTransactionByHash": ["bytes32"],
    "eth_getStorageAt": ["address", "uint", None],
    "eth_getProof": ["address", "uint[]", None],
    "eth_getTransactionByBlockHashAndIndex": ["bytes32", "uint"],
    "eth_getTransactionByHash": ["bytes32"],
    "eth_getTransactionCount": ["address", None],
    "eth_getTransactionReceipt": ["bytes32"],
    "eth_getRawTransactionByBlockHashAndIndex": ["bytes32", "uint"],
    "eth_getUncleCountByBlockHash": ["bytes32"],
    "eth_newFilter": FILTER_PARAMS_ABIS,
    "eth_sendRawTransaction": ["bytes"],
    "eth_sendTransaction": TRANSACTION_PARAMS_ABIS,
    "eth_signTransaction": TRANSACTION_PARAMS_ABIS,
    "eth_sign": ["address", "bytes"],
    "eth_signTypedData": ["address", None],
    "eth_submitHashrate": ["uint", "bytes32"],
    "eth_submitWork": ["bytes8", "bytes32", "bytes32"],
    "trace_call": TRANSACTION_PARAMS_ABIS,
    "trace_filter": TRACE_FILTER_PARAM_ABIS,
}


@curry
def apply_abi_formatters_to_dict(
    normalizers: Sequence[Callable[[TypeStr, Any], Tuple[TypeStr, Any]]],
    abi_dict: Dict[str, Any],
    data: Dict[Any, Any],
) -> Dict[Any, Any]:
    fields = list(abi_dict.keys() & data.keys())
    formatted_values = map_abi_data(
        normalizers,
        [abi_dict[field] for field in fields],
        [data[field] for field in fields],
    )
    formatted_dict = dict(zip(fields, formatted_values))
    return dict(data, **formatted_dict)


@to_dict
def abi_request_formatters(
    normalizers: Sequence[Callable[[TypeStr, Any], Tuple[TypeStr, Any]]],
    abis: Dict[RPCEndpoint, Any],
) -> Iterable[Tuple[RPCEndpoint, Callable[..., Any]]]:
    for method, abi_types in abis.items():
        if isinstance(abi_types, list):
            yield method, map_abi_data(normalizers, abi_types)
        elif isinstance(abi_types, dict):
            single_dict_formatter = apply_abi_formatters_to_dict(normalizers, abi_types)
            yield method, apply_formatter_at_index(single_dict_formatter, 0)
        else:
            raise Web3TypeError(
                f"ABI definitions must be a list or dictionary, got {abi_types!r}"
            )
