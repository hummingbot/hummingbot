from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Collection,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from eth_abi.codec import (
    ABICodec,
)
from eth_abi.grammar import (
    parse as parse_type_string,
)
from eth_typing import (
    ABIEvent,
    ChecksumAddress,
    HexStr,
    TypeStr,
)
from eth_utils import (
    is_hex,
    is_list_like,
    is_string,
    is_text,
)
from eth_utils.curried import (
    apply_formatter_if,
)
from eth_utils.toolz import (
    complement,
    curry,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.events import (
    AsyncEventFilterBuilder,
    EventFilterBuilder,
    construct_event_data_set,
    construct_event_topic_set,
)
from web3._utils.validation import (
    validate_address,
)
from web3.exceptions import (
    Web3TypeError,
    Web3ValidationError,
    Web3ValueError,
)
from web3.types import (
    BlockIdentifier,
    FilterParams,
    LogReceipt,
    RPCEndpoint,
)

if TYPE_CHECKING:
    from web3.eth import AsyncEth  # noqa: F401
    from web3.eth import Eth  # noqa: F401


def construct_event_filter_params(
    event_abi: ABIEvent,
    abi_codec: ABICodec,
    contract_address: Optional[ChecksumAddress] = None,
    argument_filters: Optional[Dict[str, Any]] = None,
    topics: Optional[Sequence[HexStr]] = None,
    from_block: Optional[BlockIdentifier] = None,
    to_block: Optional[BlockIdentifier] = None,
    address: Optional[ChecksumAddress] = None,
) -> Tuple[List[List[Optional[HexStr]]], FilterParams]:
    filter_params: FilterParams = {}
    topic_set: Sequence[HexStr] = construct_event_topic_set(
        event_abi, abi_codec, argument_filters
    )

    if topics is not None:
        if len(topic_set) > 1:
            raise Web3TypeError(
                "Merging the topics argument with topics generated "
                "from argument_filters is not supported."
            )
        topic_set = topics

    filter_params["topics"] = topic_set

    if address and contract_address:
        if is_list_like(address):
            filter_params["address"] = [address] + [contract_address]
        elif is_string(address):
            filter_params["address"] = (
                [address, contract_address]
                if address != contract_address
                else [address]
            )
        else:
            raise Web3ValueError(
                f"Unsupported type for `address` parameter: {type(address)}"
            )
    elif address:
        filter_params["address"] = address
    elif contract_address:
        filter_params["address"] = contract_address

    if "address" not in filter_params:
        pass
    elif is_list_like(filter_params["address"]):
        for addr in filter_params["address"]:
            validate_address(addr)
    else:
        validate_address(filter_params["address"])

    if from_block is not None:
        filter_params["fromBlock"] = from_block

    if to_block is not None:
        filter_params["toBlock"] = to_block

    data_filters_set = construct_event_data_set(event_abi, abi_codec, argument_filters)

    return data_filters_set, filter_params


class BaseFilter:
    callbacks: List[Callable[..., Any]] = None
    stopped = False
    poll_interval = None
    filter_id = None

    def __init__(self, filter_id: HexStr) -> None:
        self.filter_id = filter_id
        self.callbacks = []
        super().__init__()

    def __str__(self) -> str:
        return f"Filter for {self.filter_id}"

    def format_entry(self, entry: LogReceipt) -> LogReceipt:
        """
        Hook for subclasses to change the format of the value that is passed
        into the callback functions.
        """
        return entry

    def is_valid_entry(self, entry: LogReceipt) -> bool:
        """
        Hook for subclasses to implement additional filtering layers.
        """
        return True

    def _filter_valid_entries(
        self, entries: Collection[LogReceipt]
    ) -> Iterator[LogReceipt]:
        return filter(self.is_valid_entry, entries)

    def _format_log_entries(
        self, log_entries: Optional[Iterator[LogReceipt]] = None
    ) -> List[LogReceipt]:
        if log_entries is None:
            return []

        formatted_log_entries = [
            self.format_entry(log_entry) for log_entry in log_entries
        ]
        return formatted_log_entries


class Filter(BaseFilter):
    def __init__(self, filter_id: HexStr, eth_module: "Eth") -> None:
        self.eth_module = eth_module
        super().__init__(filter_id)

    def get_new_entries(self) -> List[LogReceipt]:
        log_entries = self._filter_valid_entries(
            self.eth_module.get_filter_changes(self.filter_id)
        )
        return self._format_log_entries(log_entries)

    def get_all_entries(self) -> List[LogReceipt]:
        log_entries = self._filter_valid_entries(
            self.eth_module.get_filter_logs(self.filter_id)
        )
        return self._format_log_entries(log_entries)


class AsyncFilter(BaseFilter):
    def __init__(self, filter_id: HexStr, eth_module: "AsyncEth") -> None:
        self.eth_module = eth_module
        super().__init__(filter_id)

    async def get_new_entries(self) -> List[LogReceipt]:
        filter_changes = await self.eth_module.get_filter_changes(self.filter_id)
        log_entries = self._filter_valid_entries(filter_changes)
        return self._format_log_entries(log_entries)

    async def get_all_entries(self) -> List[LogReceipt]:
        filter_logs = await self.eth_module.get_filter_logs(self.filter_id)
        log_entries = self._filter_valid_entries(filter_logs)
        return self._format_log_entries(log_entries)


class BlockFilter(Filter):
    pass


class AsyncBlockFilter(AsyncFilter):
    pass


class TransactionFilter(Filter):
    pass


class AsyncTransactionFilter(AsyncFilter):
    pass


class LogFilter(Filter):
    data_filter_set = None
    data_filter_set_regex = None
    data_filter_set_function = None
    log_entry_formatter = None
    filter_params: FilterParams = None
    builder: EventFilterBuilder = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.log_entry_formatter = kwargs.pop(
            "log_entry_formatter",
            self.log_entry_formatter,
        )
        if "data_filter_set" in kwargs:
            self.set_data_filters(kwargs.pop("data_filter_set"))
        super().__init__(*args, **kwargs)

    def format_entry(self, entry: LogReceipt) -> LogReceipt:
        if self.log_entry_formatter:
            return self.log_entry_formatter(entry)
        return entry

    def set_data_filters(
        self, data_filter_set: Collection[Tuple[TypeStr, Any]]
    ) -> None:
        """
        Sets the data filters (non indexed argument filters)

        Expects a set of tuples with the type and value, e.g.:
        (('uint256', [12345, 54321]), ('string', ('a-single-string',)))
        """
        self.data_filter_set = data_filter_set
        if any(data_filter_set):
            self.data_filter_set_function = match_fn(
                self.eth_module.codec, data_filter_set
            )

    def is_valid_entry(self, entry: LogReceipt) -> bool:
        if not self.data_filter_set:
            return True
        return bool(self.data_filter_set_function(entry["data"]))


class AsyncLogFilter(AsyncFilter):
    data_filter_set = None
    data_filter_set_regex = None
    data_filter_set_function = None
    log_entry_formatter = None
    filter_params: FilterParams = None
    builder: AsyncEventFilterBuilder = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.log_entry_formatter = kwargs.pop(
            "log_entry_formatter",
            self.log_entry_formatter,
        )
        if "data_filter_set" in kwargs:
            self.set_data_filters(kwargs.pop("data_filter_set"))
        super().__init__(*args, **kwargs)

    def format_entry(self, entry: LogReceipt) -> LogReceipt:
        if self.log_entry_formatter:
            return self.log_entry_formatter(entry)
        return entry

    def set_data_filters(
        self, data_filter_set: Collection[Tuple[TypeStr, Any]]
    ) -> None:
        """
        Sets the data filters (non indexed argument filters)

        Expects a set of tuples with the type and value, e.g.:
        (('uint256', [12345, 54321]), ('string', ('a-single-string',)))
        """
        self.data_filter_set = data_filter_set
        if any(data_filter_set):
            self.data_filter_set_function = match_fn(
                self.eth_module.codec, data_filter_set
            )

    def is_valid_entry(self, entry: LogReceipt) -> bool:
        if not self.data_filter_set:
            return True
        return bool(self.data_filter_set_function(entry["data"]))


def decode_utf8_bytes(value: bytes) -> str:
    return value.decode("utf-8")


not_text = complement(is_text)
normalize_to_text = apply_formatter_if(not_text, decode_utf8_bytes)


def normalize_data_values(type_string: TypeStr, data_value: Any) -> Any:
    """
    Decodes utf-8 bytes to strings for abi string values.

    eth-abi v1 returns utf-8 bytes for string values.
    This can be removed once eth-abi v2 is required.
    """
    _type = parse_type_string(type_string)
    if _type.base == "string":
        if _type.arrlist is not None:
            return tuple(normalize_to_text(value) for value in data_value)
        else:
            return normalize_to_text(data_value)
    return data_value


@curry
def match_fn(
    codec: ABICodec, match_values_and_abi: Collection[Tuple[str, Any]], data: Any
) -> bool:
    """
    Match function used for filtering non-indexed event arguments.

    Values provided through the match_values_and_abi parameter are
    compared to the abi decoded log data.
    """
    abi_types, all_match_values = zip(*match_values_and_abi)

    decoded_values = codec.decode(abi_types, HexBytes(data))
    for data_value, match_values, abi_type in zip(
        decoded_values, all_match_values, abi_types
    ):
        if match_values is None:
            continue
        normalized_data = normalize_data_values(abi_type, data_value)
        for value in match_values:
            if not codec.is_encodable(abi_type, value):
                raise Web3ValueError(
                    f"Value {value} is of the wrong abi type. "
                    f"Expected {abi_type} typed value."
                )
            if value == normalized_data:
                break
        else:
            return False

    return True


class _UseExistingFilter(Exception):
    """
    Internal exception, raised when a filter_id is passed into w3.eth.filter()
    """

    def __init__(self, filter_id: Union[str, FilterParams, HexStr]) -> None:
        self.filter_id = filter_id


@curry
def select_filter_method(
    value: Union[str, FilterParams, HexStr],
    if_new_block_filter: RPCEndpoint,
    if_new_pending_transaction_filter: RPCEndpoint,
    if_new_filter: RPCEndpoint,
) -> Optional[RPCEndpoint]:
    if is_string(value):
        if value == "latest":
            return if_new_block_filter
        elif value == "pending":
            return if_new_pending_transaction_filter
        elif is_hex(value):
            raise _UseExistingFilter(value)
        else:
            raise Web3ValidationError(
                "Filter argument needs to be either 'latest',"
                " 'pending', or a hex-encoded filter_id. Filter argument"
                f" is: {value}"
            )
    elif isinstance(value, dict):
        return if_new_filter
    else:
        raise Web3ValidationError(
            "Filter argument needs to be either the string "
            "'pending' or 'latest', a filter_id, "
            f"or a filter params dictionary. Filter argument is: {value}"
        )
