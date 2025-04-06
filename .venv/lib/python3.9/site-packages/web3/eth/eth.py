from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
    overload,
)
import warnings

from eth_typing import (
    Address,
    BlockNumber,
    ChecksumAddress,
    HexStr,
)
from eth_utils.toolz import (
    merge,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.blocks import (
    select_method_for_block_identifier,
)
from web3._utils.compat import (
    Unpack,
)
from web3._utils.fee_utils import (
    fee_history_priority_fee,
)
from web3._utils.filters import (
    Filter,
    select_filter_method,
)
from web3._utils.rpc_abi import (
    RPC,
)
from web3._utils.threads import (
    Timeout,
)
from web3._utils.transactions import (
    assert_valid_transaction_params,
    extract_valid_transaction_params,
    get_required_transaction,
    replace_transaction,
)
from web3.contract import (
    Contract,
    ContractCaller,
)
from web3.eth.base_eth import (
    BaseEth,
)
from web3.exceptions import (
    OffchainLookup,
    TimeExhausted,
    TooManyRequests,
    TransactionIndexingInProgress,
    TransactionNotFound,
    Web3RPCError,
    Web3ValueError,
)
from web3.method import (
    Method,
    default_root_munger,
)
from web3.types import (
    ENS,
    BlockData,
    BlockIdentifier,
    BlockParams,
    BlockReceipts,
    CreateAccessListResponse,
    FeeHistory,
    FilterParams,
    LogReceipt,
    MerkleProof,
    Nonce,
    SignedTx,
    SimulateV1Payload,
    SimulateV1Result,
    StateOverride,
    SyncStatus,
    TxData,
    TxParams,
    TxReceipt,
    Uncle,
    Wei,
    _Hash32,
)
from web3.utils import (
    handle_offchain_lookup,
)

if TYPE_CHECKING:
    from web3 import Web3  # noqa: F401


class Eth(BaseEth):
    # mypy types
    w3: "Web3"

    _default_contract_factory: Type[Union[Contract, ContractCaller]] = Contract

    # eth_accounts

    _accounts: Method[Callable[[], Tuple[ChecksumAddress]]] = Method(
        RPC.eth_accounts,
        is_property=True,
    )

    @property
    def accounts(self) -> Tuple[ChecksumAddress]:
        return self._accounts()

    # eth_blobBaseFee

    _eth_blobBaseFee: Method[Callable[[], Wei]] = Method(
        RPC.eth_blobBaseFee,
        is_property=True,
    )

    @property
    def blob_base_fee(self) -> Wei:
        return self._eth_blobBaseFee()

    # eth_blockNumber

    get_block_number: Method[Callable[[], BlockNumber]] = Method(
        RPC.eth_blockNumber,
        is_property=True,
    )

    @property
    def block_number(self) -> BlockNumber:
        return self.get_block_number()

    # eth_chainId

    _chain_id: Method[Callable[[], int]] = Method(
        RPC.eth_chainId,
        is_property=True,
    )

    @property
    def chain_id(self) -> int:
        return self._chain_id()

    # eth_gasPrice

    _gas_price: Method[Callable[[], Wei]] = Method(
        RPC.eth_gasPrice,
        is_property=True,
    )

    @property
    def gas_price(self) -> Wei:
        return self._gas_price()

    # eth_maxPriorityFeePerGas

    _max_priority_fee: Method[Callable[[], Wei]] = Method(
        RPC.eth_maxPriorityFeePerGas,
        is_property=True,
    )

    @property
    def max_priority_fee(self) -> Wei:
        """
        Try to use eth_maxPriorityFeePerGas but, since this is not part
        of the spec and is only supported by some clients, fall back to
        an eth_feeHistory calculation with min and max caps.
        """
        try:
            return self._max_priority_fee()
        except Web3RPCError:
            warnings.warn(
                "There was an issue with the method eth_maxPriorityFeePerGas. "
                "Calculating using eth_feeHistory.",
                stacklevel=2,
            )
            return fee_history_priority_fee(self)

    # eth_syncing

    _syncing: Method[Callable[[], Union[SyncStatus, bool]]] = Method(
        RPC.eth_syncing,
        is_property=True,
    )

    @property
    def syncing(self) -> Union[SyncStatus, bool]:
        return self._syncing()

    # eth_feeHistory

    _fee_history: Method[
        Callable[
            [int, Union[BlockParams, BlockNumber], Optional[List[float]]], FeeHistory
        ]
    ] = Method(RPC.eth_feeHistory, mungers=[default_root_munger])

    def fee_history(
        self,
        block_count: int,
        newest_block: Union[BlockParams, BlockNumber],
        reward_percentiles: Optional[List[float]] = None,
    ) -> FeeHistory:
        reward_percentiles = reward_percentiles or []
        return self._fee_history(block_count, newest_block, reward_percentiles)

    # eth_call

    _call: Method[
        Callable[
            [TxParams, Optional[BlockIdentifier], Optional[StateOverride]],
            HexBytes,
        ]
    ] = Method(RPC.eth_call, mungers=[BaseEth.call_munger])

    def call(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[StateOverride] = None,
        ccip_read_enabled: Optional[bool] = None,
    ) -> HexBytes:
        ccip_read_enabled_on_provider = self.w3.provider.global_ccip_read_enabled
        if (
            # default conditions:
            ccip_read_enabled_on_provider
            and ccip_read_enabled is not False
            # explicit call flag overrides provider flag,
            # enabling ccip read for specific calls:
            or not ccip_read_enabled_on_provider
            and ccip_read_enabled is True
        ):
            return self._durin_call(transaction, block_identifier, state_override)

        return self._call(transaction, block_identifier, state_override)

    def _durin_call(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[StateOverride] = None,
    ) -> HexBytes:
        max_redirects = self.w3.provider.ccip_read_max_redirects

        if not max_redirects or max_redirects < 4:
            raise Web3ValueError(
                "ccip_read_max_redirects property on provider must be at least 4."
            )

        for _ in range(max_redirects):
            try:
                return self._call(transaction, block_identifier, state_override)
            except OffchainLookup as offchain_lookup:
                durin_calldata = handle_offchain_lookup(
                    offchain_lookup.payload,
                    transaction,
                )
                transaction["data"] = durin_calldata

        raise TooManyRequests("Too many CCIP read redirects")

    # eth_simulateV1

    _simulateV1: Method[
        Callable[[SimulateV1Payload, BlockIdentifier], Sequence[SimulateV1Result]]
    ] = Method(RPC.eth_simulateV1)

    def simulate_v1(
        self,
        payload: SimulateV1Payload,
        block_identifier: BlockIdentifier,
    ) -> Sequence[SimulateV1Result]:
        return self._simulateV1(payload, block_identifier)

    # eth_createAccessList

    _create_access_list: Method[
        Callable[
            [TxParams, Optional[BlockIdentifier]],
            CreateAccessListResponse,
        ]
    ] = Method(RPC.eth_createAccessList, mungers=[BaseEth.create_access_list_munger])

    def create_access_list(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> CreateAccessListResponse:
        return self._create_access_list(transaction, block_identifier)

    # eth_estimateGas

    _estimate_gas: Method[
        Callable[[TxParams, Optional[BlockIdentifier], Optional[StateOverride]], int]
    ] = Method(RPC.eth_estimateGas, mungers=[BaseEth.estimate_gas_munger])

    def estimate_gas(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[StateOverride] = None,
    ) -> int:
        return self._estimate_gas(transaction, block_identifier, state_override)

    # eth_getTransactionByHash

    _get_transaction: Method[Callable[[_Hash32], TxData]] = Method(
        RPC.eth_getTransactionByHash, mungers=[default_root_munger]
    )

    def get_transaction(self, transaction_hash: _Hash32) -> TxData:
        return self._get_transaction(transaction_hash)

    # eth_getRawTransactionByHash

    _get_raw_transaction: Method[Callable[[_Hash32], HexBytes]] = Method(
        RPC.eth_getRawTransactionByHash, mungers=[default_root_munger]
    )

    def get_raw_transaction(self, transaction_hash: _Hash32) -> HexBytes:
        return self._get_raw_transaction(transaction_hash)

    # eth_getTransactionByBlockNumberAndIndex
    # eth_getTransactionByBlockHashAndIndex

    get_transaction_by_block: Method[Callable[[BlockIdentifier, int], TxData]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getTransactionByBlockNumberAndIndex,
            if_hash=RPC.eth_getTransactionByBlockHashAndIndex,
            if_number=RPC.eth_getTransactionByBlockNumberAndIndex,
        ),
        mungers=[default_root_munger],
    )

    # eth_getRawTransactionByBlockHashAndIndex
    # eth_getRawTransactionByBlockNumberAndIndex

    _get_raw_transaction_by_block: Method[
        Callable[[BlockIdentifier, int], HexBytes]
    ] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getRawTransactionByBlockNumberAndIndex,
            if_hash=RPC.eth_getRawTransactionByBlockHashAndIndex,
            if_number=RPC.eth_getRawTransactionByBlockNumberAndIndex,
        ),
        mungers=[default_root_munger],
    )

    def get_raw_transaction_by_block(
        self, block_identifier: BlockIdentifier, index: int
    ) -> HexBytes:
        return self._get_raw_transaction_by_block(block_identifier, index)

    # eth_getBlockTransactionCountByHash
    # eth_getBlockTransactionCountByNumber

    get_block_transaction_count: Method[Callable[[BlockIdentifier], int]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getBlockTransactionCountByNumber,
            if_hash=RPC.eth_getBlockTransactionCountByHash,
            if_number=RPC.eth_getBlockTransactionCountByNumber,
        ),
        mungers=[default_root_munger],
    )

    # eth_sendTransaction

    _send_transaction: Method[Callable[[TxParams], HexBytes]] = Method(
        RPC.eth_sendTransaction, mungers=[BaseEth.send_transaction_munger]
    )

    def send_transaction(self, transaction: TxParams) -> HexBytes:
        return self._send_transaction(transaction)

    # eth_sendRawTransaction

    _send_raw_transaction: Method[Callable[[Union[HexStr, bytes]], HexBytes]] = Method(
        RPC.eth_sendRawTransaction,
        mungers=[default_root_munger],
    )

    def send_raw_transaction(self, transaction: Union[HexStr, bytes]) -> HexBytes:
        return self._send_raw_transaction(transaction)

    # eth_getBlockByHash
    # eth_getBlockByNumber

    _get_block: Method[Callable[[BlockIdentifier, bool], BlockData]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getBlockByNumber,
            if_hash=RPC.eth_getBlockByHash,
            if_number=RPC.eth_getBlockByNumber,
        ),
        mungers=[BaseEth.get_block_munger],
    )

    def get_block(
        self, block_identifier: BlockIdentifier, full_transactions: bool = False
    ) -> BlockData:
        return self._get_block(block_identifier, full_transactions)

    # eth_getBlockReceipts

    _get_block_receipts: Method[Callable[[BlockIdentifier], BlockReceipts]] = Method(
        RPC.eth_getBlockReceipts,
        mungers=[default_root_munger],
    )

    def get_block_receipts(self, block_identifier: BlockIdentifier) -> BlockReceipts:
        return self._get_block_receipts(block_identifier)

    # eth_getBalance

    _get_balance: Method[
        Callable[[Union[Address, ChecksumAddress, ENS], Optional[BlockIdentifier]], Wei]
    ] = Method(
        RPC.eth_getBalance,
        mungers=[BaseEth.block_id_munger],
    )

    def get_balance(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> Wei:
        return self._get_balance(account, block_identifier)

    # eth_getCode

    _get_code: Method[
        Callable[
            [Union[Address, ChecksumAddress, ENS], Optional[BlockIdentifier]], HexBytes
        ]
    ] = Method(RPC.eth_getCode, mungers=[BaseEth.block_id_munger])

    def get_code(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> HexBytes:
        return self._get_code(account, block_identifier)

    # eth_getLogs

    _get_logs: Method[Callable[[FilterParams], List[LogReceipt]]] = Method(
        RPC.eth_getLogs, mungers=[default_root_munger]
    )

    def get_logs(
        self,
        filter_params: FilterParams,
    ) -> List[LogReceipt]:
        return self._get_logs(filter_params)

    # eth_getTransactionCount

    _get_transaction_count: Method[
        Callable[
            [Union[Address, ChecksumAddress, ENS], Optional[BlockIdentifier]], Nonce
        ]
    ] = Method(
        RPC.eth_getTransactionCount,
        mungers=[BaseEth.block_id_munger],
    )

    def get_transaction_count(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> Nonce:
        return self._get_transaction_count(account, block_identifier)

    # eth_getTransactionReceipt

    _transaction_receipt: Method[Callable[[_Hash32], TxReceipt]] = Method(
        RPC.eth_getTransactionReceipt, mungers=[default_root_munger]
    )

    def get_transaction_receipt(self, transaction_hash: _Hash32) -> TxReceipt:
        return self._transaction_receipt(transaction_hash)

    def wait_for_transaction_receipt(
        self, transaction_hash: _Hash32, timeout: float = 120, poll_latency: float = 0.1
    ) -> TxReceipt:
        try:
            with Timeout(timeout) as _timeout:
                while True:
                    try:
                        tx_receipt = self._transaction_receipt(transaction_hash)
                    except (TransactionNotFound, TransactionIndexingInProgress):
                        tx_receipt = None
                    if tx_receipt is not None:
                        break
                    _timeout.sleep(poll_latency)
            return tx_receipt

        except Timeout:
            raise TimeExhausted(
                f"Transaction {HexBytes(transaction_hash) !r} is not in the chain "
                f"after {timeout} seconds"
            )

    # eth_getStorageAt

    _get_storage_at: Method[
        Callable[
            [Union[Address, ChecksumAddress, ENS], int, Optional[BlockIdentifier]],
            HexBytes,
        ]
    ] = Method(
        RPC.eth_getStorageAt,
        mungers=[BaseEth.get_storage_at_munger],
    )

    def get_storage_at(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        position: int,
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> HexBytes:
        return self._get_storage_at(account, position, block_identifier)

    # eth_getProof

    def get_proof_munger(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        positions: Sequence[int],
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> Tuple[
        Union[Address, ChecksumAddress, ENS], Sequence[int], Optional[BlockIdentifier]
    ]:
        if block_identifier is None:
            block_identifier = self.default_block
        return (account, positions, block_identifier)

    get_proof: Method[
        Callable[
            [
                Tuple[
                    Union[Address, ChecksumAddress, ENS],
                    Sequence[int],
                    Optional[BlockIdentifier],
                ]
            ],
            MerkleProof,
        ]
    ] = Method(
        RPC.eth_getProof,
        mungers=[get_proof_munger],
    )

    # eth_getUncleCountByBlockHash
    # eth_getUncleCountByBlockNumber

    get_uncle_count: Method[Callable[[BlockIdentifier], int]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getUncleCountByBlockNumber,
            if_hash=RPC.eth_getUncleCountByBlockHash,
            if_number=RPC.eth_getUncleCountByBlockNumber,
        ),
        mungers=[default_root_munger],
    )

    # eth_getUncleByBlockHashAndIndex
    # eth_getUncleByBlockNumberAndIndex

    get_uncle_by_block: Method[Callable[[BlockIdentifier, int], Uncle]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getUncleByBlockNumberAndIndex,
            if_hash=RPC.eth_getUncleByBlockHashAndIndex,
            if_number=RPC.eth_getUncleByBlockNumberAndIndex,
        ),
        mungers=[default_root_munger],
    )

    def replace_transaction(
        self, transaction_hash: _Hash32, new_transaction: TxParams
    ) -> HexBytes:
        current_transaction = get_required_transaction(self.w3, transaction_hash)
        return replace_transaction(self.w3, current_transaction, new_transaction)

    def modify_transaction(
        self, transaction_hash: _Hash32, **transaction_params: Unpack[TxParams]
    ) -> HexBytes:
        assert_valid_transaction_params(cast(TxParams, transaction_params))
        current_transaction = get_required_transaction(self.w3, transaction_hash)
        current_transaction_params = extract_valid_transaction_params(
            current_transaction
        )
        new_transaction = merge(current_transaction_params, transaction_params)
        return replace_transaction(self.w3, current_transaction, new_transaction)

    # eth_sign

    sign: Method[Callable[..., HexStr]] = Method(
        RPC.eth_sign, mungers=[BaseEth.sign_munger]
    )

    # eth_signTransaction

    sign_transaction: Method[Callable[[TxParams], SignedTx]] = Method(
        RPC.eth_signTransaction,
        mungers=[default_root_munger],
    )

    # eth_signTypedData

    sign_typed_data: Method[
        Callable[[Union[Address, ChecksumAddress, ENS], Dict[str, Any]], HexStr]
    ] = Method(
        RPC.eth_signTypedData,
        mungers=[default_root_munger],
    )

    # eth_newFilter, eth_newBlockFilter, eth_newPendingTransactionFilter

    filter: Method[
        Callable[[Optional[Union[str, FilterParams, HexStr]]], Filter]
    ] = Method(
        method_choice_depends_on_args=select_filter_method(
            if_new_block_filter=RPC.eth_newBlockFilter,
            if_new_pending_transaction_filter=RPC.eth_newPendingTransactionFilter,
            if_new_filter=RPC.eth_newFilter,
        ),
        mungers=[BaseEth.filter_munger],
    )

    # eth_getFilterChanges, eth_getFilterLogs, eth_uninstallFilter

    get_filter_changes: Method[Callable[[HexStr], List[LogReceipt]]] = Method(
        RPC.eth_getFilterChanges, mungers=[default_root_munger]
    )

    get_filter_logs: Method[Callable[[HexStr], List[LogReceipt]]] = Method(
        RPC.eth_getFilterLogs, mungers=[default_root_munger]
    )

    uninstall_filter: Method[Callable[[HexStr], bool]] = Method(
        RPC.eth_uninstallFilter,
        mungers=[default_root_munger],
    )

    @overload
    def contract(self, address: None = None, **kwargs: Any) -> Type[Contract]:
        ...

    @overload
    def contract(
        self, address: Union[Address, ChecksumAddress, ENS], **kwargs: Any
    ) -> Contract:
        ...

    def contract(
        self,
        address: Optional[Union[Address, ChecksumAddress, ENS]] = None,
        **kwargs: Any,
    ) -> Union[Type[Contract], Contract]:
        ContractFactoryClass = kwargs.pop(
            "ContractFactoryClass", self._default_contract_factory
        )

        ContractFactory = ContractFactoryClass.factory(self.w3, **kwargs)

        if address:
            return ContractFactory(address)
        else:
            return ContractFactory

    def set_contract_factory(
        self,
        contract_factory: Type[Union[Contract, ContractCaller]],
    ) -> None:
        self._default_contract_factory = contract_factory
