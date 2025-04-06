from abc import (
    ABC,
    abstractmethod,
)
from enum import (
    Enum,
)
import itertools
from typing import (
    TYPE_CHECKING,
    Any,
    Collection,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from eth_abi import (
    grammar,
)
from eth_abi.codec import (
    ABICodec,
)
from eth_typing import (
    ABIComponent,
    ABIComponentIndexed,
    ABIEvent,
    ChecksumAddress,
    HexStr,
    Primitives,
    TypeStr,
)
from eth_utils import (
    encode_hex,
    is_list_like,
    keccak,
    to_bytes,
    to_dict,
    to_hex,
    to_tuple,
)
from eth_utils.abi import (
    collapse_if_tuple,
    event_abi_to_log_topic,
    get_abi_input_names,
)
from eth_utils.curried import (
    apply_formatter_if,
)
from eth_utils.toolz import (
    complement,
    compose,
    cons,
    curry,
    valfilter,
)

import web3
from web3._utils.abi import (
    exclude_indexed_event_inputs,
    get_indexed_event_inputs,
    map_abi_data,
    named_tree,
    normalize_event_input_types,
)
from web3._utils.encoding import (
    encode_single_packed,
    hexstr_if_str,
)
from web3._utils.normalizers import (
    BASE_RETURN_NORMALIZERS,
)
from web3.datastructures import (
    AttributeDict,
)
from web3.exceptions import (
    InvalidEventABI,
    LogTopicError,
    Web3ValueError,
)
from web3.types import (
    BlockIdentifier,
    EventData,
    FilterParams,
    LogReceipt,
)
from web3.utils.abi import (
    get_event_log_topics,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )
    from web3._utils.filters import (  # noqa: F401
        AsyncLogFilter,
        LogFilter,
    )


def _log_entry_data_to_bytes(
    log_entry_data: Union[Primitives, HexStr, str],
) -> bytes:
    return hexstr_if_str(to_bytes, log_entry_data)


def construct_event_topic_set(
    event_abi: ABIEvent,
    abi_codec: ABICodec,
    arguments: Optional[Union[List[Any], Tuple[Any], Dict[str, Any]]] = None,
) -> List[HexStr]:
    if arguments is None:
        arguments = {}
    elif isinstance(arguments, (list, tuple)):
        if len(arguments) != len(event_abi["inputs"]):
            raise Web3ValueError(
                "When passing an argument list, the number of arguments must "
                "match the event constructor."
            )
        arguments = {
            arg["name"]: [arg_value]
            for arg, arg_value in zip(event_abi["inputs"], arguments)
        }
    normalized_args = {
        key: value if is_list_like(value) else [value]
        for key, value in arguments.items()
    }

    event_topic = encode_hex(event_abi_to_log_topic(event_abi))
    indexed_args = get_indexed_event_inputs(event_abi)
    zipped_abi_and_args = [
        (arg, normalized_args.get(arg["name"], [None])) for arg in indexed_args
    ]
    encoded_args = [
        [
            (
                None
                if option is None
                else encode_hex(abi_codec.encode([arg["type"]], [option]))
            )
            for option in arg_options
        ]
        for arg, arg_options in zipped_abi_and_args
    ]

    topics = list(normalize_topic_list([event_topic] + encoded_args))
    return topics


def construct_event_data_set(
    event_abi: ABIEvent,
    abi_codec: ABICodec,
    arguments: Optional[Union[Sequence[Any], Dict[str, Any]]] = None,
) -> List[List[Optional[HexStr]]]:
    if arguments is None:
        arguments = {}
    if isinstance(arguments, (list, tuple)):
        if len(arguments) != len(event_abi["inputs"]):
            raise Web3ValueError(
                "When passing an argument list, the number of arguments must "
                "match the event constructor."
            )
        arguments = {
            arg["name"]: [arg_value]
            for arg, arg_value in zip(event_abi["inputs"], arguments)
        }

    normalized_args = {
        key: value if is_list_like(value) else [value]
        # type ignored b/c at this point arguments is always a dict
        for key, value in arguments.items()  # type: ignore
    }

    non_indexed_args = exclude_indexed_event_inputs(event_abi)
    zipped_abi_and_args = [
        (arg, normalized_args.get(arg["name"], [None])) for arg in non_indexed_args
    ]
    encoded_args = [
        [
            (
                None
                if option is None
                else encode_hex(abi_codec.encode([arg["type"]], [option]))
            )
            for option in arg_options
        ]
        for arg, arg_options in zipped_abi_and_args
    ]

    data = [
        list(permutation) if any(value is not None for value in permutation) else []
        for permutation in itertools.product(*encoded_args)
    ]
    return data


def is_dynamic_sized_type(type_str: TypeStr) -> bool:
    abi_type = grammar.parse(type_str)
    return abi_type.is_dynamic


@to_tuple
def get_event_abi_types_for_decoding(
    event_inputs: Sequence[Union[ABIComponent, ABIComponentIndexed]],
) -> Iterable[TypeStr]:
    """
    Event logs use the `keccak(value)` for indexed inputs of type `bytes` or
    `string`.  Because of this we need to modify the types so that we can
    decode the log entries using the correct types.
    """
    for input_abi in event_inputs:
        if input_abi.get("indexed") and is_dynamic_sized_type(input_abi["type"]):
            yield "bytes32"
        else:
            yield collapse_if_tuple(input_abi)


@curry
def get_event_data(
    abi_codec: ABICodec,
    event_abi: ABIEvent,
    log_entry: LogReceipt,
) -> EventData:
    """
    Given an event ABI and a log entry for that event, return the decoded
    event data
    """
    log_topics = get_event_log_topics(event_abi, log_entry["topics"])
    log_topics_bytes = [_log_entry_data_to_bytes(topic) for topic in log_topics]
    log_topics_abi = get_indexed_event_inputs(event_abi)
    log_topic_normalized_inputs = normalize_event_input_types(log_topics_abi)
    log_topic_types = get_event_abi_types_for_decoding(log_topic_normalized_inputs)
    log_topic_names = get_abi_input_names(
        ABIEvent({"name": event_abi["name"], "type": "event", "inputs": log_topics_abi})
    )

    if len(log_topics_bytes) != len(log_topic_types):
        raise LogTopicError(
            f"Expected {len(log_topic_types)} log topics.  Got {len(log_topics_bytes)}"
        )

    log_data = _log_entry_data_to_bytes(log_entry["data"])
    log_data_abi = exclude_indexed_event_inputs(event_abi)
    log_data_normalized_inputs = normalize_event_input_types(log_data_abi)
    log_data_types = get_event_abi_types_for_decoding(log_data_normalized_inputs)
    log_data_names = get_abi_input_names(
        ABIEvent({"name": event_abi["name"], "type": "event", "inputs": log_data_abi})
    )

    # sanity check that there are not name intersections between the topic
    # names and the data argument names.
    duplicate_names = set(log_topic_names).intersection(log_data_names)
    if duplicate_names:
        raise InvalidEventABI(
            "The following argument names are duplicated "
            f"between event inputs: '{', '.join(duplicate_names)}'"
        )

    decoded_log_data = abi_codec.decode(log_data_types, log_data)
    normalized_log_data = map_abi_data(
        BASE_RETURN_NORMALIZERS, log_data_types, decoded_log_data
    )
    named_log_data = named_tree(
        log_data_normalized_inputs,
        normalized_log_data,
    )

    decoded_topic_data = [
        abi_codec.decode([topic_type], topic_data)[0]
        for topic_type, topic_data in zip(log_topic_types, log_topics_bytes)
    ]
    normalized_topic_data = map_abi_data(
        BASE_RETURN_NORMALIZERS, log_topic_types, decoded_topic_data
    )

    event_args = dict(
        itertools.chain(
            zip(log_topic_names, normalized_topic_data),
            named_log_data.items(),
        )
    )

    event_data = EventData(
        args=event_args,
        event=event_abi["name"],
        logIndex=log_entry["logIndex"],
        transactionIndex=log_entry["transactionIndex"],
        transactionHash=log_entry["transactionHash"],
        address=log_entry["address"],
        blockHash=log_entry["blockHash"],
        blockNumber=log_entry["blockNumber"],
    )

    if isinstance(log_entry, AttributeDict):
        return cast(EventData, AttributeDict.recursive(event_data))

    return event_data


@to_tuple
def pop_singlets(seq: Sequence[Any]) -> Iterable[Any]:
    yield from (i[0] if is_list_like(i) and len(i) == 1 else i for i in seq)


@curry
def remove_trailing_from_seq(
    seq: Sequence[Any], remove_value: Optional[Any] = None
) -> Sequence[Any]:
    index = len(seq)
    while index > 0 and seq[index - 1] == remove_value:
        index -= 1
    return seq[:index]


normalize_topic_list = compose(
    remove_trailing_from_seq(remove_value=None),
    pop_singlets,
)


def is_indexed(arg: Any) -> bool:
    if isinstance(arg, TopicArgumentFilter):
        return True
    return False


is_not_indexed = complement(is_indexed)


class BaseEventFilterBuilder:
    formatter = None
    _from_block = None
    _to_block = None
    _address = None
    _immutable = False

    def __init__(
        self,
        event_abi: ABIEvent,
        abi_codec: ABICodec,
        formatter: Optional[EventData] = None,
    ) -> None:
        self.event_abi = event_abi
        self.abi_codec = abi_codec
        self.formatter = formatter
        self.event_topic = initialize_event_topics(self.event_abi)
        self.args = AttributeDict(
            _build_argument_filters_from_event_abi(event_abi, abi_codec)
        )
        self._ordered_arg_names = tuple(arg["name"] for arg in event_abi["inputs"])

    @property
    def from_block(self) -> BlockIdentifier:
        return self._from_block

    @from_block.setter
    def from_block(self, value: BlockIdentifier) -> None:
        if self._from_block is None and not self._immutable:
            self._from_block = value
        else:
            raise Web3ValueError(
                f"from_block is already set to {self._from_block!r}. "
                "Resetting filter parameters is not permitted"
            )

    @property
    def to_block(self) -> BlockIdentifier:
        return self._to_block

    @to_block.setter
    def to_block(self, value: BlockIdentifier) -> None:
        if self._to_block is None and not self._immutable:
            self._to_block = value
        else:
            raise Web3ValueError(
                f"toBlock is already set to {self._to_block!r}. "
                "Resetting filter parameters is not permitted"
            )

    @property
    def address(self) -> ChecksumAddress:
        return self._address

    @address.setter
    def address(self, value: ChecksumAddress) -> None:
        if self._address is None and not self._immutable:
            self._address = value
        else:
            raise Web3ValueError(
                f"address is already set to {self.address!r}. "
                "Resetting filter parameters is not permitted"
            )

    @property
    def ordered_args(self) -> Tuple[Any, ...]:
        return tuple(map(self.args.__getitem__, self._ordered_arg_names))

    @property
    @to_tuple
    def indexed_args(self) -> Tuple[Any, ...]:
        return tuple(filter(is_indexed, self.ordered_args))

    @property
    @to_tuple
    def data_args(self) -> Tuple[Any, ...]:
        return tuple(filter(is_not_indexed, self.ordered_args))

    @property
    def topics(self) -> List[HexStr]:
        arg_topics = tuple(arg.match_values for arg in self.indexed_args)
        return normalize_topic_list(cons(to_hex(self.event_topic), arg_topics))

    @property
    def data_argument_values(self) -> Tuple[Any, ...]:
        if self.data_args is not None:
            return tuple(arg.match_values for arg in self.data_args)
        else:
            return (None,)

    @property
    def filter_params(self) -> FilterParams:
        params = {
            "topics": self.topics,
            "fromBlock": self.from_block,
            "toBlock": self.to_block,
            "address": self.address,
        }
        return valfilter(lambda x: x is not None, params)


class EventFilterBuilder(BaseEventFilterBuilder):
    def deploy(self, w3: "Web3") -> "LogFilter":
        if not isinstance(w3, web3.Web3):
            raise Web3ValueError(f"Invalid web3 argument: got: {w3!r}")

        for arg in self.args.values():
            arg._immutable = True
        self._immutable = True

        log_filter = cast("LogFilter", w3.eth.filter(self.filter_params))
        log_filter.filter_params = self.filter_params
        log_filter.set_data_filters(self.data_argument_values)
        log_filter.builder = self
        if self.formatter is not None:
            log_filter.log_entry_formatter = self.formatter
        return log_filter


class AsyncEventFilterBuilder(BaseEventFilterBuilder):
    async def deploy(self, async_w3: "AsyncWeb3") -> "AsyncLogFilter":
        if not isinstance(async_w3, web3.AsyncWeb3):
            raise Web3ValueError(f"Invalid web3 argument: got: {async_w3!r}")

        for arg in self.args.values():
            arg._immutable = True
        self._immutable = True

        log_filter = await async_w3.eth.filter(self.filter_params)
        log_filter = cast("AsyncLogFilter", log_filter)
        log_filter.filter_params = self.filter_params
        log_filter.set_data_filters(self.data_argument_values)
        log_filter.builder = self
        if self.formatter is not None:
            log_filter.log_entry_formatter = self.formatter
        return log_filter


def initialize_event_topics(event_abi: ABIEvent) -> Union[bytes, List[Any]]:
    if event_abi["anonymous"] is False:
        return event_abi_to_log_topic(event_abi)
    else:
        return list()


@to_dict
def _build_argument_filters_from_event_abi(
    event_abi: ABIEvent, abi_codec: ABICodec
) -> Iterable[Tuple[str, "BaseArgumentFilter"]]:
    for item in event_abi["inputs"]:
        key = item["name"]
        value: "BaseArgumentFilter"
        if item.get("indexed") is True:
            value = TopicArgumentFilter(
                abi_codec=abi_codec, arg_type=collapse_if_tuple(item)
            )
        else:
            value = DataArgumentFilter(arg_type=collapse_if_tuple(item))
        yield key, value


array_to_tuple = apply_formatter_if(is_list_like, tuple)


@to_tuple
def _normalize_match_values(match_values: Collection[Any]) -> Iterable[Any]:
    for value in match_values:
        yield array_to_tuple(value)


class BaseArgumentFilter(ABC):
    _match_values: Tuple[Any, ...] = None
    _immutable = False

    def __init__(self, arg_type: TypeStr) -> None:
        self.arg_type = arg_type

    def match_single(self, value: Any) -> None:
        if self._immutable:
            raise Web3ValueError(
                "Setting values is forbidden after filter is deployed."
            )
        if self._match_values is None:
            self._match_values = _normalize_match_values((value,))
        else:
            raise Web3ValueError("An argument match value/s has already been set.")

    def match_any(self, *values: Collection[Any]) -> None:
        if self._immutable:
            raise Web3ValueError(
                "Setting values is forbidden after filter is deployed."
            )
        if self._match_values is None:
            self._match_values = _normalize_match_values(values)
        else:
            raise Web3ValueError("An argument match value/s has already been set.")

    @property
    @abstractmethod
    def match_values(self) -> None:
        pass


class DataArgumentFilter(BaseArgumentFilter):
    # type ignore b/c conflict with BaseArgumentFilter.match_values type
    @property
    def match_values(self) -> Tuple[TypeStr, Tuple[Any, ...]]:  # type: ignore
        return self.arg_type, self._match_values


class TopicArgumentFilter(BaseArgumentFilter):
    def __init__(self, arg_type: TypeStr, abi_codec: ABICodec) -> None:
        self.abi_codec = abi_codec
        self.arg_type = arg_type

    @to_tuple
    def _get_match_values(self) -> Iterable[HexStr]:
        yield from (self._encode(value) for value in self._match_values)

    # type ignore b/c conflict with BaseArgumentFilter.match_values type
    @property
    def match_values(self) -> Optional[Tuple[HexStr, ...]]:  # type: ignore
        if self._match_values is not None:
            return self._get_match_values()
        else:
            return None

    def _encode(self, value: Any) -> HexStr:
        if is_dynamic_sized_type(self.arg_type):
            return to_hex(keccak(encode_single_packed(self.arg_type, value)))
        else:
            return to_hex(self.abi_codec.encode([self.arg_type], [value]))


class EventLogErrorFlags(Enum):
    Discard = "discard"
    Ignore = "ignore"
    Strict = "strict"
    Warn = "warn"

    @classmethod
    def flag_options(self) -> List[str]:
        return [key.upper() for key in self.__members__.keys()]
