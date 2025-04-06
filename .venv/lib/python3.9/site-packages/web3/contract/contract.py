from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Type,
    cast,
)

from eth_typing import (
    ABI,
    ChecksumAddress,
)
from eth_utils import (
    abi_to_signature,
    combomethod,
    filter_abi_by_type,
    get_abi_input_names,
)
from eth_utils.toolz import (
    partial,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.abi import (
    fallback_func_abi_exists,
    receive_func_abi_exists,
)
from web3._utils.abi_element_identifiers import (
    FallbackFn,
    ReceiveFn,
)
from web3._utils.compat import (
    Self,
)
from web3._utils.contracts import (
    parse_block_identifier,
)
from web3._utils.datatypes import (
    PropertyCheckingFactory,
)
from web3._utils.events import (
    EventFilterBuilder,
    get_event_data,
)
from web3._utils.filters import (
    LogFilter,
)
from web3._utils.normalizers import (
    normalize_abi,
    normalize_address,
    normalize_bytecode,
)
from web3._utils.transactions import (
    fill_transaction_defaults,
)
from web3.contract.base_contract import (
    BaseContract,
    BaseContractCaller,
    BaseContractConstructor,
    BaseContractEvent,
    BaseContractEvents,
    BaseContractFunction,
    BaseContractFunctions,
    NonExistentFallbackFunction,
    NonExistentReceiveFunction,
)
from web3.contract.utils import (
    build_transaction_for_function,
    call_contract_function,
    estimate_gas_for_function,
    find_events_by_identifier,
    find_functions_by_identifier,
    get_event_by_identifier,
    get_function_by_identifier,
    transact_with_contract_function,
)
from web3.exceptions import (
    Web3AttributeError,
    Web3TypeError,
    Web3ValidationError,
    Web3ValueError,
)
from web3.types import (
    BlockIdentifier,
    EventData,
    StateOverride,
    TxParams,
)

if TYPE_CHECKING:
    from ens import ENS  # noqa: F401
    from web3 import Web3  # noqa: F401


class ContractEvent(BaseContractEvent):
    # mypy types
    w3: "Web3"

    @combomethod
    def get_logs(
        self,
        argument_filters: Optional[Dict[str, Any]] = None,
        from_block: Optional[BlockIdentifier] = None,
        to_block: Optional[BlockIdentifier] = None,
        block_hash: Optional[HexBytes] = None,
    ) -> Iterable[EventData]:
        """
        Get events for this contract instance using eth_getLogs API.

        This is a stateless method, as opposed to create_filter.
        It can be safely called against nodes which do not provide
        eth_newFilter API, like Infura nodes.

        If there are many events,
        like ``Transfer`` events for a popular token,
        the Ethereum node might be overloaded and timeout
        on the underlying JSON-RPC call.

        Example - how to get all ERC-20 token transactions
        for the latest 10 blocks:

        .. code-block:: python

            from = max(my_contract.web3.eth.block_number - 10, 1)
            to = my_contract.web3.eth.block_number

            events = my_contract.events.Transfer.get_logs(from_block=from, to_block=to)

            for e in events:
                print(e["args"]["from"],
                    e["args"]["to"],
                    e["args"]["value"])

        The returned processed log values will look like:

        .. code-block:: python

            (
                AttributeDict({
                 'args': AttributeDict({}),
                 'event': 'LogNoArguments',
                 'logIndex': 0,
                 'transactionIndex': 0,
                 'transactionHash': HexBytes('...'),
                 'address': '0xF2E246BB76DF876Cef8b38ae84130F4F55De395b',
                 'blockHash': HexBytes('...'),
                 'blockNumber': 3
                }),
                AttributeDict(...),
                ...
            )

        See also: :func:`web3.middleware.filter.LocalFilterMiddleware`.

        :param argument_filters: Filter by argument values. Indexed arguments are
          filtered by the node while non-indexed arguments are filtered by the library.
        :param from_block: block number or "latest", defaults to "latest"
        :param to_block: block number or "latest". Defaults to "latest"
        :param block_hash: block hash. block_hash cannot be set at the
          same time as ``from_block`` or ``to_block``
        :yield: Tuple of :class:`AttributeDict` instances
        """
        event_abi = self._get_event_abi()
        # validate ``argument_filters`` if present
        if argument_filters is not None:
            event_arg_names = get_abi_input_names(event_abi)
            if not all(arg in event_arg_names for arg in argument_filters.keys()):
                raise Web3ValidationError(
                    "When filtering by argument names, all argument names must be "
                    "present in the contract's event ABI."
                )

        _filter_params = self._get_event_filter_params(
            event_abi, argument_filters, from_block, to_block, block_hash
        )
        # call JSON-RPC API
        logs = self.w3.eth.get_logs(_filter_params)

        # convert raw binary data to Python proxy objects as described by ABI:
        all_event_logs = tuple(
            get_event_data(self.w3.codec, event_abi, entry) for entry in logs
        )
        filtered_logs = self._process_get_logs_argument_filters(
            event_abi,
            all_event_logs,
            argument_filters,
        )
        sorted_logs = sorted(filtered_logs, key=lambda e: e["logIndex"])
        sorted_logs = sorted(sorted_logs, key=lambda e: e["blockNumber"])
        return sorted_logs

    @combomethod
    def create_filter(
        self,
        *,  # PEP 3102
        argument_filters: Optional[Dict[str, Any]] = None,
        from_block: Optional[BlockIdentifier] = None,
        to_block: BlockIdentifier = "latest",
        address: Optional[ChecksumAddress] = None,
        topics: Optional[Sequence[Any]] = None,
    ) -> LogFilter:
        """
        Create filter object that tracks logs emitted by this contract event.
        """
        abi = self._get_event_abi()
        filter_builder = EventFilterBuilder(abi, self.w3.codec)
        self._set_up_filter_builder(
            argument_filters,
            from_block,
            to_block,
            address,
            topics,
            filter_builder,
        )
        log_filter = filter_builder.deploy(self.w3)
        log_filter.log_entry_formatter = get_event_data(self.w3.codec, abi)
        log_filter.builder = filter_builder

        return log_filter

    @combomethod
    def build_filter(self) -> EventFilterBuilder:
        abi = self._get_event_abi()
        builder = EventFilterBuilder(
            abi,
            self.w3.codec,
            formatter=get_event_data(self.w3.codec, abi),
        )
        builder.address = self.address
        return builder


class ContractEvents(BaseContractEvents[ContractEvent]):
    def __init__(
        self, abi: ABI, w3: "Web3", address: Optional[ChecksumAddress] = None
    ) -> None:
        super().__init__(abi, w3, ContractEvent, address)


class ContractFunction(BaseContractFunction):
    # mypy types
    w3: "Web3"

    def call(
        self,
        transaction: Optional[TxParams] = None,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[StateOverride] = None,
        ccip_read_enabled: Optional[bool] = None,
    ) -> Any:
        """
        Execute a contract function call using the `eth_call` interface.

        This method prepares a ``Caller`` object that exposes the contract
        functions and public variables as callable Python functions.

        Reading a public ``owner`` address variable example:

        .. code-block:: python

            ContractFactory = w3.eth.contract(
                abi=wallet_contract_definition["abi"]
            )

            # Not a real contract address
            contract = ContractFactory("0x2f70d3d26829e412A602E83FE8EeBF80255AEeA5")

            # Read "owner" public variable
            addr = contract.functions.owner().call()

        :param transaction: Dictionary of transaction info for web3 interface
        :param block_identifier: Block number or string "latest", "pending", "earliest"
        :param state_override: Dictionary of state override values
        :param ccip_read_enabled: Enable CCIP read operations for the call
        :return: ``Caller`` object that has contract public functions
            and variables exposed as Python methods
        """
        call_transaction = self._get_call_txparams(transaction)

        block_id = parse_block_identifier(self.w3, block_identifier)

        abi_element_identifier = abi_to_signature(self.abi)

        return call_contract_function(
            self.w3,
            self.address,
            self._return_data_normalizers,
            abi_element_identifier,
            call_transaction,
            block_id,
            self.contract_abi,
            self.abi,
            state_override,
            ccip_read_enabled,
            self.decode_tuples,
            *self.args or (),
            **self.kwargs or {},
        )

    def transact(self, transaction: Optional[TxParams] = None) -> HexBytes:
        setup_transaction = self._transact(transaction)
        abi_element_identifier = abi_to_signature(self.abi)

        return transact_with_contract_function(
            self.address,
            self.w3,
            abi_element_identifier,
            setup_transaction,
            self.contract_abi,
            self.abi,
            *self.args or (),
            **self.kwargs or {},
        )

    def estimate_gas(
        self,
        transaction: Optional[TxParams] = None,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[StateOverride] = None,
    ) -> int:
        setup_transaction = self._estimate_gas(transaction)
        abi_element_identifier = abi_to_signature(self.abi)
        return estimate_gas_for_function(
            self.address,
            self.w3,
            abi_element_identifier,
            setup_transaction,
            self.contract_abi,
            self.abi,
            block_identifier,
            state_override,
            *self.args or (),
            **self.kwargs or {},
        )

    def build_transaction(self, transaction: Optional[TxParams] = None) -> TxParams:
        built_transaction = self._build_transaction(transaction)
        abi_element_identifier = abi_to_signature(self.abi)

        return build_transaction_for_function(
            self.address,
            self.w3,
            abi_element_identifier,
            built_transaction,
            self.contract_abi,
            self.abi,
            *self.args or (),
            **self.kwargs or {},
        )

    @staticmethod
    def get_fallback_function(
        abi: ABI,
        w3: "Web3",
        address: Optional[ChecksumAddress] = None,
    ) -> "ContractFunction":
        if abi and fallback_func_abi_exists(abi):
            fallback_abi = filter_abi_by_type("fallback", abi)[0]
            return ContractFunction.factory(
                "fallback",
                w3=w3,
                contract_abi=abi,
                address=address,
                abi_element_identifier=FallbackFn,
                abi=fallback_abi,
            )()
        return cast(ContractFunction, NonExistentFallbackFunction())

    @staticmethod
    def get_receive_function(
        abi: ABI,
        w3: "Web3",
        address: Optional[ChecksumAddress] = None,
    ) -> "ContractFunction":
        if abi and receive_func_abi_exists(abi):
            receive_abi = filter_abi_by_type("receive", abi)[0]
            return ContractFunction.factory(
                "receive",
                w3=w3,
                contract_abi=abi,
                address=address,
                abi_element_identifier=ReceiveFn,
                abi=receive_abi,
            )()
        return cast(ContractFunction, NonExistentReceiveFunction())


class ContractFunctions(BaseContractFunctions[ContractFunction]):
    def __init__(
        self,
        abi: ABI,
        w3: "Web3",
        address: Optional[ChecksumAddress] = None,
        decode_tuples: Optional[bool] = False,
    ) -> None:
        super().__init__(abi, w3, ContractFunction, address, decode_tuples)


class Contract(BaseContract):
    # mypy types
    w3: "Web3"
    functions: ContractFunctions = None
    caller: "ContractCaller" = None

    # Instance of :class:`ContractEvents` presenting available Event ABIs
    events: ContractEvents = None

    def __init__(self, address: Optional[ChecksumAddress] = None) -> None:
        """
        Create a new smart contract proxy object.
        :param address: Contract address as 0x hex string
        """
        _w3 = self.w3
        if _w3 is None:
            raise Web3AttributeError(
                "The `Contract` class has not been initialized.  Please use the "
                "`web3.contract` interface to create your contract class."
            )

        if address:
            # invoke ``w3._ens`` over ``w3.ens`` to avoid premature instantiation
            self.address = normalize_address(cast("ENS", _w3._ens), address)

        if not self.address:
            raise Web3TypeError(
                "The address argument is required to instantiate a contract."
            )

        self.functions = ContractFunctions(
            self.abi, _w3, self.address, decode_tuples=self.decode_tuples
        )
        self.caller = ContractCaller(
            self.abi,
            _w3,
            self.address,
            decode_tuples=self.decode_tuples,
            contract_functions=self.functions,
        )
        self.events = ContractEvents(self.abi, _w3, self.address)
        self.fallback = Contract.get_fallback_function(
            self.abi,
            _w3,
            ContractFunction,
            self.address,
        )
        self.receive = Contract.get_receive_function(
            self.abi,
            _w3,
            ContractFunction,
            self.address,
        )

    @classmethod
    def factory(
        cls, w3: "Web3", class_name: Optional[str] = None, **kwargs: Any
    ) -> Type[Self]:
        kwargs["w3"] = w3

        normalizers = {
            "abi": normalize_abi,
            # invoke ``w3._ens`` over ``w3.ens`` to avoid premature instantiation
            "address": partial(normalize_address, w3._ens),
            "bytecode": normalize_bytecode,
            "bytecode_runtime": normalize_bytecode,
        }

        contract = cast(
            Type[Self],
            PropertyCheckingFactory(
                class_name or cls.__name__,
                (cls,),
                kwargs,
                normalizers=normalizers,
            ),
        )

        if contract.abi:
            for abi in contract.abi:
                abi_name = abi.get("name")
                if abi_name in ["abi", "address"]:
                    raise Web3AttributeError(
                        f"Contract contains a reserved word `{abi_name}` "
                        f"and could not be instantiated."
                    )

        contract.functions = ContractFunctions(
            contract.abi, contract.w3, decode_tuples=contract.decode_tuples
        )
        contract.caller = ContractCaller(
            contract.abi,
            contract.w3,
            contract.address,
            decode_tuples=contract.decode_tuples,
            contract_functions=contract.functions,
        )
        contract.events = ContractEvents(contract.abi, contract.w3)
        contract.fallback = Contract.get_fallback_function(
            contract.abi,
            contract.w3,
            ContractFunction,
        )
        contract.receive = Contract.get_receive_function(
            contract.abi,
            contract.w3,
            ContractFunction,
        )

        return contract

    @classmethod
    def constructor(cls, *args: Any, **kwargs: Any) -> "ContractConstructor":
        """
        :param args: The contract constructor arguments as positional arguments
        :param kwargs: The contract constructor arguments as keyword arguments
        :return: a contract constructor object
        """
        if cls.bytecode is None:
            raise Web3ValueError(
                "Cannot call constructor on a contract that does not have "
                "'bytecode' associated with it"
            )

        return ContractConstructor(cls.w3, cls.abi, cls.bytecode, *args, **kwargs)

    @combomethod
    def find_functions_by_identifier(
        cls,
        contract_abi: ABI,
        w3: "Web3",
        address: ChecksumAddress,
        callable_check: Callable[..., Any],
    ) -> List["ContractFunction"]:
        return cast(
            List["ContractFunction"],
            find_functions_by_identifier(
                contract_abi, w3, address, callable_check, ContractFunction
            ),
        )

    @combomethod
    def get_function_by_identifier(
        cls, fns: Sequence["ContractFunction"], identifier: str
    ) -> "ContractFunction":
        return get_function_by_identifier(fns, identifier)

    @combomethod
    def find_events_by_identifier(
        cls,
        contract_abi: ABI,
        w3: "Web3",
        address: ChecksumAddress,
        callable_check: Callable[..., Any],
    ) -> List["ContractEvent"]:
        return find_events_by_identifier(
            contract_abi, w3, address, callable_check, ContractEvent
        )

    @combomethod
    def get_event_by_identifier(
        self, events: Sequence["ContractEvent"], identifier: str
    ) -> "ContractEvent":
        return get_event_by_identifier(events, identifier)


class ContractCaller(BaseContractCaller):
    # mypy types
    w3: "Web3"

    def __init__(
        self,
        abi: ABI,
        w3: "Web3",
        address: ChecksumAddress,
        transaction: Optional[TxParams] = None,
        block_identifier: BlockIdentifier = None,
        ccip_read_enabled: Optional[bool] = None,
        decode_tuples: Optional[bool] = False,
        contract_functions: Optional[ContractFunctions] = None,
    ) -> None:
        super().__init__(abi, w3, address, decode_tuples=decode_tuples)

        if self.abi:
            if transaction is None:
                transaction = {}

            if contract_functions is None:
                contract_functions = ContractFunctions(
                    abi, w3, address=address, decode_tuples=decode_tuples
                )

            self._functions = contract_functions._functions
            for fn in contract_functions.__iter__():
                caller_method = partial(
                    self.call_function,
                    fn,
                    transaction=transaction,
                    block_identifier=block_identifier,
                    ccip_read_enabled=ccip_read_enabled,
                )
                setattr(self, str(fn.abi_element_identifier), caller_method)

    def __call__(
        self,
        transaction: Optional[TxParams] = None,
        block_identifier: BlockIdentifier = None,
        ccip_read_enabled: Optional[bool] = None,
    ) -> "ContractCaller":
        if transaction is None:
            transaction = {}

        return type(self)(
            self.abi,
            self.w3,
            self.address,
            transaction=transaction,
            block_identifier=block_identifier,
            ccip_read_enabled=ccip_read_enabled,
            decode_tuples=self.decode_tuples,
        )


class ContractConstructor(BaseContractConstructor):
    # mypy types
    w3: "Web3"

    @combomethod
    def transact(self, transaction: Optional[TxParams] = None) -> HexBytes:
        return self.w3.eth.send_transaction(self._get_transaction(transaction))

    @combomethod
    def build_transaction(self, transaction: Optional[TxParams] = None) -> TxParams:
        """
        Build the transaction dictionary without sending
        """
        built_transaction = self._build_transaction(transaction)
        return fill_transaction_defaults(self.w3, built_transaction)

    @combomethod
    def estimate_gas(
        self,
        transaction: Optional[TxParams] = None,
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> int:
        transaction = self._estimate_gas(transaction)

        return self.w3.eth.estimate_gas(transaction, block_identifier=block_identifier)
