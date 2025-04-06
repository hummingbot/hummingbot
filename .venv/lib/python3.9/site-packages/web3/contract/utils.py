import itertools
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

from eth_abi.exceptions import (
    DecodingError,
)
from eth_typing import (
    ABI,
    ABICallable,
    ABIFunction,
    ChecksumAddress,
    TypeStr,
)
from eth_utils.abi import (
    abi_to_signature,
    filter_abi_by_type,
    get_abi_output_types,
)
from eth_utils.toolz import (
    compose,
    curry,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.abi import (
    map_abi_data,
    named_tree,
    recursive_dict_to_namedtuple,
)
from web3._utils.async_transactions import (
    async_fill_transaction_defaults,
)
from web3._utils.compat import (
    TypeAlias,
)
from web3._utils.contracts import (
    prepare_transaction,
)
from web3._utils.normalizers import (
    BASE_RETURN_NORMALIZERS,
)
from web3._utils.transactions import (
    fill_transaction_defaults,
)
from web3.exceptions import (
    BadFunctionCallOutput,
    Web3ValueError,
)
from web3.types import (
    ABIElementIdentifier,
    BlockIdentifier,
    RPCEndpoint,
    StateOverride,
    TContractEvent,
    TContractFn,
    TxParams,
)
from web3.utils.abi import (
    get_abi_element,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )
    from web3.providers.persistent import (  # noqa: F401
        PersistentConnectionProvider,
    )

ACCEPTABLE_EMPTY_STRINGS = ["0x", b"0x", "", b""]


@curry
def format_contract_call_return_data_curried(
    async_w3: Union["AsyncWeb3", "Web3"],
    decode_tuples: bool,
    fn_abi: ABICallable,
    abi_element_identifier: ABIElementIdentifier,
    normalizers: Tuple[Callable[..., Any], ...],
    output_types: Sequence[TypeStr],
    return_data: Any,
) -> Any:
    """
    Helper function for formatting contract call return data for batch requests. Curry
    with all arguments except `return_data` and process `return_data` once it is
    available.
    """
    try:
        output_data = async_w3.codec.decode(output_types, return_data)
    except DecodingError as e:
        msg = (
            f"Could not decode contract function call to {abi_element_identifier} "
            f"with return data: {str(return_data)}, output_types: {output_types}"
        )
        raise BadFunctionCallOutput(msg) from e

    _normalizers = itertools.chain(
        BASE_RETURN_NORMALIZERS,
        normalizers,
    )
    normalized_data = map_abi_data(_normalizers, output_types, output_data)

    if decode_tuples and fn_abi["type"] == "function":
        decoded = named_tree(fn_abi["outputs"], normalized_data)
        normalized_data = recursive_dict_to_namedtuple(decoded)

    return normalized_data[0] if len(normalized_data) == 1 else normalized_data


def call_contract_function(
    w3: "Web3",
    address: ChecksumAddress,
    normalizers: Tuple[Callable[..., Any], ...],
    abi_element_identifier: ABIElementIdentifier,
    transaction: TxParams,
    block_id: Optional[BlockIdentifier] = None,
    contract_abi: Optional[ABI] = None,
    abi_callable: Optional[ABICallable] = None,
    state_override: Optional[StateOverride] = None,
    ccip_read_enabled: Optional[bool] = None,
    decode_tuples: Optional[bool] = False,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Helper function for interacting with a contract function using the
    `eth_call` API.
    """
    call_transaction = prepare_transaction(
        address,
        w3,
        abi_element_identifier=abi_element_identifier,
        contract_abi=contract_abi,
        abi_callable=abi_callable,
        transaction=transaction,
        fn_args=args,
        fn_kwargs=kwargs,
    )

    return_data = w3.eth.call(
        call_transaction,
        block_identifier=block_id,
        state_override=state_override,
        ccip_read_enabled=ccip_read_enabled,
    )

    if abi_callable is None:
        abi_callable = cast(
            ABIFunction,
            get_abi_element(
                contract_abi,
                abi_element_identifier,
                *args,
                abi_codec=w3.codec,
                **kwargs,
            ),
        )

    # get the output types, which only exist for function types
    output_types = []
    if abi_callable["type"] == "function":
        output_types = get_abi_output_types(abi_callable)

    provider = w3.provider
    if hasattr(provider, "_is_batching") and provider._is_batching:
        BatchingReturnData: TypeAlias = Tuple[Tuple[RPCEndpoint, Any], Tuple[Any, ...]]
        request_information = tuple(cast(BatchingReturnData, return_data))
        method_and_params = request_information[0]

        # append return data formatting to result formatters
        current_response_formatters = request_information[1]
        current_result_formatters = current_response_formatters[0]
        updated_result_formatters = compose(
            # contract call return data formatter
            format_contract_call_return_data_curried(
                w3,
                decode_tuples,
                abi_callable,
                abi_element_identifier,
                normalizers,
                output_types,
            ),
            current_result_formatters,
        )
        response_formatters = (
            updated_result_formatters,  # result formatters
            current_response_formatters[1],  # error formatters
            current_response_formatters[2],  # null result formatters
        )
        return (method_and_params, response_formatters)

    try:
        output_data = w3.codec.decode(output_types, return_data)
    except DecodingError as e:
        # Provide a more helpful error message than the one provided by
        # eth-abi-utils
        is_missing_code_error = (
            return_data in ACCEPTABLE_EMPTY_STRINGS
            and w3.eth.get_code(address) in ACCEPTABLE_EMPTY_STRINGS
        )
        if is_missing_code_error:
            msg = (
                "Could not transact with/call contract function, is contract "
                "deployed correctly and chain synced?"
            )
        else:
            msg = (
                f"Could not decode contract function call to {abi_element_identifier} "
                f"with return data: {str(return_data)}, output_types: {output_types}"
            )
        raise BadFunctionCallOutput(msg) from e

    _normalizers = itertools.chain(
        BASE_RETURN_NORMALIZERS,
        normalizers,
    )
    normalized_data = map_abi_data(_normalizers, output_types, output_data)

    if decode_tuples and abi_callable["type"] == "function":
        decoded = named_tree(abi_callable["outputs"], normalized_data)
        normalized_data = recursive_dict_to_namedtuple(decoded)

    if len(normalized_data) == 1:
        return normalized_data[0]
    else:
        return normalized_data


def transact_with_contract_function(
    address: ChecksumAddress,
    w3: "Web3",
    abi_element_identifier: Optional[ABIElementIdentifier] = None,
    transaction: Optional[TxParams] = None,
    contract_abi: Optional[ABI] = None,
    fn_abi: Optional[ABIFunction] = None,
    *args: Any,
    **kwargs: Any,
) -> HexBytes:
    """
    Helper function for interacting with a contract function by sending a
    transaction.
    """
    transact_transaction = prepare_transaction(
        address,
        w3,
        abi_element_identifier=abi_element_identifier,
        contract_abi=contract_abi,
        transaction=transaction,
        abi_callable=fn_abi,
        fn_args=args,
        fn_kwargs=kwargs,
    )

    txn_hash = w3.eth.send_transaction(transact_transaction)
    return txn_hash


def estimate_gas_for_function(
    address: ChecksumAddress,
    w3: "Web3",
    abi_element_identifier: Optional[ABIElementIdentifier] = None,
    transaction: Optional[TxParams] = None,
    contract_abi: Optional[ABI] = None,
    fn_abi: Optional[ABIFunction] = None,
    block_identifier: Optional[BlockIdentifier] = None,
    state_override: Optional[StateOverride] = None,
    *args: Any,
    **kwargs: Any,
) -> int:
    """
    Estimates gas cost a function call would take.

    Don't call this directly, instead use :meth:`Contract.estimate_gas`
    on your contract instance.
    """
    estimate_transaction = prepare_transaction(
        address,
        w3,
        abi_element_identifier=abi_element_identifier,
        contract_abi=contract_abi,
        abi_callable=fn_abi,
        transaction=transaction,
        fn_args=args,
        fn_kwargs=kwargs,
    )

    return w3.eth.estimate_gas(estimate_transaction, block_identifier, state_override)


def build_transaction_for_function(
    address: ChecksumAddress,
    w3: "Web3",
    abi_element_identifier: Optional[ABIElementIdentifier] = None,
    transaction: Optional[TxParams] = None,
    contract_abi: Optional[ABI] = None,
    fn_abi: Optional[ABIFunction] = None,
    *args: Any,
    **kwargs: Any,
) -> TxParams:
    """
    Builds a dictionary with the fields required to make the given transaction

    Don't call this directly, instead use :meth:`Contract.build_transaction`
    on your contract instance.
    """
    prepared_transaction = prepare_transaction(
        address,
        w3,
        abi_element_identifier=abi_element_identifier,
        contract_abi=contract_abi,
        abi_callable=fn_abi,
        transaction=transaction,
        fn_args=args,
        fn_kwargs=kwargs,
    )

    prepared_transaction = fill_transaction_defaults(w3, prepared_transaction)

    return prepared_transaction


def find_functions_by_identifier(
    contract_abi: ABI,
    w3: Union["Web3", "AsyncWeb3"],
    address: ChecksumAddress,
    callable_check: Callable[..., Any],
    function_type: Type[TContractFn],
) -> List[TContractFn]:
    """
    Given a contract ABI, return a list of TContractFunction instances.
    """
    fns_abi = sorted(
        filter_abi_by_type("function", contract_abi),
        key=lambda fn: (fn["name"], len(fn.get("inputs", []))),
    )
    return [
        function_type.factory(
            abi_to_signature(fn_abi),
            w3=w3,
            contract_abi=contract_abi,
            address=address,
            abi_element_identifier=abi_to_signature(fn_abi),
            abi=fn_abi,
        )
        for fn_abi in fns_abi
        if callable_check(fn_abi)
    ]


def get_function_by_identifier(
    fns: Sequence[TContractFn], identifier: str
) -> TContractFn:
    """
    Check that the provided list of TContractFunction instances contains one element and
    return it.
    """
    if len(fns) > 1:
        raise Web3ValueError(
            f"Found multiple functions with matching {identifier}. " f"Found: {fns!r}"
        )
    elif len(fns) == 0:
        raise Web3ValueError(f"Could not find any function with matching {identifier}")
    return fns[0]


def find_events_by_identifier(
    contract_abi: ABI,
    w3: Union["Web3", "AsyncWeb3"],
    address: ChecksumAddress,
    callable_check: Callable[..., Any],
    event_type: Type[TContractEvent],
) -> List[TContractEvent]:
    """
    Given a contract ABI, return a list of TContractEvent instances.
    """
    event_abis = filter_abi_by_type("event", contract_abi)
    return [
        event_type.factory(
            event_abi["name"],
            w3=w3,
            contract_abi=contract_abi,
            address=address,
            abi=event_abi,
        )
        for event_abi in event_abis
        if callable_check(event_abi)
    ]


def get_event_by_identifier(
    events: Sequence[TContractEvent], identifier: str
) -> TContractEvent:
    """
    Check that the provided list of TContractEvent instances contains one element and
    return it.
    """
    if len(events) > 1:
        raise Web3ValueError(
            f"Found multiple events with matching {identifier}. " f"Found: {events!r}"
        )
    elif len(events) == 0:
        raise Web3ValueError(f"Could not find any event with matching {identifier}")
    return events[0]


# --- async --- #


async def async_call_contract_function(
    async_w3: "AsyncWeb3",
    address: ChecksumAddress,
    normalizers: Tuple[Callable[..., Any], ...],
    abi_element_identifier: ABIElementIdentifier,
    transaction: TxParams,
    block_id: Optional[BlockIdentifier] = None,
    contract_abi: Optional[ABI] = None,
    fn_abi: Optional[ABIFunction] = None,
    state_override: Optional[StateOverride] = None,
    ccip_read_enabled: Optional[bool] = None,
    decode_tuples: Optional[bool] = False,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Helper function for interacting with a contract function using the
    `eth_call` API.
    """
    call_transaction = prepare_transaction(
        address,
        async_w3,
        abi_element_identifier=abi_element_identifier,
        contract_abi=contract_abi,
        abi_callable=fn_abi,
        transaction=transaction,
        fn_args=args,
        fn_kwargs=kwargs,
    )

    return_data = await async_w3.eth.call(
        call_transaction,
        block_identifier=block_id,
        state_override=state_override,
        ccip_read_enabled=ccip_read_enabled,
    )

    if fn_abi is None:
        fn_abi = cast(
            ABIFunction,
            get_abi_element(
                contract_abi,
                abi_element_identifier,
                *args,
                abi_codec=async_w3.codec,
                **kwargs,
            ),
        )

    # get the output types, which only exist for function types
    output_types = []
    if fn_abi["type"] == "function":
        output_types = get_abi_output_types(fn_abi)

    if async_w3.provider._is_batching:
        contract_call_return_data_formatter = format_contract_call_return_data_curried(
            async_w3,
            decode_tuples,
            fn_abi,
            abi_element_identifier,
            normalizers,
            output_types,
        )
        if async_w3.provider.has_persistent_connection:
            # get the current request id
            provider = cast("PersistentConnectionProvider", async_w3.provider)
            current_request_id = provider._batch_request_counter - 1
            provider._request_processor.append_result_formatter_for_request(
                current_request_id, contract_call_return_data_formatter
            )
        else:
            BatchingReturnData: TypeAlias = Tuple[
                Tuple[RPCEndpoint, Any], Tuple[Any, ...]
            ]
            request_information = tuple(cast(BatchingReturnData, return_data))
            method_and_params = request_information[0]

            # append return data formatter to result formatters
            current_response_formatters = request_information[1]
            current_result_formatters = current_response_formatters[0]
            updated_result_formatters = compose(
                contract_call_return_data_formatter,
                current_result_formatters,
            )
            response_formatters = (
                updated_result_formatters,  # result formatters
                current_response_formatters[1],  # error formatters
                current_response_formatters[2],  # null result formatters
            )
            return (method_and_params, response_formatters)

        return return_data

    try:
        output_data = async_w3.codec.decode(output_types, return_data)
    except DecodingError as e:
        # Provide a more helpful error message than the one provided by
        # eth-abi-utils
        is_missing_code_error = (
            return_data in ACCEPTABLE_EMPTY_STRINGS
            and await async_w3.eth.get_code(address) in ACCEPTABLE_EMPTY_STRINGS
        )
        if is_missing_code_error:
            msg = (
                "Could not transact with/call contract function, is contract "
                "deployed correctly and chain synced?"
            )
        else:
            msg = (
                f"Could not decode contract function call to {abi_element_identifier} "
                f"with return data: {str(return_data)}, output_types: {output_types}"
            )
        raise BadFunctionCallOutput(msg) from e

    _normalizers = itertools.chain(
        BASE_RETURN_NORMALIZERS,
        normalizers,
    )
    normalized_data = map_abi_data(_normalizers, output_types, output_data)

    if decode_tuples:
        decoded = named_tree(fn_abi["outputs"], normalized_data)
        normalized_data = recursive_dict_to_namedtuple(decoded)

    return normalized_data[0] if len(normalized_data) == 1 else normalized_data


async def async_transact_with_contract_function(
    address: ChecksumAddress,
    async_w3: "AsyncWeb3",
    abi_element_identifier: Optional[ABIElementIdentifier] = None,
    transaction: Optional[TxParams] = None,
    contract_abi: Optional[ABI] = None,
    fn_abi: Optional[ABIFunction] = None,
    *args: Any,
    **kwargs: Any,
) -> HexBytes:
    """
    Helper function for interacting with a contract function by sending a
    transaction.
    """
    transact_transaction = prepare_transaction(
        address,
        async_w3,
        abi_element_identifier=abi_element_identifier,
        contract_abi=contract_abi,
        transaction=transaction,
        abi_callable=fn_abi,
        fn_args=args,
        fn_kwargs=kwargs,
    )

    txn_hash = await async_w3.eth.send_transaction(transact_transaction)
    return txn_hash


async def async_estimate_gas_for_function(
    address: ChecksumAddress,
    async_w3: "AsyncWeb3",
    abi_element_identifier: Optional[ABIElementIdentifier] = None,
    transaction: Optional[TxParams] = None,
    contract_abi: Optional[ABI] = None,
    fn_abi: Optional[ABIFunction] = None,
    block_identifier: Optional[BlockIdentifier] = None,
    state_override: Optional[StateOverride] = None,
    *args: Any,
    **kwargs: Any,
) -> int:
    """
    Estimates gas cost a function call would take.

    Don't call this directly, instead use :meth:`Contract.estimate_gas`
    on your contract instance.
    """
    estimate_transaction = prepare_transaction(
        address,
        async_w3,
        abi_element_identifier=abi_element_identifier,
        contract_abi=contract_abi,
        abi_callable=fn_abi,
        transaction=transaction,
        fn_args=args,
        fn_kwargs=kwargs,
    )

    return await async_w3.eth.estimate_gas(
        estimate_transaction, block_identifier, state_override
    )


async def async_build_transaction_for_function(
    address: ChecksumAddress,
    async_w3: "AsyncWeb3",
    abi_element_identifier: Optional[ABIElementIdentifier] = None,
    transaction: Optional[TxParams] = None,
    contract_abi: Optional[ABI] = None,
    fn_abi: Optional[ABIFunction] = None,
    *args: Any,
    **kwargs: Any,
) -> TxParams:
    """
    Builds a dictionary with the fields required to make the given transaction

    Don't call this directly, instead use :meth:`Contract.build_transaction`
    on your contract instance.
    """
    prepared_transaction = prepare_transaction(
        address,
        async_w3,
        abi_element_identifier=abi_element_identifier,
        contract_abi=contract_abi,
        abi_callable=fn_abi,
        transaction=transaction,
        fn_args=args,
        fn_kwargs=kwargs,
    )

    return await async_fill_transaction_defaults(async_w3, prepared_transaction)
