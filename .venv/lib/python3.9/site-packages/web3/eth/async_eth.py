import asyncio
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
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

from web3._utils.async_transactions import (
    async_get_required_transaction,
    async_replace_transaction,
)
from web3._utils.blocks import (
    select_method_for_block_identifier,
)
from web3._utils.compat import (
    Unpack,
)
from web3._utils.fee_utils import (
    async_fee_history_priority_fee,
)
from web3._utils.filters import (
    AsyncFilter,
    select_filter_method,
)
from web3._utils.rpc_abi import (
    RPC,
)
from web3._utils.transactions import (
    assert_valid_transaction_params,
    extract_valid_transaction_params,
)
from web3.contract import (
    AsyncContract,
    AsyncContractCaller,
)
from web3.eth.base_eth import (
    BaseEth,
)
from web3.exceptions import (
    MethodNotSupported,
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
from web3.providers import (
    PersistentConnectionProvider,
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
    LogsSubscriptionArg,
    Nonce,
    SignedTx,
    SimulateV1Payload,
    SimulateV1Result,
    StateOverride,
    SubscriptionType,
    SyncStatus,
    TxData,
    TxParams,
    TxReceipt,
    Wei,
    _Hash32,
)
from web3.utils import (
    EthSubscription,
    async_handle_offchain_lookup,
)
from web3.utils.subscriptions import (
    EthSubscriptionHandler,
)

if TYPE_CHECKING:
    from web3 import AsyncWeb3  # noqa: F401
    from web3.contract.async_contract import AsyncContractEvent  # noqa: F401


class AsyncEth(BaseEth):
    # mypy types
    w3: "AsyncWeb3"

    is_async = True

    _default_contract_factory: Type[
        Union[AsyncContract, AsyncContractCaller]
    ] = AsyncContract

    # eth_accounts

    _accounts: Method[Callable[[], Awaitable[Tuple[ChecksumAddress]]]] = Method(
        RPC.eth_accounts,
        is_property=True,
    )

    @property
    async def accounts(self) -> Tuple[ChecksumAddress]:
        return await self._accounts()

    # eth_blobBaseFee

    _eth_blobBaseFee: Method[Callable[[], Awaitable[Wei]]] = Method(
        RPC.eth_blobBaseFee,
        is_property=True,
    )

    @property
    async def blob_base_fee(self) -> Wei:
        return await self._eth_blobBaseFee()

    # eth_blockNumber

    get_block_number: Method[Callable[[], Awaitable[BlockNumber]]] = Method(
        RPC.eth_blockNumber,
        is_property=True,
    )

    @property
    async def block_number(self) -> BlockNumber:
        return await self.get_block_number()

    # eth_chainId

    _chain_id: Method[Callable[[], Awaitable[int]]] = Method(
        RPC.eth_chainId,
        is_property=True,
    )

    @property
    async def chain_id(self) -> int:
        return await self._chain_id()

    # eth_gasPrice

    _gas_price: Method[Callable[[], Awaitable[Wei]]] = Method(
        RPC.eth_gasPrice,
        is_property=True,
    )

    @property
    async def gas_price(self) -> Wei:
        return await self._gas_price()

    # eth_maxPriorityFeePerGas

    _max_priority_fee: Method[Callable[[], Awaitable[Wei]]] = Method(
        RPC.eth_maxPriorityFeePerGas,
        is_property=True,
    )

    @property
    async def max_priority_fee(self) -> Wei:
        """
        Try to use eth_maxPriorityFeePerGas but, since this is not part
        of the spec and is only supported by some clients, fall back to
        an eth_feeHistory calculation with min and max caps.
        """
        try:
            return await self._max_priority_fee()
        except Web3RPCError:
            warnings.warn(
                "There was an issue with the method eth_maxPriorityFeePerGas. "
                "Calculating using eth_feeHistory.",
                stacklevel=2,
            )
            return await async_fee_history_priority_fee(self)

    # eth_syncing

    _syncing: Method[Callable[[], Awaitable[Union[SyncStatus, bool]]]] = Method(
        RPC.eth_syncing,
        is_property=True,
    )

    @property
    async def syncing(self) -> Union[SyncStatus, bool]:
        return await self._syncing()

    # eth_feeHistory

    _fee_history: Method[
        Callable[
            [int, Union[BlockParams, BlockNumber], Optional[List[float]]],
            Awaitable[FeeHistory],
        ]
    ] = Method(RPC.eth_feeHistory, mungers=[default_root_munger])

    async def fee_history(
        self,
        block_count: int,
        newest_block: Union[BlockParams, BlockNumber],
        reward_percentiles: Optional[List[float]] = None,
    ) -> FeeHistory:
        reward_percentiles = reward_percentiles or []
        return await self._fee_history(block_count, newest_block, reward_percentiles)

    # eth_call

    _call: Method[
        Callable[
            [
                TxParams,
                Optional[BlockIdentifier],
                Optional[StateOverride],
            ],
            Awaitable[HexBytes],
        ]
    ] = Method(RPC.eth_call, mungers=[BaseEth.call_munger])

    async def call(
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
            return await self._durin_call(transaction, block_identifier, state_override)

        return await self._call(transaction, block_identifier, state_override)

    async def _durin_call(
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
                return await self._call(transaction, block_identifier, state_override)
            except OffchainLookup as offchain_lookup:
                durin_calldata = await async_handle_offchain_lookup(
                    offchain_lookup.payload,
                    transaction,
                )
                transaction["data"] = durin_calldata

        raise TooManyRequests("Too many CCIP read redirects")

    # eth_simulateV1

    _simulateV1: Method[
        Callable[
            [SimulateV1Payload, BlockIdentifier],
            Awaitable[Sequence[SimulateV1Result]],
        ]
    ] = Method(RPC.eth_simulateV1)

    async def simulate_v1(
        self,
        payload: SimulateV1Payload,
        block_identifier: BlockIdentifier,
    ) -> Sequence[SimulateV1Result]:
        return await self._simulateV1(payload, block_identifier)

    # eth_createAccessList

    _create_access_list: Method[
        Callable[
            [TxParams, Optional[BlockIdentifier]],
            Awaitable[CreateAccessListResponse],
        ]
    ] = Method(RPC.eth_createAccessList, mungers=[BaseEth.create_access_list_munger])

    async def create_access_list(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> CreateAccessListResponse:
        return await self._create_access_list(transaction, block_identifier)

    # eth_estimateGas

    _estimate_gas: Method[
        Callable[
            [TxParams, Optional[BlockIdentifier], Optional[StateOverride]],
            Awaitable[int],
        ]
    ] = Method(RPC.eth_estimateGas, mungers=[BaseEth.estimate_gas_munger])

    async def estimate_gas(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[StateOverride] = None,
    ) -> int:
        return await self._estimate_gas(transaction, block_identifier, state_override)

    # eth_getTransactionByHash

    _get_transaction: Method[Callable[[_Hash32], Awaitable[TxData]]] = Method(
        RPC.eth_getTransactionByHash, mungers=[default_root_munger]
    )

    async def get_transaction(self, transaction_hash: _Hash32) -> TxData:
        return await self._get_transaction(transaction_hash)

    # eth_getRawTransactionByHash

    _get_raw_transaction: Method[Callable[[_Hash32], Awaitable[HexBytes]]] = Method(
        RPC.eth_getRawTransactionByHash, mungers=[default_root_munger]
    )

    async def get_raw_transaction(self, transaction_hash: _Hash32) -> HexBytes:
        return await self._get_raw_transaction(transaction_hash)

    # eth_getTransactionByBlockNumberAndIndex
    # eth_getTransactionByBlockHashAndIndex

    _get_transaction_by_block: Method[
        Callable[[BlockIdentifier, int], Awaitable[TxData]]
    ] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getTransactionByBlockNumberAndIndex,
            if_hash=RPC.eth_getTransactionByBlockHashAndIndex,
            if_number=RPC.eth_getTransactionByBlockNumberAndIndex,
        ),
        mungers=[default_root_munger],
    )

    async def get_transaction_by_block(
        self, block_identifier: BlockIdentifier, index: int
    ) -> TxData:
        return await self._get_transaction_by_block(block_identifier, index)

    # eth_getRawTransactionByBlockHashAndIndex
    # eth_getRawTransactionByBlockNumberAndIndex

    _get_raw_transaction_by_block: Method[
        Callable[[BlockIdentifier, int], Awaitable[HexBytes]]
    ] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getRawTransactionByBlockNumberAndIndex,
            if_hash=RPC.eth_getRawTransactionByBlockHashAndIndex,
            if_number=RPC.eth_getRawTransactionByBlockNumberAndIndex,
        ),
        mungers=[default_root_munger],
    )

    async def get_raw_transaction_by_block(
        self, block_identifier: BlockIdentifier, index: int
    ) -> HexBytes:
        return await self._get_raw_transaction_by_block(block_identifier, index)

    # eth_getBlockTransactionCountByHash
    # eth_getBlockTransactionCountByNumber

    get_block_transaction_count: Method[
        Callable[[BlockIdentifier], Awaitable[int]]
    ] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getBlockTransactionCountByNumber,
            if_hash=RPC.eth_getBlockTransactionCountByHash,
            if_number=RPC.eth_getBlockTransactionCountByNumber,
        ),
        mungers=[default_root_munger],
    )

    # eth_sendTransaction

    _send_transaction: Method[Callable[[TxParams], Awaitable[HexBytes]]] = Method(
        RPC.eth_sendTransaction, mungers=[BaseEth.send_transaction_munger]
    )

    async def send_transaction(self, transaction: TxParams) -> HexBytes:
        return await self._send_transaction(transaction)

    # eth_sendRawTransaction

    _send_raw_transaction: Method[
        Callable[[Union[HexStr, bytes]], Awaitable[HexBytes]]
    ] = Method(
        RPC.eth_sendRawTransaction,
        mungers=[default_root_munger],
    )

    async def send_raw_transaction(self, transaction: Union[HexStr, bytes]) -> HexBytes:
        return await self._send_raw_transaction(transaction)

    # eth_getBlockByHash
    # eth_getBlockByNumber

    _get_block: Method[
        Callable[[BlockIdentifier, bool], Awaitable[BlockData]]
    ] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getBlockByNumber,
            if_hash=RPC.eth_getBlockByHash,
            if_number=RPC.eth_getBlockByNumber,
        ),
        mungers=[BaseEth.get_block_munger],
    )

    async def get_block(
        self, block_identifier: BlockIdentifier, full_transactions: bool = False
    ) -> BlockData:
        return await self._get_block(block_identifier, full_transactions)

    # eth_getBlockReceipts

    _get_block_receipts: Method[
        Callable[[BlockIdentifier], Awaitable[BlockReceipts]]
    ] = Method(
        RPC.eth_getBlockReceipts,
        mungers=[default_root_munger],
    )

    async def get_block_receipts(
        self, block_identifier: BlockIdentifier
    ) -> BlockReceipts:
        return await self._get_block_receipts(block_identifier)

    # eth_getBalance

    _get_balance: Method[
        Callable[
            [Union[Address, ChecksumAddress, ENS], Optional[BlockIdentifier]],
            Awaitable[Wei],
        ]
    ] = Method(
        RPC.eth_getBalance,
        mungers=[BaseEth.block_id_munger],
    )

    async def get_balance(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> Wei:
        return await self._get_balance(account, block_identifier)

    # eth_getCode

    _get_code: Method[
        Callable[
            [Union[Address, ChecksumAddress, ENS], Optional[BlockIdentifier]],
            Awaitable[HexBytes],
        ]
    ] = Method(RPC.eth_getCode, mungers=[BaseEth.block_id_munger])

    async def get_code(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> HexBytes:
        return await self._get_code(account, block_identifier)

    # eth_getLogs

    _get_logs: Method[Callable[[FilterParams], Awaitable[List[LogReceipt]]]] = Method(
        RPC.eth_getLogs, mungers=[default_root_munger]
    )

    async def get_logs(
        self,
        filter_params: FilterParams,
    ) -> List[LogReceipt]:
        return await self._get_logs(filter_params)

    # eth_getTransactionCount

    _get_transaction_count: Method[
        Callable[
            [Union[Address, ChecksumAddress, ENS], Optional[BlockIdentifier]],
            Awaitable[Nonce],
        ]
    ] = Method(
        RPC.eth_getTransactionCount,
        mungers=[BaseEth.block_id_munger],
    )

    async def get_transaction_count(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> Nonce:
        return await self._get_transaction_count(account, block_identifier)

    # eth_getTransactionReceipt

    _transaction_receipt: Method[Callable[[_Hash32], Awaitable[TxReceipt]]] = Method(
        RPC.eth_getTransactionReceipt, mungers=[default_root_munger]
    )

    async def get_transaction_receipt(self, transaction_hash: _Hash32) -> TxReceipt:
        return await self._transaction_receipt(transaction_hash)

    async def wait_for_transaction_receipt(
        self,
        transaction_hash: _Hash32,
        timeout: Optional[float] = 120,
        poll_latency: float = 0.1,
    ) -> TxReceipt:
        async def _wait_for_tx_receipt_with_timeout(
            _tx_hash: _Hash32, _poll_latency: float
        ) -> TxReceipt:
            while True:
                try:
                    tx_receipt = await self._transaction_receipt(_tx_hash)
                except (TransactionNotFound, TransactionIndexingInProgress):
                    tx_receipt = None
                if tx_receipt is not None:
                    break
                await asyncio.sleep(poll_latency)
            return tx_receipt

        try:
            return await asyncio.wait_for(
                _wait_for_tx_receipt_with_timeout(transaction_hash, poll_latency),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise TimeExhausted(
                f"Transaction {HexBytes(transaction_hash) !r} is not in the chain "
                f"after {timeout} seconds"
            )

    # eth_getStorageAt

    _get_storage_at: Method[
        Callable[
            [Union[Address, ChecksumAddress, ENS], int, Optional[BlockIdentifier]],
            Awaitable[HexBytes],
        ]
    ] = Method(
        RPC.eth_getStorageAt,
        mungers=[BaseEth.get_storage_at_munger],
    )

    async def get_storage_at(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        position: int,
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> HexBytes:
        return await self._get_storage_at(account, position, block_identifier)

    async def replace_transaction(
        self, transaction_hash: _Hash32, new_transaction: TxParams
    ) -> HexBytes:
        current_transaction = await async_get_required_transaction(
            self.w3, transaction_hash
        )
        return await async_replace_transaction(
            self.w3, current_transaction, new_transaction
        )

    async def modify_transaction(
        self, transaction_hash: _Hash32, **transaction_params: Unpack[TxParams]
    ) -> HexBytes:
        assert_valid_transaction_params(cast(TxParams, transaction_params))

        current_transaction = await async_get_required_transaction(
            self.w3, transaction_hash
        )
        current_transaction_params = extract_valid_transaction_params(
            current_transaction
        )
        new_transaction = merge(current_transaction_params, transaction_params)

        return await async_replace_transaction(
            self.w3, current_transaction, new_transaction
        )

    # eth_sign

    _sign: Method[Callable[..., Awaitable[HexStr]]] = Method(
        RPC.eth_sign, mungers=[BaseEth.sign_munger]
    )

    async def sign(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        data: Union[int, bytes] = None,
        hexstr: HexStr = None,
        text: str = None,
    ) -> HexStr:
        return await self._sign(account, data, hexstr, text)

    # eth_signTransaction

    _sign_transaction: Method[Callable[[TxParams], Awaitable[SignedTx]]] = Method(
        RPC.eth_signTransaction,
        mungers=[default_root_munger],
    )

    async def sign_transaction(self, transaction: TxParams) -> SignedTx:
        return await self._sign_transaction(transaction)

    # eth_signTypedData

    _sign_typed_data: Method[
        Callable[
            [Union[Address, ChecksumAddress, ENS], Dict[str, Any]], Awaitable[HexStr]
        ]
    ] = Method(
        RPC.eth_signTypedData,
        mungers=[default_root_munger],
    )

    async def sign_typed_data(
        self, account: Union[Address, ChecksumAddress, ENS], data: Dict[str, Any]
    ) -> HexStr:
        return await self._sign_typed_data(account, data)

    # eth_getUncleCountByBlockHash
    # eth_getUncleCountByBlockNumber

    _get_uncle_count: Method[Callable[[BlockIdentifier], Awaitable[int]]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getUncleCountByBlockNumber,
            if_hash=RPC.eth_getUncleCountByBlockHash,
            if_number=RPC.eth_getUncleCountByBlockNumber,
        ),
        mungers=[default_root_munger],
    )

    async def get_uncle_count(self, block_identifier: BlockIdentifier) -> int:
        return await self._get_uncle_count(block_identifier)

    # eth_newFilter, eth_newBlockFilter, eth_newPendingTransactionFilter

    filter: Method[
        Callable[[Optional[Union[str, FilterParams, HexStr]]], Awaitable[AsyncFilter]]
    ] = Method(
        method_choice_depends_on_args=select_filter_method(
            if_new_block_filter=RPC.eth_newBlockFilter,
            if_new_pending_transaction_filter=RPC.eth_newPendingTransactionFilter,
            if_new_filter=RPC.eth_newFilter,
        ),
        mungers=[BaseEth.filter_munger],
    )

    # eth_getFilterChanges, eth_getFilterLogs, eth_uninstallFilter

    _get_filter_changes: Method[
        Callable[[HexStr], Awaitable[List[LogReceipt]]]
    ] = Method(RPC.eth_getFilterChanges, mungers=[default_root_munger])

    async def get_filter_changes(self, filter_id: HexStr) -> List[LogReceipt]:
        return await self._get_filter_changes(filter_id)

    _get_filter_logs: Method[Callable[[HexStr], Awaitable[List[LogReceipt]]]] = Method(
        RPC.eth_getFilterLogs, mungers=[default_root_munger]
    )

    async def get_filter_logs(self, filter_id: HexStr) -> List[LogReceipt]:
        return await self._get_filter_logs(filter_id)

    _uninstall_filter: Method[Callable[[HexStr], Awaitable[bool]]] = Method(
        RPC.eth_uninstallFilter,
        mungers=[default_root_munger],
    )

    async def uninstall_filter(self, filter_id: HexStr) -> bool:
        return await self._uninstall_filter(filter_id)

    # eth_subscribe / eth_unsubscribe

    _subscribe: Method[Callable[[SubscriptionType], Awaitable[HexStr]]] = Method(
        RPC.eth_subscribe,
        mungers=[default_root_munger],
    )

    _subscribe_with_args: Method[
        Callable[
            [
                SubscriptionType,
                Optional[Union[LogsSubscriptionArg, bool]],
            ],
            Awaitable[HexStr],
        ]
    ] = Method(
        RPC.eth_subscribe,
        mungers=[default_root_munger],
    )

    async def subscribe(
        self,
        subscription_type: SubscriptionType,
        subscription_arg: Optional[
            Union[
                LogsSubscriptionArg,  # logs, optional filter params
                bool,  # newPendingTransactions, full_transactions
            ]
        ] = None,
        handler: Optional[EthSubscriptionHandler] = None,
        handler_context: Optional[Dict[str, Any]] = None,
        label: Optional[str] = None,
    ) -> HexStr:
        if not isinstance(self.w3.provider, PersistentConnectionProvider):
            raise MethodNotSupported(
                "eth_subscribe is only supported with providers that support "
                "persistent connections."
            )

        sub = EthSubscription._create_type_aware_subscription(
            subscription_params=(subscription_type, subscription_arg),
            handler=handler,
            handler_context=handler_context or {},
            label=label,
        )
        return await self.w3.subscription_manager.subscribe(sub)

    _unsubscribe: Method[Callable[[HexStr], Awaitable[bool]]] = Method(
        RPC.eth_unsubscribe,
        mungers=[default_root_munger],
    )

    async def unsubscribe(self, subscription_id: HexStr) -> bool:
        if not isinstance(self.w3.provider, PersistentConnectionProvider):
            raise MethodNotSupported(
                "eth_unsubscribe is only supported with providers that support "
                "persistent connections."
            )

        for sub in self.w3.subscription_manager.subscriptions:
            if sub._id == subscription_id:
                return await sub.unsubscribe()

        raise Web3ValueError(
            f"Cannot unsubscribe subscription with id `{subscription_id}`. "
            "Subscription not found."
        )

    # -- contract methods -- #

    @overload
    def contract(self, address: None = None, **kwargs: Any) -> Type[AsyncContract]:
        ...

    @overload
    def contract(
        self, address: Union[Address, ChecksumAddress, ENS], **kwargs: Any
    ) -> AsyncContract:
        ...

    def contract(
        self,
        address: Optional[Union[Address, ChecksumAddress, ENS]] = None,
        **kwargs: Any,
    ) -> Union[Type[AsyncContract], AsyncContract]:
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
        contract_factory: Type[Union[AsyncContract, AsyncContractCaller]],
    ) -> None:
        self._default_contract_factory = contract_factory
