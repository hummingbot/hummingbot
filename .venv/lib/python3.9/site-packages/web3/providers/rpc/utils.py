from typing import (
    Sequence,
    Type,
)

from pydantic import (
    BaseModel,
)

from web3.types import (
    RPCEndpoint,
)

REQUEST_RETRY_ALLOWLIST = [
    "admin",
    "net",
    "txpool",
    "testing",
    "evm",
    "eth_protocolVersion",
    "eth_syncing",
    "eth_chainId",
    "eth_gasPrice",
    "eth_accounts",
    "eth_blockNumber",
    "eth_getBalance",
    "eth_getStorageAt",
    "eth_getProof",
    "eth_getCode",
    "eth_getBlockByNumber",
    "eth_getBlockByHash",
    "eth_getBlockTransactionCountByNumber",
    "eth_getBlockTransactionCountByHash",
    "eth_getUncleCountByBlockNumber",
    "eth_getUncleCountByBlockHash",
    "eth_getTransactionByHash",
    "eth_getTransactionByBlockHashAndIndex",
    "eth_getTransactionByBlockNumberAndIndex",
    "eth_getTransactionReceipt",
    "eth_getTransactionCount",
    "eth_getRawTransactionByHash",
    "eth_call",
    "eth_estimateGas",
    "eth_createAccessList",
    "eth_maxPriorityFeePerGas",
    "eth_newBlockFilter",
    "eth_newPendingTransactionFilter",
    "eth_newFilter",
    "eth_getFilterChanges",
    "eth_getFilterLogs",
    "eth_getLogs",
    "eth_uninstallFilter",
    "eth_getCompilers",
    "eth_getWork",
    "eth_sign",
    "eth_signTypedData",
    "eth_sendRawTransaction",
]


def check_if_retry_on_failure(
    method: RPCEndpoint,
    allowlist: Sequence[str] = None,
) -> bool:
    if allowlist is None:
        allowlist = REQUEST_RETRY_ALLOWLIST

    if method in allowlist or method.split("_")[0] in allowlist:
        return True
    else:
        return False


class ExceptionRetryConfiguration(BaseModel):
    errors: Sequence[Type[BaseException]]
    retries: int
    backoff_factor: float
    method_allowlist: Sequence[str]

    def __init__(
        self,
        errors: Sequence[Type[BaseException]] = None,
        retries: int = 5,
        backoff_factor: float = 0.125,
        method_allowlist: Sequence[str] = None,
    ):
        super().__init__(
            errors=errors,
            retries=retries,
            backoff_factor=backoff_factor,
            method_allowlist=method_allowlist or REQUEST_RETRY_ALLOWLIST,
        )
