from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Literal,
    NewType,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
)

from eth_typing import (
    Address,
    BlockNumber,
    ChecksumAddress,
    Hash32,
    HexStr,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.abi_element_identifiers import (
    FallbackFn,
    ReceiveFn,
)
from web3._utils.compat import (
    NotRequired,
)

if TYPE_CHECKING:
    from web3.contract.base_contract import (
        BaseContractEvent,
        BaseContractFunction,
    )
    from web3.main import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )


TFunc = TypeVar("TFunc", bound=Callable[..., Any])
TParams = TypeVar("TParams")
TReturn = TypeVar("TReturn")
TValue = TypeVar("TValue")

BlockParams = Literal["latest", "earliest", "pending", "safe", "finalized"]
BlockIdentifier = Union[BlockParams, BlockNumber, Hash32, HexStr, HexBytes, int]
LatestBlockParam = Literal["latest"]

ABIElementIdentifier = Union[str, Type[FallbackFn], Type[ReceiveFn]]

# bytes, hexbytes, or hexstr representing a 32 byte hash
_Hash32 = Union[Hash32, HexBytes, HexStr]
EnodeURI = NewType("EnodeURI", str)
ENS = NewType("ENS", str)
Nonce = NewType("Nonce", int)
RPCEndpoint = NewType("RPCEndpoint", str)
Timestamp = NewType("Timestamp", int)
Wei = NewType("Wei", int)
Gwei = NewType("Gwei", int)
Formatters = Dict[RPCEndpoint, Callable[..., Any]]


class AccessListEntry(TypedDict):
    address: HexStr
    storageKeys: Sequence[HexStr]


AccessList = NewType("AccessList", Sequence[AccessListEntry])


class EventData(TypedDict):
    address: ChecksumAddress
    args: Dict[str, Any]
    blockHash: HexBytes
    blockNumber: int
    event: str
    logIndex: int
    transactionHash: HexBytes
    transactionIndex: int


class RPCError(TypedDict):
    code: int
    message: str
    data: NotRequired[str]


# syntax b/c "from" keyword not allowed w/ class construction
TxData = TypedDict(
    "TxData",
    {
        "accessList": AccessList,
        "blobVersionedHashes": Sequence[HexBytes],
        "blockHash": HexBytes,
        "blockNumber": BlockNumber,
        "chainId": int,
        "data": Union[bytes, HexStr],
        "from": ChecksumAddress,
        "gas": int,
        "gasPrice": Wei,
        "maxFeePerBlobGas": Wei,
        "maxFeePerGas": Wei,
        "maxPriorityFeePerGas": Wei,
        "hash": HexBytes,
        "input": HexBytes,
        "nonce": Nonce,
        "r": HexBytes,
        "s": HexBytes,
        "to": ChecksumAddress,
        "transactionIndex": int,
        "type": Union[int, HexStr],
        "v": int,
        "value": Wei,
        "yParity": int,
    },
    total=False,
)

# syntax b/c "from" keyword not allowed w/ class construction
TxParams = TypedDict(
    "TxParams",
    {
        "accessList": AccessList,
        "blobVersionedHashes": Sequence[Union[str, HexStr, bytes, HexBytes]],
        "chainId": int,
        "data": Union[bytes, HexStr],
        # addr or ens
        "from": Union[Address, ChecksumAddress, str],
        "gas": int,
        # legacy pricing
        "gasPrice": Wei,
        "maxFeePerBlobGas": Union[str, Wei],
        # dynamic fee pricing
        "maxFeePerGas": Union[str, Wei],
        "maxPriorityFeePerGas": Union[str, Wei],
        "nonce": Nonce,
        # addr or ens
        "to": Union[Address, ChecksumAddress, str],
        "type": Union[int, HexStr],
        "value": Wei,
    },
    total=False,
)


class WithdrawalData(TypedDict):
    index: int
    validator_index: int
    address: ChecksumAddress
    amount: Gwei


class BlockData(TypedDict, total=False):
    baseFeePerGas: Wei
    difficulty: int
    extraData: HexBytes
    gasLimit: int
    gasUsed: int
    hash: HexBytes
    logsBloom: HexBytes
    miner: ChecksumAddress
    mixHash: HexBytes
    nonce: HexBytes
    number: BlockNumber
    parentHash: HexBytes
    receiptsRoot: HexBytes
    sha3Uncles: HexBytes
    size: int
    stateRoot: HexBytes
    timestamp: Timestamp
    totalDifficulty: int
    transactions: Union[Sequence[HexBytes], Sequence[TxData]]
    transactionsRoot: HexBytes
    uncles: Sequence[HexBytes]
    withdrawals: Sequence[WithdrawalData]
    withdrawalsRoot: HexBytes
    parentBeaconBlockRoot: HexBytes
    blobGasUsed: int
    excessBlobGas: int

    # ExtraDataToPOAMiddleware replaces extraData w/ proofOfAuthorityData
    proofOfAuthorityData: HexBytes


class LogReceipt(TypedDict):
    address: ChecksumAddress
    blockHash: HexBytes
    blockNumber: BlockNumber
    data: HexBytes
    logIndex: int
    removed: bool
    topics: Sequence[HexBytes]
    transactionHash: HexBytes
    transactionIndex: int


class SubscriptionResponse(TypedDict):
    subscription: HexBytes


class BlockTypeSubscriptionResponse(SubscriptionResponse):
    result: BlockData


class TransactionTypeSubscriptionResponse(SubscriptionResponse):
    result: Union[HexBytes, TxData]


class LogsSubscriptionResponse(SubscriptionResponse):
    result: LogReceipt


class SyncProgress(TypedDict):
    isSyncing: bool
    startingBlock: int
    currentBlock: int
    highestBlock: int


class SyncingSubscriptionResponse(SubscriptionResponse):
    result: Union[Literal[False], SyncProgress]


class GethSyncingStatus(TypedDict):
    currentBlock: int
    highestBlock: int
    knownStates: int
    pulledStates: int
    startingBlock: int


class GethSyncingSubscriptionResult(TypedDict):
    syncing: bool
    status: GethSyncingStatus


class GethSyncingSubscriptionResponse(SubscriptionResponse):
    result: GethSyncingSubscriptionResult


EthSubscriptionParams = Union[
    BlockTypeSubscriptionResponse,
    TransactionTypeSubscriptionResponse,
    LogsSubscriptionResponse,
    SyncingSubscriptionResponse,
    GethSyncingSubscriptionResponse,
]

RPCId = Optional[Union[int, str]]


class RPCRequest(TypedDict, total=False):
    id: RPCId
    jsonrpc: Literal["2.0"]
    method: RPCEndpoint
    params: Any


class RPCResponse(TypedDict, total=False):
    error: RPCError
    id: RPCId
    jsonrpc: Literal["2.0"]
    result: Any

    # eth_subscribe
    method: Literal["eth_subscription"]
    params: EthSubscriptionParams


EthSubscriptionResult = Union[
    BlockData,  # newHeads
    TxData,  # newPendingTransactions, full_transactions=True
    HexBytes,  # newPendingTransactions, full_transactions=False
    LogReceipt,  # logs
    SyncProgress,  # syncing
    GethSyncingSubscriptionResult,  # geth syncing
]


class FormattedEthSubscriptionResponse(TypedDict):
    subscription: HexStr
    result: EthSubscriptionResult


class CreateAccessListResponse(TypedDict):
    accessList: AccessList
    gasUsed: int


MakeRequestFn = Callable[[RPCEndpoint, Any], RPCResponse]
MakeBatchRequestFn = Callable[
    [List[Tuple[RPCEndpoint, Any]]], Union[List[RPCResponse], RPCResponse]
]
AsyncMakeRequestFn = Callable[[RPCEndpoint, Any], Coroutine[Any, Any, RPCResponse]]
AsyncMakeBatchRequestFn = Callable[
    [List[Tuple[RPCEndpoint, Any]]],
    Coroutine[Any, Any, Union[List[RPCResponse], RPCResponse]],
]


class FormattersDict(TypedDict, total=False):
    error_formatters: Optional[Formatters]
    request_formatters: Optional[Formatters]
    result_formatters: Optional[Formatters]


class FilterParams(TypedDict, total=False):
    address: Union[Address, ChecksumAddress, List[Address], List[ChecksumAddress]]
    blockHash: HexBytes
    fromBlock: BlockIdentifier
    toBlock: BlockIdentifier
    topics: Sequence[Optional[Union[_Hash32, Sequence[_Hash32]]]]


class FeeHistory(TypedDict):
    baseFeePerGas: List[Wei]
    gasUsedRatio: List[float]
    oldestBlock: BlockNumber
    reward: List[List[Wei]]


class StateOverrideParams(TypedDict, total=False):
    balance: Optional[Wei]
    nonce: Optional[int]
    code: Optional[Union[bytes, HexStr]]
    state: Optional[Dict[HexStr, HexStr]]
    stateDiff: Optional[Dict[HexStr, HexStr]]


StateOverride = Dict[Union[str, Address, ChecksumAddress], StateOverrideParams]


GasPriceStrategy = Union[
    Callable[["Web3", TxParams], Wei], Callable[["AsyncWeb3", TxParams], Wei]
]


# syntax b/c "from" keyword not allowed w/ class construction
TxReceipt = TypedDict(
    "TxReceipt",
    {
        "blockHash": HexBytes,
        "blockNumber": BlockNumber,
        "contractAddress": Optional[ChecksumAddress],
        "cumulativeGasUsed": int,
        "effectiveGasPrice": Wei,
        "gasUsed": int,
        "from": ChecksumAddress,
        "logs": List[LogReceipt],
        "logsBloom": HexBytes,
        "root": HexStr,
        "status": int,
        "to": ChecksumAddress,
        "transactionHash": HexBytes,
        "transactionIndex": int,
        "type": int,
    },
)

BlockReceipts = List[TxReceipt]


class SignedTx(TypedDict, total=False):
    raw: bytes
    tx: TxParams


class StorageProof(TypedDict):
    key: HexStr
    proof: Sequence[HexStr]
    value: HexBytes


class MerkleProof(TypedDict):
    address: ChecksumAddress
    accountProof: Sequence[HexStr]
    balance: int
    codeHash: HexBytes
    nonce: Nonce
    storageHash: HexBytes
    storageProof: Sequence[StorageProof]


class Protocol(TypedDict):
    difficulty: int
    head: HexStr
    network: int
    version: int


class NodeInfo(TypedDict):
    enode: EnodeURI
    id: HexStr
    ip: str
    listenAddr: str
    name: str
    ports: Dict[str, int]
    protocols: Dict[str, Protocol]


class Peer(TypedDict, total=False):
    caps: Sequence[str]
    id: HexStr
    name: str
    network: Dict[str, str]
    protocols: Dict[str, Protocol]


class SyncStatus(TypedDict):
    currentBlock: int
    highestBlock: int
    knownStates: int
    pulledStates: int
    startingBlock: int


class Uncle(TypedDict):
    author: ChecksumAddress
    difficulty: HexStr
    extraData: HexStr
    gasLimit: HexStr
    gasUsed: HexStr
    hash: HexBytes
    logsBloom: HexStr
    miner: HexBytes
    mixHash: HexBytes
    nonce: HexStr
    number: HexStr
    parentHash: HexBytes
    receiptsRoot: HexBytes
    sealFields: Sequence[HexStr]
    sha3Uncles: HexBytes
    size: int
    stateRoot: HexBytes
    timestamp: Timestamp
    totalDifficulty: HexStr
    transactions: Sequence[HexBytes]
    transactionsRoot: HexBytes
    uncles: Sequence[HexBytes]


#
# txpool types
#

# syntax b/c "from" keyword not allowed w/ class construction
PendingTx = TypedDict(
    "PendingTx",
    {
        "blockHash": HexBytes,
        "blockNumber": None,
        "from": ChecksumAddress,
        "gas": HexBytes,
        "maxFeePerGas": HexBytes,
        "maxPriorityFeePerGas": HexBytes,
        "gasPrice": HexBytes,
        "hash": HexBytes,
        "input": HexBytes,
        "nonce": HexBytes,
        "to": ChecksumAddress,
        "transactionIndex": None,
        "value": HexBytes,
    },
    total=False,
)


class TxPoolContent(TypedDict, total=False):
    pending: Dict[ChecksumAddress, Dict[Nonce, List[PendingTx]]]
    queued: Dict[ChecksumAddress, Dict[Nonce, List[PendingTx]]]


class TxPoolInspect(TypedDict, total=False):
    pending: Dict[ChecksumAddress, Dict[Nonce, str]]
    queued: Dict[ChecksumAddress, Dict[Nonce, str]]


class TxPoolStatus(TypedDict, total=False):
    pending: int
    queued: int


#
# debug types
#
class TraceConfig(TypedDict, total=False):
    disableStorage: bool
    disableStack: bool
    enableMemory: bool
    enableReturnData: bool
    tracer: str
    tracerConfig: Dict[str, Any]
    timeout: int


class CallTraceLog(TypedDict):
    address: ChecksumAddress
    data: HexBytes
    topics: Sequence[HexBytes]
    position: int


# syntax b/c "from" keyword not allowed w/ class construction
CallTrace = TypedDict(
    "CallTrace",
    {
        "type": str,
        "from": ChecksumAddress,
        "to": ChecksumAddress,
        "value": Wei,
        "gas": int,
        "gasUsed": int,
        "input": HexBytes,
        "output": HexBytes,
        "error": str,
        "revertReason": str,
        "calls": Sequence["CallTrace"],
        "logs": Sequence[CallTraceLog],
    },
    total=False,
)


class TraceData(TypedDict, total=False):
    balance: int
    nonce: int
    code: str
    storage: Dict[str, str]


class DiffModeTrace(TypedDict):
    post: Dict[ChecksumAddress, TraceData]
    pre: Dict[ChecksumAddress, TraceData]


PrestateTrace = Dict[ChecksumAddress, TraceData]


# 4byte tracer returns something like:
# { '0x27dc297e-128' : 1 }
# which is: { 4byte signature - calldata size : # of occurrences of key }
FourByteTrace = Dict[str, int]


class StructLog(TypedDict):
    pc: int
    op: str
    gas: int
    gasCost: int
    depth: int
    stack: List[HexStr]


class OpcodeTrace(TypedDict, total=False):
    gas: int
    failed: bool
    returnValue: str
    structLogs: List[StructLog]


class BlockStateCallV1(TypedDict):
    blockOverrides: NotRequired[BlockData]
    stateOverrides: NotRequired[StateOverride]
    calls: Sequence[TxParams]


class SimulateV1Payload(TypedDict):
    blockStateCalls: Sequence[BlockStateCallV1]
    validation: NotRequired[bool]
    traceTransfers: NotRequired[bool]


class SimulateV1CallResult(TypedDict):
    returnData: HexBytes
    logs: Sequence[LogReceipt]
    gasUsed: int
    status: int
    error: NotRequired[RPCError]


class SimulateV1Result(BlockData):
    calls: Sequence[SimulateV1CallResult]


#
# web3.geth types
#


class GethWallet(TypedDict):
    accounts: Sequence[Dict[str, str]]
    status: str
    url: str


# Contract types

TContractFn = TypeVar("TContractFn", bound="BaseContractFunction")
TContractEvent = TypeVar("TContractEvent", bound="BaseContractEvent")


# Tracing types
BlockTrace = NewType("BlockTrace", Dict[str, Any])
FilterTrace = NewType("FilterTrace", Dict[str, Any])
TraceMode = Sequence[Literal["trace", "vmTrace", "stateDiff"]]


class TraceFilterParams(TypedDict, total=False):
    after: int
    count: int
    fromAddress: Sequence[Union[Address, ChecksumAddress, ENS]]
    fromBlock: BlockIdentifier
    toAddress: Sequence[Union[Address, ChecksumAddress, ENS]]
    toBlock: BlockIdentifier


# Subscriptions

SubscriptionType = Literal[
    "newHeads",
    "logs",
    "newPendingTransactions",
    "syncing",
]


class LogsSubscriptionArg(TypedDict, total=False):
    address: Union[
        Address,
        ChecksumAddress,
        ENS,
        Sequence[Union[Address, ChecksumAddress, ENS]],
    ]
    topics: Sequence[Union[HexStr, Sequence[HexStr]]]
