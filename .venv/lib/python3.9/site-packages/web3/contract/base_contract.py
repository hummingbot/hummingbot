from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Collection,
    Dict,
    Generic,
    Iterable,
    List,
    NoReturn,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)
import warnings

from eth_abi.exceptions import (
    InsufficientDataBytes,
)
from eth_typing import (
    ABI,
    ABIElement,
    ABIEvent,
    ABIFunction,
    Address,
    ChecksumAddress,
    HexStr,
)
from eth_utils import (
    abi_to_signature,
    add_0x_prefix,
    combomethod,
    encode_hex,
    filter_abi_by_type,
    function_abi_to_4byte_selector,
    get_normalized_abi_inputs,
    is_list_like,
    is_text,
    keccak,
    to_bytes,
    to_tuple,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.abi import (
    fallback_func_abi_exists,
    find_constructor_abi_element_by_type,
    get_abi_element_signature,
    get_name_from_abi_element_identifier,
    is_array_type,
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
    copy_contract_event,
    copy_contract_function,
    decode_transaction_data,
    encode_abi,
    prepare_transaction,
)
from web3._utils.datatypes import (
    PropertyCheckingFactory,
)
from web3._utils.empty import (
    empty,
)
from web3._utils.encoding import (
    hexstr_if_str,
    to_4byte_hex,
    to_hex,
)
from web3._utils.events import (
    AsyncEventFilterBuilder,
    EventFilterBuilder,
    get_event_data,
    is_dynamic_sized_type,
)
from web3._utils.filters import (
    construct_event_filter_params,
)
from web3._utils.normalizers import (
    BASE_RETURN_NORMALIZERS,
)
from web3.datastructures import (
    AttributeDict,
    MutableAttributeDict,
)
from web3.exceptions import (
    ABIEventNotFound,
    ABIFallbackNotFound,
    ABIFunctionNotFound,
    ABIReceiveNotFound,
    InvalidEventABI,
    LogTopicError,
    MismatchedABI,
    NoABIEventsFound,
    NoABIFound,
    NoABIFunctionsFound,
    Web3AttributeError,
    Web3TypeError,
    Web3ValidationError,
    Web3ValueError,
)
from web3.logs import (
    DISCARD,
    IGNORE,
    STRICT,
    WARN,
    EventLogErrorFlags,
)
from web3.types import (
    ABIElementIdentifier,
    BlockIdentifier,
    EventData,
    FilterParams,
    LogReceipt,
    StateOverride,
    TContractEvent,
    TContractFn,
    TxParams,
    TxReceipt,
)
from web3.utils.abi import (
    _filter_by_argument_count,
    _get_any_abi_signature_with_name,
    _mismatched_abi_error_diagnosis,
    check_if_arguments_can_be_encoded,
    get_abi_element,
    get_abi_element_info,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )

    from .async_contract import (  # noqa: F401
        AsyncContractEvent,
        AsyncContractFunction,
    )
    from .contract import (  # noqa: F401
        ContractEvent,
        ContractFunction,
    )


class BaseContractEvent:
    """
    Base class for contract events

    An event accessed via the api `contract.events.myEvents(*args, **kwargs)`
    is a subclass of this class.
    """

    address: ChecksumAddress = None
    event_name: str = None
    name: str = None
    abi_element_identifier: ABIElementIdentifier = None
    signature: str = None
    w3: Union["Web3", "AsyncWeb3"] = None
    contract_abi: ABI = None
    abi: ABIEvent = None
    argument_names: Tuple[str, ...] = tuple()
    argument_types: Tuple[str, ...] = tuple()
    args: Any = None
    kwargs: Any = None
    _topic: HexStr = None

    def __init__(self, *argument_names: str, abi: Optional[ABIEvent] = None) -> None:
        self.abi_element_identifier = type(self).__name__
        self.name = get_name_from_abi_element_identifier(self.abi_element_identifier)
        self.event_name = self.name

        if abi:
            self.abi = abi

        self.signature = abi_to_signature(self.abi)

        if argument_names:
            self.argument_names = argument_names

        event_inputs = self.abi.get("inputs", [])
        self.argument_names = tuple([input.get("name", None) for input in event_inputs])
        self.argument_types = tuple([input["type"] for input in event_inputs])

    def __repr__(self) -> str:
        if self.abi:
            return f"<Event {abi_to_signature(self.abi)}>"
        return f"<Event {get_abi_element_signature(self.abi_element_identifier)}>"

    def __call__(self, *args: Any, **kwargs: Any) -> Self:
        return copy_contract_event(self, *args, **kwargs)

    @property
    def topic(self) -> HexStr:
        if self._topic is None:
            self._topic = encode_hex(keccak(text=self.signature))
        return self._topic

    @combomethod
    def _get_event_abi(cls) -> ABIEvent:
        if cls.abi:
            return cls.abi

        return cast(
            ABIEvent,
            get_abi_element(
                filter_abi_by_type("event", cls.contract_abi),
                cls.abi_element_identifier,
                abi_codec=cls.w3.codec,
            ),
        )

    def _set_event_info(self) -> None:
        self.abi = self._get_event_abi()

    @combomethod
    def process_receipt(
        self, txn_receipt: TxReceipt, errors: EventLogErrorFlags = WARN
    ) -> Iterable[EventData]:
        return self._parse_logs(txn_receipt=txn_receipt, errors=errors)

    @combomethod
    @to_tuple
    def _parse_logs(
        self, txn_receipt: TxReceipt, errors: EventLogErrorFlags
    ) -> Iterable[EventData]:
        try:
            errors.name
        except AttributeError:
            raise Web3AttributeError(
                f"Error flag must be one of: {EventLogErrorFlags.flag_options()}"
            )

        for log in txn_receipt["logs"]:
            try:
                rich_log = get_event_data(self.w3.codec, self.abi, log)
            except (
                MismatchedABI,
                LogTopicError,
                InvalidEventABI,
                TypeError,
                InsufficientDataBytes,
            ) as e:
                if errors == DISCARD:
                    continue
                elif errors == IGNORE:
                    # type ignores b/c rich_log set on 1092 conflicts with mutated types
                    new_log = MutableAttributeDict(log)  # type: ignore
                    new_log["errors"] = e
                    rich_log = AttributeDict(new_log)  # type: ignore
                elif errors == STRICT:
                    raise e
                else:
                    warnings.warn(
                        f"The log with transaction hash: {log['transactionHash']!r} "
                        f"and logIndex: {log['logIndex']} encountered the following "
                        f"error during processing: {type(e).__name__}({e}). It has "
                        "been discarded.",
                        stacklevel=2,
                    )
                    continue
            yield rich_log

    @combomethod
    def process_log(self, log: LogReceipt) -> EventData:
        return get_event_data(self.w3.codec, self.abi, log)

    @combomethod
    def _get_event_filter_params(
        self,
        abi: ABIEvent,
        argument_filters: Optional[Dict[str, Any]] = None,
        from_block: Optional[BlockIdentifier] = None,
        to_block: Optional[BlockIdentifier] = None,
        block_hash: Optional[HexBytes] = None,
    ) -> FilterParams:
        if not self.address:
            raise Web3TypeError(
                "This method can be only called on "
                "an instated contract with an address"
            )

        if argument_filters is None:
            argument_filters = dict()

        _filters = dict(**argument_filters)

        blkhash_set = block_hash is not None
        blknum_set = from_block is not None or to_block is not None
        if blkhash_set and blknum_set:
            raise Web3ValidationError(
                "`block_hash` cannot be set at the same time as "
                "`from_block` or `to_block`"
            )

        # Construct JSON-RPC raw filter presentation based on human readable
        # Python descriptions. Namely, convert event names to their keccak signatures
        _, event_filter_params = construct_event_filter_params(
            abi,
            self.w3.codec,
            contract_address=self.address,
            argument_filters=_filters,
            from_block=from_block,
            to_block=to_block,
            address=self.address,
        )

        if block_hash is not None:
            event_filter_params["blockHash"] = block_hash

        return event_filter_params

    @classmethod
    def factory(cls, class_name: str, **kwargs: Any) -> Self:
        return PropertyCheckingFactory(class_name, (cls,), kwargs)()

    @staticmethod
    def check_for_forbidden_api_filter_arguments(
        event_abi: ABIEvent, _filters: Dict[str, Any]
    ) -> None:
        name_indexed_inputs = {_input["name"]: _input for _input in event_abi["inputs"]}

        for filter_name, filter_value in _filters.items():
            _input = name_indexed_inputs[filter_name]
            if is_array_type(_input["type"]):
                raise Web3TypeError(
                    "createFilter no longer supports array type filter arguments. "
                    "see the build_filter method for filtering array type filters."
                )
            if is_list_like(filter_value) and is_dynamic_sized_type(_input["type"]):
                raise Web3TypeError(
                    "createFilter no longer supports setting filter argument options "
                    "for dynamic sized types. See the build_filter method for setting "
                    "filters with the match_any method."
                )

    @staticmethod
    def _process_get_logs_argument_filters(
        event_abi: ABIEvent,
        event_logs: Sequence[EventData],
        argument_filters: Optional[Dict[str, Any]],
    ) -> Iterable[EventData]:
        if (
            argument_filters is None
            or len(event_logs) == 0
            or
            # if no non-indexed args in argument filters, since indexed args are
            # filtered pre-call to ``eth_getLogs`` by building specific ``topics``.
            not any(
                not arg["indexed"]
                for arg in event_abi["inputs"]
                if arg["name"] in argument_filters
            )
        ):
            return event_logs

        filtered_logs_by_non_indexed_args = []

        for log in event_logs:
            match = False
            for arg, match_values in argument_filters.items():
                if not is_list_like(match_values):
                    match_values = [match_values]

                for abi_arg in event_abi["inputs"]:
                    if abi_arg["name"] == arg:
                        if (
                            # isolate ``string`` values to support substrings
                            abi_arg["type"] == "string"
                            and any(val in log["args"][arg] for val in match_values)
                            or (
                                # otherwise, do direct value comparison
                                abi_arg["type"] != "string"
                                and log["args"][arg] in match_values
                            )
                        ):
                            filtered_logs_by_non_indexed_args.append(log)
                            match = True
                            break
                if match:
                    break

        return filtered_logs_by_non_indexed_args

    @combomethod
    def _set_up_filter_builder(
        self,
        argument_filters: Optional[Dict[str, Any]] = None,
        from_block: Optional[BlockIdentifier] = None,
        to_block: BlockIdentifier = "latest",
        address: Optional[ChecksumAddress] = None,
        topics: Optional[Sequence[Any]] = None,
        filter_builder: Union[EventFilterBuilder, AsyncEventFilterBuilder] = None,
    ) -> None:
        if from_block is None:
            raise Web3TypeError(
                "Missing mandatory keyword argument to create_filter: `from_block`"
            )

        if argument_filters is None:
            argument_filters = dict()

        _filters = dict(**argument_filters)

        self.check_for_forbidden_api_filter_arguments(self.abi, _filters)

        _, event_filter_params = construct_event_filter_params(
            self.abi,
            self.w3.codec,
            contract_address=self.address,
            argument_filters=_filters,
            from_block=from_block,
            to_block=to_block,
            address=address,
            topics=topics,
        )

        filter_builder.address = cast(
            ChecksumAddress, event_filter_params.get("address")
        )
        filter_builder.from_block = event_filter_params.get("fromBlock")
        filter_builder.to_block = event_filter_params.get("toBlock")
        match_any_vals = {
            arg: value
            for arg, value in _filters.items()
            if not is_array_type(filter_builder.args[arg].arg_type)
            and is_list_like(value)
        }
        for arg, value in match_any_vals.items():
            filter_builder.args[arg].match_any(*value)

        match_single_vals = {
            arg: value
            for arg, value in _filters.items()
            if not is_array_type(filter_builder.args[arg].arg_type)
            and not is_list_like(value)
        }
        for arg, value in match_single_vals.items():
            filter_builder.args[arg].match_single(value)


class BaseContractEvents(Generic[TContractEvent]):
    """
    Class containing contract event objects

    This is available via:

    .. code-block:: python

        >>> mycontract.events
        <web3.contract.ContractEvents object at 0x108afde10>

    To get list of all supported events in the contract ABI.
    This allows you to iterate over :class:`ContractEvent` proxy classes.

    .. code-block:: python

        >>> for e in mycontract.events: print(e)
        <class 'web3._utils.datatypes.LogAnonymous'>
        ...

    """

    def __init__(
        self,
        abi: ABI,
        w3: Union["Web3", "AsyncWeb3"],
        contract_event_type: Type[TContractEvent],
        address: Optional[ChecksumAddress] = None,
    ) -> None:
        self.abi = abi
        self.w3 = w3
        self.address = address
        self.contract_event_type = contract_event_type
        _events: Sequence[ABIEvent] = None

        if self.abi:
            _events = sorted(
                filter_abi_by_type("event", self.abi),
                key=lambda evt: (evt["name"], len(evt.get("inputs", []))),
            )
            for event in _events:
                abi_signature = abi_to_signature(event)
                event_factory = contract_event_type.factory(
                    abi_signature,
                    w3=self.w3,
                    contract_abi=self.abi,
                    address=self.address,
                    abi=event,
                )

                # Set event name on instance if it does not already exist
                if event["name"] not in self.__dict__:
                    setattr(self, event["name"], event_factory)

                # Set underscore prefixed event signature on instance
                # Handles ambiguity in overloaded contract events
                setattr(self, f"_{abi_signature}", event_factory)

        if _events:
            self._events = _events

    def __hasattr__(self, event_name: str) -> bool:
        try:
            return event_name in self.__dict__["_events"]
        except ABIEventNotFound:
            return False

    def __getattr__(self, event_name: str) -> TContractEvent:
        if super().__getattribute__("abi") is None:
            raise NoABIFound(
                "There is no ABI found for this contract.",
            )
        elif "_events" not in self.__dict__ or len(self._events) == 0:
            raise NoABIEventsFound(
                "The abi for this contract contains no event definitions. ",
                "Are you sure you provided the correct contract abi?",
            )
        elif get_name_from_abi_element_identifier(event_name) not in [
            get_name_from_abi_element_identifier(event["name"])
            for event in self._events
        ]:
            raise ABIEventNotFound(
                f"The event '{event_name}' was not found in this contract's abi. ",
                "Are you sure you provided the correct contract abi?",
            )

        if "(" not in event_name:
            event_name = _get_any_abi_signature_with_name(event_name, self._events)
        else:
            event_name = f"_{event_name}"

        return super().__getattribute__(event_name)

    def __getitem__(self, event_name: str) -> TContractEvent:
        return getattr(self, event_name)

    def __iter__(self) -> Iterable[TContractEvent]:
        if not hasattr(self, "_events") or not self._events:
            return

        for event in self._events:
            yield self[abi_to_signature(event)]


class BaseContractFunction:
    """
    Base class for contract functions

    A function accessed via the api `contract.functions.myMethod(*args, **kwargs)`
    is a subclass of this class.
    """

    address: ChecksumAddress = None
    fn_name: str = None
    name: str = None
    signature: str = None
    abi_element_identifier: ABIElementIdentifier = None
    w3: Union["Web3", "AsyncWeb3"] = None
    contract_abi: ABI = None
    abi: ABIFunction = None
    transaction: TxParams = None
    arguments: Tuple[Any, ...] = None
    decode_tuples: Optional[bool] = None
    argument_names: Tuple[str, ...] = tuple()
    argument_types: Tuple[str, ...] = tuple()
    args: Any = None
    kwargs: Any = None

    def __init__(self, abi: Optional[ABIFunction] = None) -> None:
        if not self.abi_element_identifier:
            self.abi_element_identifier = type(self).__name__

        self.name = get_name_from_abi_element_identifier(self.abi_element_identifier)
        self.fn_name = self.name

        if abi:
            self.abi = abi

        self.signature = abi_to_signature(self.abi)

        event_inputs = self.abi.get("inputs", [])
        self.argument_names = tuple([input.get("name", None) for input in event_inputs])
        self.argument_types = tuple([input["type"] for input in event_inputs])

    @combomethod
    def _get_abi(cls) -> ABIFunction:
        if not cls.args and not cls.kwargs:
            # If no args or kwargs are provided, get the ABI element by name
            return cast(
                ABIFunction,
                get_abi_element(
                    cls.contract_abi,
                    get_abi_element_signature(cls.abi_element_identifier),
                    abi_codec=cls.w3.codec,
                ),
            )

        return cast(
            ABIFunction,
            get_abi_element(
                cls.contract_abi,
                get_name_from_abi_element_identifier(cls.abi_element_identifier),
                *cls.args,
                abi_codec=cls.w3.codec,
                **cls.kwargs,
            ),
        )

    def _set_function_info(self) -> None:
        self.selector = encode_hex(b"")
        if self.abi_element_identifier in [
            "fallback",
            "receive",
            FallbackFn,
            ReceiveFn,
        ]:
            self.selector = encode_hex(function_abi_to_4byte_selector(self.abi))
            self.arguments = None
        elif is_text(self.abi_element_identifier):
            self.selector = encode_hex(function_abi_to_4byte_selector(self.abi))
            self.arguments = get_normalized_abi_inputs(
                self.abi, *self.args, **self.kwargs
            )
        else:
            raise Web3TypeError("Unsupported function identifier")

    def _get_call_txparams(self, transaction: Optional[TxParams] = None) -> TxParams:
        if transaction is None:
            call_transaction: TxParams = {}
        else:
            call_transaction = cast(TxParams, dict(**transaction))

        if "data" in call_transaction:
            raise Web3ValueError("Cannot set 'data' field in call transaction")

        if self.address:
            call_transaction.setdefault("to", self.address)
        if self.w3.eth.default_account is not empty:
            call_transaction.setdefault(
                "from",
                cast(ChecksumAddress, self.w3.eth.default_account),
            )

        if "to" not in call_transaction:
            if isinstance(self, type):
                raise Web3ValueError(
                    "When using `Contract.[methodtype].[method].call()` from"
                    " a contract factory you "
                    "must provide a `to` address with the transaction"
                )
            else:
                raise Web3ValueError(
                    "Please ensure that this contract instance has an address."
                )

        return call_transaction

    def _transact(self, transaction: Optional[TxParams] = None) -> TxParams:
        if transaction is None:
            transact_transaction: TxParams = {}
        else:
            transact_transaction = cast(TxParams, dict(**transaction))

        if "data" in transact_transaction:
            raise Web3ValueError("Cannot set 'data' field in transact transaction")

        if self.address is not None:
            transact_transaction.setdefault("to", self.address)
        if self.w3.eth.default_account is not empty:
            transact_transaction.setdefault(
                "from", cast(ChecksumAddress, self.w3.eth.default_account)
            )

        if "to" not in transact_transaction:
            if isinstance(self, type):
                raise Web3ValueError(
                    "When using `Contract.transact` from a contract factory you "
                    "must provide a `to` address with the transaction"
                )
            else:
                raise Web3ValueError(
                    "Please ensure that this contract instance has an address."
                )
        return transact_transaction

    def _estimate_gas(self, transaction: Optional[TxParams] = None) -> TxParams:
        if transaction is None:
            estimate_gas_transaction: TxParams = {}
        else:
            estimate_gas_transaction = cast(TxParams, dict(**transaction))

        if "data" in estimate_gas_transaction:
            raise Web3ValueError("Cannot set 'data' field in estimate_gas transaction")
        if "to" in estimate_gas_transaction:
            raise Web3ValueError("Cannot set to in estimate_gas transaction")

        if self.address:
            estimate_gas_transaction.setdefault("to", self.address)
        if self.w3.eth.default_account is not empty:
            estimate_gas_transaction.setdefault(
                "from", cast(ChecksumAddress, self.w3.eth.default_account)
            )

        if "to" not in estimate_gas_transaction:
            if isinstance(self, type):
                raise Web3ValueError(
                    "When using `Contract.estimate_gas` from a contract factory "
                    "you must provide a `to` address with the transaction"
                )
            else:
                raise Web3ValueError(
                    "Please ensure that this contract instance has an address."
                )
        return estimate_gas_transaction

    def _build_transaction(self, transaction: Optional[TxParams] = None) -> TxParams:
        if transaction is None:
            built_transaction: TxParams = {}
        else:
            built_transaction = cast(TxParams, dict(**transaction))

        if "data" in built_transaction:
            raise Web3ValueError("Cannot set 'data' field in build transaction")

        if not self.address and "to" not in built_transaction:
            raise Web3ValueError(
                "When using `ContractFunction.build_transaction` from a contract "
                "factory you must provide a `to` address with the transaction"
            )
        if self.address and "to" in built_transaction:
            raise Web3ValueError(
                "Cannot set 'to' field in contract call build transaction"
            )

        if self.address:
            built_transaction.setdefault("to", self.address)

        if "to" not in built_transaction:
            raise Web3ValueError(
                "Please ensure that this contract instance has an address."
            )

        return built_transaction

    @combomethod
    def _encode_transaction_data(cls) -> HexStr:
        return add_0x_prefix(encode_abi(cls.w3, cls.abi, cls.arguments, cls.selector))

    _return_data_normalizers: Optional[Tuple[Callable[..., Any], ...]] = tuple()

    def __repr__(self) -> str:
        if self.abi:
            _repr = f"<Function {abi_to_signature(self.abi)}"
            if self.arguments is not None:
                _repr += f" bound to {self.arguments!r}"
            return _repr + ">"
        return f"<Function {get_abi_element_signature(self.abi_element_identifier)}>"

    def __call__(self, *args: Any, **kwargs: Any) -> Self:
        # When a function is called, check arguments to obtain the correct function
        # in the contract. self will be used if all args and kwargs are
        # encodable to self.abi, otherwise the correct function is obtained from
        # the contract.
        if (
            self.abi_element_identifier in [FallbackFn, ReceiveFn]
            or self.abi_element_identifier == "constructor"
        ):
            return copy_contract_function(self, *args, **kwargs)

        all_functions = cast(
            List[ABIFunction],
            filter_abi_by_type(
                "function",
                self.contract_abi,
            ),
        )
        # Filter functions by name to obtain function signatures
        function_name = get_name_from_abi_element_identifier(
            self.abi_element_identifier
        )
        function_abis = [
            function for function in all_functions if function["name"] == function_name
        ]
        num_args = len(args) + len(kwargs)
        function_abis_with_arg_count = cast(
            List[ABIFunction],
            _filter_by_argument_count(
                num_args,
                function_abis,
            ),
        )

        if not len(function_abis_with_arg_count):
            # Build an ABI without arguments to determine if one exists
            function_abis_with_arg_count = [
                ABIFunction({"type": "function", "name": function_name})
            ]

        function_abi_matches = []
        contract_function = None
        for abi in function_abis_with_arg_count:
            try:
                # Search for a function ABI that matches the arguments used
                function_abi_matches.append(
                    cast(
                        ABIFunction,
                        get_abi_element(
                            function_abis,
                            abi_to_signature(abi),
                            *args,
                            abi_codec=self.w3.codec,
                            **kwargs,
                        ),
                    )
                )
            except MismatchedABI:
                # ignore exceptions
                continue

        if len(function_abi_matches) == 1:
            function_abi = function_abi_matches[0]
            if abi_to_signature(self.abi) == abi_to_signature(function_abi):
                contract_function = self
            else:
                # Found a match that is not self
                contract_function = self.__class__.factory(
                    abi_to_signature(function_abi),
                    w3=self.w3,
                    contract_abi=self.contract_abi,
                    address=self.address,
                    abi_element_identifier=abi_to_signature(function_abi),
                    abi=function_abi,
                )
        else:
            for abi in function_abi_matches:
                if abi_to_signature(self.abi) == abi_to_signature(abi):
                    contract_function = self
                    break
            else:
                # Raise exception if multiple found
                raise MismatchedABI(
                    _mismatched_abi_error_diagnosis(
                        function_name,
                        self.contract_abi,
                        len(function_abi_matches),
                        num_args,
                        *args,
                        abi_codec=self.w3.codec,
                        **kwargs,
                    )
                )

        return copy_contract_function(contract_function, *args, **kwargs)

    @classmethod
    def factory(cls, class_name: str, **kwargs: Any) -> Self:
        return PropertyCheckingFactory(class_name, (cls,), kwargs)()

    def call(
        self,
        transaction: Optional[TxParams] = None,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[StateOverride] = None,
        ccip_read_enabled: Optional[bool] = None,
    ) -> Any:
        """
        Implementation of ``call`` should create a callable contract function
        and execute it using the `eth_call` interface.
        """
        raise NotImplementedError(
            "This method should be implemented in the inherited class"
        )


class BaseContractFunctions(Generic[TContractFn]):
    """Class containing contract function objects"""

    _functions: Sequence[ABIFunction] = None

    def __init__(
        self,
        abi: ABI,
        w3: Union["Web3", "AsyncWeb3"],
        contract_function_class: Type[TContractFn],
        address: Optional[ChecksumAddress] = None,
        decode_tuples: Optional[bool] = False,
    ) -> None:
        self.abi = abi
        self.w3 = w3
        self.address = address
        _functions: Sequence[ABIFunction] = None

        if self.abi:
            # Function with least number of inputs is first
            # This ensures ambiguity will always be deterministic
            # Prefer function without arguments if present, otherwise
            # just use the first available
            _functions = sorted(
                filter_abi_by_type("function", self.abi),
                key=lambda fn: (fn["name"], len(fn.get("inputs", []))),
            )
            for func in _functions:
                abi_signature = abi_to_signature(func)
                function_factory = contract_function_class.factory(
                    abi_signature,
                    w3=self.w3,
                    contract_abi=self.abi,
                    address=self.address,
                    decode_tuples=decode_tuples,
                    abi=func,
                )

                # Set function name on instance if it does not already exist
                if func["name"] not in self.__dict__:
                    setattr(self, func["name"], function_factory)

                # Set function signature on instance
                # Handles ambiguity in overloaded contract functions
                setattr(self, f"_{abi_signature}", function_factory)

        if _functions:
            self._functions = _functions

    def __hasattr__(self, function_name: str) -> bool:
        try:
            return function_name in self.__dict__["_functions"]
        except ABIFunctionNotFound:
            return False

    def __iter__(self) -> Iterable[TContractFn]:
        if not hasattr(self, "_functions") or not self._functions:
            return

        for func in self._functions:
            yield self[abi_to_signature(func)]

    def __getattr__(self, function_name: str) -> TContractFn:
        if super().__getattribute__("abi") is None:
            raise NoABIFound(
                "There is no ABI found for this contract.",
            )
        elif "_functions" not in self.__dict__ or len(self._functions) == 0:
            raise NoABIFunctionsFound(
                "The abi for this contract contains no function definitions. ",
                "Are you sure you provided the correct contract abi?",
            )
        elif get_name_from_abi_element_identifier(function_name) not in [
            get_name_from_abi_element_identifier(function["name"])
            for function in self._functions
        ]:
            raise ABIFunctionNotFound(
                f"The function '{function_name}' was not found in this ",
                "contract's abi.",
            )

        if "(" not in function_name:
            function_name = _get_any_abi_signature_with_name(
                function_name, self._functions
            )
        else:
            function_name = f"_{function_name}"

        return super().__getattribute__(
            function_name,
        )

    def __getitem__(self, function_name: str) -> TContractFn:
        return getattr(self, function_name)


class BaseContract:
    """
    Base class for Contract proxy classes.

    First you need to create your Contract classes using
    :meth:`web3.eth.Eth.contract` that takes compiled Solidity contract
    ABI definitions as input.  The created class object will be a subclass of
    this base class.

    After you have your Contract proxy class created you can interact with
    smart contracts

    * Create a Contract proxy object for an existing deployed smart contract by
      its address using :meth:`__init__`

    * Deploy a new smart contract using :py:meth:`Contract.constructor.transact()`
    """

    # set during class construction
    w3: Union["Web3", "AsyncWeb3"] = None

    # instance level properties
    address: ChecksumAddress = None

    # class properties (overridable at instance level)
    abi: ABI = None

    asm = None
    ast = None

    bytecode = None
    bytecode_runtime = None
    clone_bin = None

    decode_tuples = None
    dev_doc = None
    interface = None
    metadata = None
    opcodes = None
    src_map = None
    src_map_runtime = None
    user_doc = None

    #  Public API
    #
    @combomethod
    def encode_abi(
        cls,
        abi_element_identifier: str,
        args: Optional[Any] = None,
        kwargs: Optional[Any] = None,
        data: Optional[HexStr] = None,
    ) -> HexStr:
        """
        Encodes the arguments using the Ethereum ABI for the contract function
        that matches the given name and arguments.

        :param data: defaults to function selector
        """
        args = args or tuple()
        kwargs = kwargs or {}

        element_info = get_abi_element_info(
            cls.abi,
            abi_element_identifier,
            *args,
            abi_codec=cls.w3.codec,
            **kwargs,
        )

        if data is None:
            data = element_info["selector"]

        return encode_abi(cls.w3, element_info["abi"], element_info["arguments"], data)

    #
    # Functions API
    #
    @combomethod
    def all_functions(
        self,
    ) -> List["BaseContractFunction"]:
        """
        Return all functions in the contract.
        """
        return self.find_functions_by_identifier(
            self.abi, self.w3, self.address, lambda _: True
        )

    @combomethod
    def get_function_by_signature(self, signature: str) -> "BaseContractFunction":
        """
        Return a distinct function with matching signature.
        Raises a Web3ValueError if the signature is invalid or if there is no match or
        more than one is found.
        """
        if " " in signature:
            raise Web3ValueError(
                "Function signature should not contain any spaces. "
                f"Found spaces in input: {signature}"
            )

        def callable_check(fn_abi: ABIFunction) -> bool:
            return abi_to_signature(fn_abi) == signature

        fns = self.find_functions_by_identifier(
            self.abi, self.w3, self.address, callable_check
        )
        return self.get_function_by_identifier(fns, "signature")

    @combomethod
    def find_functions_by_name(self, fn_name: str) -> List["BaseContractFunction"]:
        """
        Return all functions with matching name.
        Raises a Web3ValueError if there is no match or more than one is found.
        """

        def callable_check(fn_abi: ABIFunction) -> bool:
            return fn_abi["name"] == fn_name

        return self.find_functions_by_identifier(
            self.abi, self.w3, self.address, callable_check
        )

    @combomethod
    def get_function_by_name(self, fn_name: str) -> "BaseContractFunction":
        """
        Return a distinct function with matching name.
        Raises a Web3ValueError if there is no match or more than one is found.
        """
        fns = self.find_functions_by_name(fn_name)
        return self.get_function_by_identifier(fns, "name")

    @combomethod
    def get_function_by_selector(
        self, selector: Union[bytes, int, HexStr]
    ) -> "BaseContractFunction":
        """
        Return a distinct function with matching 4byte selector.
        Raises a Web3ValueError if there is no match or more than one is found.
        """

        def callable_check(fn_abi: ABIFunction) -> bool:
            return encode_hex(function_abi_to_4byte_selector(fn_abi)) == to_4byte_hex(
                selector
            )

        fns = self.find_functions_by_identifier(
            self.abi, self.w3, self.address, callable_check
        )
        return self.get_function_by_identifier(fns, "selector")

    @combomethod
    def decode_function_input(
        self, data: HexStr
    ) -> Tuple["BaseContractFunction", Dict[str, Any]]:
        """
        Return a Tuple of the function selector and decoded arguments.
        """
        func = self.get_function_by_selector(HexBytes(data)[:4])
        arguments = decode_transaction_data(
            func.abi, data, normalizers=BASE_RETURN_NORMALIZERS
        )
        return func, arguments

    @combomethod
    def find_functions_by_args(self, *args: Any) -> "BaseContractFunction":
        """
        Return all functions with matching args, checking each argument can be encoded
        with the type.
        """

        def callable_check(fn_abi: ABIFunction) -> bool:
            return check_if_arguments_can_be_encoded(
                fn_abi,
                *args,
                abi_codec=self.w3.codec,
                **{},
            )

        return self.find_functions_by_identifier(
            self.abi, self.w3, self.address, callable_check
        )

    @combomethod
    def get_function_by_args(self, *args: Any) -> "BaseContractFunction":
        """
        Return a distinct function with matching args, checking each argument can be
        encoded with the type.
        Raises a Web3ValueError if there is no match or more than one is found.
        """
        fns = self.find_functions_by_args(*args)
        return self.get_function_by_identifier(fns, "args")

    #
    #  Events API
    #
    @combomethod
    def all_events(self) -> List["BaseContractEvent"]:
        """
        Return all events in the contract.
        """
        return self.find_events_by_identifier(
            self.abi, self.w3, self.address, lambda _: True
        )

    @combomethod
    def get_event_by_signature(self, signature: str) -> "BaseContractEvent":
        """
        Return a distinct event with matching signature.
        Raises a Web3ValueError if the signature is invalid or if there is no match or
        more than one is found.
        """

        def callable_check(event_abi: ABIEvent) -> bool:
            return abi_to_signature(event_abi) == signature.replace(" ", "")

        events = self.find_events_by_identifier(
            self.abi, self.w3, self.address, callable_check
        )
        return self.get_event_by_identifier(events, "signature")

    @combomethod
    def find_events_by_name(self, event_name: str) -> List["BaseContractEvent"]:
        """
        Return all events with matching name.
        Raises a Web3ValueError if there is no match or more than one is found.
        """

        def callable_check(fn_abi: ABIFunction) -> bool:
            return fn_abi["name"] == event_name

        return self.find_events_by_identifier(
            self.abi, self.w3, self.address, callable_check
        )

    @combomethod
    def get_event_by_name(self, event_name: str) -> "BaseContractEvent":
        """
        Return a distinct event with matching name.
        Raises a Web3ValueError if there is no match or more than one is found.
        """
        events = self.find_events_by_name(event_name)
        return self.get_event_by_identifier(events, "name")

    @combomethod
    def find_events_by_selector(
        self, selector: Union[bytes, int, HexStr]
    ) -> List["BaseContractEvent"]:
        """
        Return all events with matching selector.
        Raises a Web3ValueError if there is no match or more than one is found.
        """

        def callable_check(event_abi: ABIEvent) -> bool:
            return encode_hex(
                keccak(text=abi_to_signature(event_abi).replace(" ", ""))
            ) == encode_hex(hexstr_if_str(to_bytes, selector))

        return self.find_events_by_identifier(
            self.abi, self.w3, self.address, callable_check
        )

    @combomethod
    def get_event_by_selector(
        self, selector: Union[bytes, int, HexStr]
    ) -> "BaseContractEvent":
        """
        Return a distinct event with matching keccak selector.
        Raises a Web3ValueError if there is no match or more than one is found.
        """
        events = self.find_events_by_selector(selector)
        return self.get_event_by_identifier(events, "selector")

    @combomethod
    def find_events_by_topic(self, topic: HexStr) -> List["BaseContractEvent"]:
        """
        Return all events with matching topic.
        Raises a Web3ValueError if there is no match or more than one is found.
        """

        def callable_check(event_abi: ABIEvent) -> bool:
            return (
                encode_hex(keccak(text=abi_to_signature(event_abi).replace(" ", "")))
                == topic
            )

        return self.find_events_by_identifier(
            self.abi, self.w3, self.address, callable_check
        )

    @combomethod
    def get_event_by_topic(self, topic: HexStr) -> "BaseContractEvent":
        """
        Return a distinct event with matching topic.
        Raises a Web3ValueError if there is no match or more than one is found.
        """
        events = self.find_events_by_topic(topic)
        return self.get_event_by_identifier(events, "topic")

    @combomethod
    def find_functions_by_identifier(
        cls,
        contract_abi: ABI,
        w3: Union["Web3", "AsyncWeb3"],
        address: ChecksumAddress,
        callable_check: Callable[..., Any],
    ) -> List[Any]:
        raise NotImplementedError(
            "This method should be implemented in the inherited class"
        )

    @combomethod
    def get_function_by_identifier(
        cls, fns: Sequence["BaseContractFunction"], identifier: str
    ) -> "BaseContractFunction":
        raise NotImplementedError(
            "This method should be implemented in the inherited class"
        )

    @combomethod
    def find_events_by_identifier(
        cls,
        contract_abi: ABI,
        w3: Union["Web3", "AsyncWeb3"],
        address: ChecksumAddress,
        callable_check: Callable[..., Any],
    ) -> List[Any]:
        raise NotImplementedError(
            "This method should be implemented in the inherited class"
        )

    @combomethod
    def get_event_by_identifier(
        cls, fns: Sequence["BaseContractEvent"], identifier: str
    ) -> "BaseContractEvent":
        raise NotImplementedError(
            "This method should be implemented in the inherited class"
        )

    @staticmethod
    def get_fallback_function(
        abi: ABI,
        w3: Union["Web3", "AsyncWeb3"],
        function_type: Type["BaseContractFunction"],
        address: Optional[ChecksumAddress] = None,
    ) -> "BaseContractFunction":
        if abi and fallback_func_abi_exists(abi):
            fallback_abi = filter_abi_by_type("fallback", abi)[0]
            return function_type.factory(
                "fallback",
                w3=w3,
                contract_abi=abi,
                address=address,
                abi_element_identifier=FallbackFn,
                abi=fallback_abi,
            )()

        return cast(function_type, NonExistentFallbackFunction())  # type: ignore

    @staticmethod
    def get_receive_function(
        abi: ABI,
        w3: Union["Web3", "AsyncWeb3"],
        function_type: Type["BaseContractFunction"],
        address: Optional[ChecksumAddress] = None,
    ) -> "BaseContractFunction":
        if abi and receive_func_abi_exists(abi):
            receive_abi = filter_abi_by_type("receive", abi)[0]
            return function_type.factory(
                "receive",
                w3=w3,
                contract_abi=abi,
                address=address,
                abi_element_identifier=ReceiveFn,
                abi=receive_abi,
            )()

        return cast(function_type, NonExistentReceiveFunction())  # type: ignore

    #
    # Private Helpers
    #
    _return_data_normalizers: Tuple[Callable[..., Any], ...] = tuple()

    @classmethod
    def _prepare_transaction(
        cls,
        abi_element_identifier: ABIElementIdentifier,
        fn_args: Optional[Any] = None,
        fn_kwargs: Optional[Any] = None,
        transaction: Optional[TxParams] = None,
    ) -> TxParams:
        return prepare_transaction(
            cls.address,
            cls.w3,
            abi_element_identifier=abi_element_identifier,
            contract_abi=cls.abi,
            transaction=transaction,
            fn_args=fn_args,
            fn_kwargs=fn_kwargs,
        )

    @classmethod
    def _find_matching_fn_abi(
        cls,
        fn_identifier: Optional[ABIElementIdentifier] = None,
        *args: Sequence[Any],
        **kwargs: Dict[str, Any],
    ) -> ABIElement:
        if not args and not kwargs:
            fn_identifier = get_abi_element_signature(fn_identifier)

        return get_abi_element(
            cls.abi,
            fn_identifier,
            *args,
            abi_codec=cls.w3.codec,
            **kwargs,
        )

    @classmethod
    def _get_event_abi(
        cls,
        event_name: Optional[str] = None,
        argument_names: Optional[Sequence[str]] = None,
    ) -> ABIEvent:
        return cast(
            ABIEvent,
            get_abi_element(
                abi=cls.abi,
                abi_element_identifier=event_name,
                argument_names=argument_names,
            ),
        )

    @combomethod
    def _encode_constructor_data(
        cls, *args: Sequence[Any], **kwargs: Dict[str, Any]
    ) -> HexStr:
        constructor_abi = find_constructor_abi_element_by_type(cls.abi)

        if constructor_abi:
            arguments = get_normalized_abi_inputs(constructor_abi, *args, **kwargs)

            deploy_data = add_0x_prefix(
                encode_abi(cls.w3, constructor_abi, arguments, data=cls.bytecode)
            )
        else:
            if args or kwargs:
                msg = "Constructor args were provided, but no constructor function was provided."  # noqa: E501
                raise Web3TypeError(msg)

            deploy_data = to_hex(cls.bytecode)

        return deploy_data


class BaseContractCaller:
    """
    An alternative Contract API.

    This call:

    > contract.caller({'from': eth.accounts[1], 'gas': 100000, ...}).add(2, 3)
    is equivalent to this call in the classic contract:
    > contract.functions.add(2, 3).call({'from': eth.accounts[1], 'gas': 100000, ...})

    Other options for invoking this class include:

    > contract.caller.add(2, 3)

    or

    > contract.caller().add(2, 3)

    or

    > contract.caller(transaction={'from': eth.accounts[1], 'gas': 100000, ...}).add(2, 3)  # noqa: E501
    """

    # mypy types
    _functions: Sequence[ABIFunction]

    def __init__(
        self,
        abi: ABI,
        w3: Union["Web3", "AsyncWeb3"],
        address: ChecksumAddress,
        decode_tuples: Optional[bool] = False,
    ) -> None:
        self.w3 = w3
        self.address = address
        self.abi = abi
        self.decode_tuples = decode_tuples
        self._functions = []

    def __getattr__(self, function_name: str) -> Any:
        function_names = [
            get_name_from_abi_element_identifier(fn["name"])
            for fn in self._functions
            if fn.get("type") == "function"
        ]
        if self.abi is None:
            raise NoABIFound(
                "There is no ABI found for this contract.",
            )
        elif not self._functions or len(self._functions) == 0:
            raise NoABIFunctionsFound(
                "The ABI for this contract contains no function definitions. ",
                "Are you sure you provided the correct contract ABI?",
            )
        elif get_name_from_abi_element_identifier(function_name) not in function_names:
            functions_available = ", ".join(function_names)
            raise ABIFunctionNotFound(
                f"The function '{function_name}' was not found in this contract's ABI.",
                " Here is a list of all of the function names found: ",
                f"{functions_available}. ",
                "Did you mean to call one of those functions?",
            )
        else:
            function_identifier = function_name

            if "(" not in function_name:
                function_identifier = _get_any_abi_signature_with_name(
                    function_name, self._functions
                )
            return super().__getattribute__(function_identifier)

    def __hasattr__(self, function_name: str) -> bool:
        try:
            return function_name in self.__dict__["_functions"]
        except ABIFunctionNotFound:
            return False

    @staticmethod
    def call_function(
        fn: TContractFn,
        *args: Any,
        transaction: Optional[TxParams] = None,
        block_identifier: BlockIdentifier = None,
        ccip_read_enabled: Optional[bool] = None,
        **kwargs: Any,
    ) -> Any:
        if transaction is None:
            transaction = {}
        return fn(*args, **kwargs).call(
            transaction=transaction,
            block_identifier=block_identifier,
            ccip_read_enabled=ccip_read_enabled,
        )


class BaseContractConstructor:
    """
    Class for contract constructor API.
    """

    def __init__(
        self,
        w3: Union["Web3", "AsyncWeb3"],
        abi: ABI,
        bytecode: HexStr,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.w3 = w3
        self.abi = abi
        self.bytecode = bytecode
        self.data_in_transaction = self._encode_data_in_transaction(*args, **kwargs)

    @combomethod
    def _encode_data_in_transaction(self, *args: Any, **kwargs: Any) -> HexStr:
        constructor_abi = find_constructor_abi_element_by_type(self.abi)

        if constructor_abi:
            if not args:
                args = tuple()
            if not kwargs:
                kwargs = {}

            arguments = get_normalized_abi_inputs(constructor_abi, *args, **kwargs)

            data = add_0x_prefix(
                encode_abi(self.w3, constructor_abi, arguments, data=self.bytecode)
            )
        else:
            data = to_hex(self.bytecode)

        return data

    @combomethod
    def _estimate_gas(self, transaction: Optional[TxParams] = None) -> TxParams:
        if transaction is None:
            estimate_gas_transaction: TxParams = {}
        else:
            estimate_gas_transaction = cast(TxParams, dict(**transaction))
            self.check_forbidden_keys_in_transaction(
                estimate_gas_transaction, ["data", "to"]
            )

        if self.w3.eth.default_account is not empty:
            estimate_gas_transaction.setdefault(
                "from", cast(ChecksumAddress, self.w3.eth.default_account)
            )

        estimate_gas_transaction["data"] = self.data_in_transaction

        return estimate_gas_transaction

    def _get_transaction(self, transaction: Optional[TxParams] = None) -> TxParams:
        if transaction is None:
            transact_transaction: TxParams = {}
        else:
            transact_transaction = cast(TxParams, dict(**transaction))
            self.check_forbidden_keys_in_transaction(
                transact_transaction, ["data", "to"]
            )

        if self.w3.eth.default_account is not empty:
            transact_transaction.setdefault(
                "from", cast(ChecksumAddress, self.w3.eth.default_account)
            )

        transact_transaction["data"] = self.data_in_transaction

        return transact_transaction

    @combomethod
    def _build_transaction(self, transaction: Optional[TxParams] = None) -> TxParams:
        built_transaction = self._get_transaction(transaction)
        built_transaction["to"] = Address(b"")
        return built_transaction

    @staticmethod
    def check_forbidden_keys_in_transaction(
        transaction: TxParams, forbidden_keys: Optional[Collection[str]] = None
    ) -> None:
        keys_found = transaction.keys() & forbidden_keys
        if keys_found:
            raise Web3ValueError(
                f"Cannot set '{', '.join(keys_found)}' field(s) in transaction"
            )


class NonExistentFallbackFunction:
    @staticmethod
    def _raise_exception() -> NoReturn:
        raise ABIFallbackNotFound("No fallback function was found in the contract ABI.")

    def __getattr__(self, attr: Any) -> Callable[[], None]:
        return self._raise_exception


class NonExistentReceiveFunction:
    @staticmethod
    def _raise_exception() -> NoReturn:
        raise ABIReceiveNotFound("No receive function was found in the contract ABI.")

    def __getattr__(self, attr: Any) -> Callable[[], None]:
        return self._raise_exception
