import binascii
from collections import (
    abc,
    namedtuple,
)
import copy
import itertools
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Collection,
    Coroutine,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

from eth_abi import (
    decoding,
    encoding,
)
from eth_abi.base import (
    parse_type_str,
)
from eth_abi.exceptions import (
    ValueOutOfBounds,
)
from eth_abi.grammar import (
    ABIType,
    BasicType,
    TupleType,
    parse,
)
from eth_abi.registry import (
    ABIRegistry,
    BaseEquals,
    registry as default_registry,
)
from eth_typing import (
    ABI,
    ABIComponent,
    ABIComponentIndexed,
    ABIConstructor,
    ABIElement,
    ABIEvent,
    ABIFallback,
    ABIFunction,
    ABIReceive,
    HexStr,
    TypeStr,
)
from eth_utils import (
    collapse_if_tuple,
    decode_hex,
    filter_abi_by_type,
    get_abi_input_names,
    get_abi_input_types,
    is_bytes,
    is_list_like,
    is_string,
    is_text,
    to_text,
    to_tuple,
)
from eth_utils.toolz import (
    curry,
    partial,
    pipe,
)

from web3._utils.abi_element_identifiers import (
    FallbackFn,
    ReceiveFn,
)
from web3._utils.decorators import (
    reject_recursive_repeats,
)
from web3._utils.ens import (
    is_ens_name,
)
from web3._utils.formatters import (
    recursive_map,
)
from web3.exceptions import (
    MismatchedABI,
    Web3AttributeError,
    Web3TypeError,
    Web3ValueError,
)
from web3.types import (
    ABIElementIdentifier,
    TReturn,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
    )


def fallback_func_abi_exists(contract_abi: ABI) -> Sequence[ABIFallback]:
    return filter_abi_by_type("fallback", contract_abi)


def receive_func_abi_exists(contract_abi: ABI) -> Sequence[ABIReceive]:
    return filter_abi_by_type("receive", contract_abi)


def get_indexed_event_inputs(event_abi: ABIEvent) -> Sequence[ABIComponentIndexed]:
    return [arg for arg in event_abi["inputs"] if arg["indexed"] is True]


def exclude_indexed_event_inputs(event_abi: ABIEvent) -> Sequence[ABIComponentIndexed]:
    return [arg for arg in event_abi["inputs"] if arg["indexed"] is False]


def filter_by_types(types: Collection[str], contract_abi: ABI) -> Sequence[ABIElement]:
    return [abi_element for abi_element in contract_abi if abi_element["type"] in types]


def filter_by_argument_name(
    argument_names: Collection[str], contract_abi: ABI
) -> Sequence[ABIElement]:
    """
    Return a list of each ``ABIElement`` which contains arguments matching provided
    names.
    """
    abis_with_matching_args = []
    for abi_element in contract_abi:
        try:
            abi_arg_names = get_abi_input_names(abi_element)

            if set(argument_names).intersection(abi_arg_names) == set(argument_names):
                abis_with_matching_args.append(abi_element)
        except TypeError:
            # fallback or receive functions do not have arguments
            # proceed to next ABIElement
            continue

    return abis_with_matching_args


def filter_by_argument_type(
    argument_types: Collection[str], contract_abi: ABI
) -> List[ABIElement]:
    """
    Return a list of each ``ABIElement`` which contains arguments matching provided
    types.
    """
    abis_with_matching_args = []
    for abi_element in contract_abi:
        try:
            abi_arg_types = get_abi_input_types(abi_element)

            if set(argument_types).intersection(abi_arg_types) == set(argument_types):
                abis_with_matching_args.append(abi_element)
        except ValueError:
            # fallback or receive functions do not have arguments
            # proceed to next ABIElement
            continue

    return abis_with_matching_args


def get_name_from_abi_element_identifier(
    abi_element_identifier: ABIElementIdentifier,
) -> str:
    if abi_element_identifier in ["fallback", FallbackFn]:
        return "fallback"
    elif abi_element_identifier in ["receive", ReceiveFn]:
        return "receive"
    elif is_text(abi_element_identifier):
        return str(abi_element_identifier).split("(")[0]
    else:
        raise Web3TypeError("Unsupported function identifier")


def get_abi_element_signature(
    abi_element_identifier: ABIElementIdentifier,
    abi_element_argument_types: Optional[Sequence[str]] = None,
) -> str:
    element_name = get_name_from_abi_element_identifier(abi_element_identifier)
    argument_types = ",".join(abi_element_argument_types or [])

    if element_name in ["fallback", "receive"]:
        return element_name

    return f"{element_name}({argument_types})"


class AddressEncoder(encoding.AddressEncoder):
    @classmethod
    def validate_value(cls, value: Any) -> None:
        if is_ens_name(value):
            return

        super().validate_value(value)  # type: ignore[no-untyped-call]


class AcceptsHexStrEncoder(encoding.BaseEncoder):
    subencoder_cls: Type[encoding.BaseEncoder] = None
    is_strict: bool = None
    is_big_endian: bool = False
    data_byte_size: int = None
    value_bit_size: int = None

    def __init__(
        self,
        subencoder: encoding.BaseEncoder,
        **kwargs: Dict[str, Any],
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[no-untyped-call]
        self.subencoder = subencoder
        self.is_dynamic = subencoder.is_dynamic

    @classmethod
    def from_type_str(
        cls, abi_type: TypeStr, registry: ABIRegistry
    ) -> "AcceptsHexStrEncoder":
        subencoder_cls = cls.get_subencoder_class()
        # cast b/c expects BaseCoder but `from_type_string`
        # restricted to BaseEncoder subclasses
        subencoder = cast(
            encoding.BaseEncoder, subencoder_cls.from_type_str(abi_type, registry)  # type: ignore[no-untyped-call]  # noqa: E501
        )
        return cls(subencoder)

    @classmethod
    def get_subencoder_class(cls) -> Type[encoding.BaseEncoder]:
        if cls.subencoder_cls is None:
            raise Web3AttributeError(f"No subencoder class is set. {cls.__name__}")
        return cls.subencoder_cls

    def validate_value(self, value: Any) -> None:
        normalized_value = self.validate_and_normalize(value)
        self.subencoder.validate_value(normalized_value)

    def encode(self, value: Any) -> bytes:
        normalized_value = self.validate_and_normalize(value)
        return self.subencoder.encode(normalized_value)

    def validate_and_normalize(self, value: Any) -> HexStr:
        if not is_bytes(value) and not is_text(value):
            self.invalidate_value(value)

        raw_value = value
        if is_text(value):
            try:
                value = decode_hex(value)
            except binascii.Error:
                self.invalidate_value(
                    value,
                    msg=f"{value} is an invalid hex string",
                )
            else:
                if raw_value[:2] != "0x" and self.is_strict:
                    self.invalidate_value(
                        raw_value, msg="hex string must be prefixed with 0x"
                    )

        if self.is_strict and self.data_byte_size is not None:
            if len(value) > self.data_byte_size:
                self.invalidate_value(
                    value,
                    exc=ValueOutOfBounds,
                    msg=f"exceeds total byte size for bytes{self.data_byte_size} "
                    "encoding",
                )
            elif len(value) < self.data_byte_size:
                self.invalidate_value(
                    value,
                    exc=ValueOutOfBounds,
                    msg=f"less than total byte size for bytes{self.data_byte_size} "
                    "encoding",
                )

        return value


class BytesEncoder(AcceptsHexStrEncoder):
    subencoder_cls = encoding.BytesEncoder
    is_strict = False


class ExactLengthBytesEncoder(BytesEncoder):
    is_strict = True

    def validate(self) -> None:
        super().validate()  # type: ignore[no-untyped-call]
        if self.value_bit_size is None:
            raise Web3ValueError("`value_bit_size` may not be none")
        if self.data_byte_size is None:
            raise Web3ValueError("`data_byte_size` may not be none")
        if self.is_big_endian is None:
            raise Web3ValueError("`is_big_endian` may not be none")

        if self.value_bit_size % 8 != 0:
            raise Web3ValueError(
                f"Invalid value bit size: {self.value_bit_size}. "
                "Must be a multiple of 8"
            )

        if self.value_bit_size > self.data_byte_size * 8:
            raise Web3ValueError("Value byte size exceeds data size")

    @parse_type_str("bytes")  # type: ignore[no-untyped-call]
    def from_type_str(
        cls, abi_type: BasicType, registry: ABIRegistry
    ) -> "ExactLengthBytesEncoder":
        subencoder_cls = cls.get_subencoder_class()
        subencoder = subencoder_cls.from_type_str(abi_type.to_type_str(), registry)  # type: ignore[no-untyped-call]  # noqa: E501
        return cast(
            ExactLengthBytesEncoder,
            # type ignored b/c mypy thinks the __call__ is from BaseEncoder, but it's
            # from ExactLengthBytesEncoder, which does have value_bit_size and
            # data_byte_size attributes
            cls(  # type: ignore[call-arg]
                subencoder,
                value_bit_size=abi_type.sub * 8,
                data_byte_size=abi_type.sub,
            ),
        )


class ByteStringEncoder(AcceptsHexStrEncoder):
    subencoder_cls = encoding.ByteStringEncoder
    is_strict = False


class StrictByteStringEncoder(AcceptsHexStrEncoder):
    subencoder_cls = encoding.ByteStringEncoder
    is_strict = True


class TextStringEncoder(encoding.TextStringEncoder):
    @classmethod
    def validate_value(cls, value: Any) -> None:
        if is_bytes(value):
            try:
                value = to_text(value)
            except UnicodeDecodeError:
                cls.invalidate_value(
                    value,
                    msg="not decodable as unicode string",
                )

        super().validate_value(value)  # type: ignore[no-untyped-call]


TUPLE_TYPE_STR_RE = re.compile(r"^(tuple)((\[([1-9]\d*\b)?])*)??$")


def get_tuple_type_str_parts(s: str) -> Optional[Tuple[str, Optional[str]]]:
    """
    Takes a JSON ABI type string.  For tuple type strings, returns the separated
    prefix and array dimension parts.  For all other strings, returns ``None``.
    """
    match = TUPLE_TYPE_STR_RE.match(s)

    if match is not None:
        tuple_prefix = match.group(1)
        tuple_dims = match.group(2)

        return tuple_prefix, tuple_dims

    return None


def _align_abi_input(
    arg_abi: Union[ABIComponent, ABIComponentIndexed], arg: Any
) -> Tuple[Any, ...]:
    """
    Aligns the values of any mapping at any level of nesting in ``arg``
    according to the layout of the corresponding abi spec.
    """
    tuple_parts = get_tuple_type_str_parts(arg_abi["type"])

    if tuple_parts is None:
        # Arg is non-tuple.  Just return value.
        return arg

    tuple_prefix, tuple_dims = tuple_parts
    if tuple_dims is None:
        # Arg is non-list tuple.  Each sub arg in `arg` will be aligned
        # according to its corresponding abi.
        sub_abis = arg_abi["components"]
    else:
        num_dims = tuple_dims.count("[")

        # Arg is list tuple.  A non-list version of its abi will be used to
        # align each element in `arg`.
        new_abi = copy.copy(arg_abi)
        new_abi["type"] = tuple_prefix + "[]" * (num_dims - 1)

        sub_abis = [cast(ABIComponent, abi) for abi in itertools.repeat(new_abi)]

    if isinstance(arg, abc.Mapping):
        # Arg is mapping.  Align values according to abi order.
        aligned_arg = tuple(arg[abi["name"]] for abi in sub_abis)
    else:
        aligned_arg = arg

    if not is_list_like(aligned_arg):
        raise Web3TypeError(
            f'Expected non-string sequence for "{arg_abi.get("type")}" '
            f"component type: got {aligned_arg}"
        )

    # convert NamedTuple to regular tuple
    typing = tuple if isinstance(aligned_arg, tuple) else type(aligned_arg)

    return typing(
        _align_abi_input(sub_abi, sub_arg)
        for sub_abi, sub_arg in zip(sub_abis, aligned_arg)
    )


def find_constructor_abi_element_by_type(contract_abi: ABI) -> ABIConstructor:
    """
    Find the constructor ABI element in the contract ABI.

    This function is often used in place of `web3.utils.abi.get_abi_element` to find
    a constructor without considering its argument types. This is used prior to
    encoding the abi, since the argument types are not known at that time.
    """
    candidates = [abi for abi in contract_abi if abi["type"] == "constructor"]
    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) == 0:
        return None
    elif len(candidates) > 1:
        raise Web3ValueError("Found multiple constructors.")
    return None


DYNAMIC_TYPES = ["bytes", "string"]

INT_SIZES = range(8, 257, 8)
BYTES_SIZES = range(1, 33)
UINT_TYPES = [f"uint{i}" for i in INT_SIZES]
INT_TYPES = [f"int{i}" for i in INT_SIZES]
BYTES_TYPES = [f"bytes{i}" for i in BYTES_SIZES] + ["bytes32.byte"]

STATIC_TYPES = list(
    itertools.chain(
        ["address", "bool"],
        UINT_TYPES,
        INT_TYPES,
        BYTES_TYPES,
    )
)

BASE_TYPE_REGEX = "|".join(
    _type + "(?![a-z0-9])" for _type in itertools.chain(STATIC_TYPES, DYNAMIC_TYPES)
)

SUB_TYPE_REGEX = r"\[" "[0-9]*" r"\]"

TYPE_REGEX = ("^" "(?:{base_type})" "(?:(?:{sub_type})*)?" "$").format(
    base_type=BASE_TYPE_REGEX,
    sub_type=SUB_TYPE_REGEX,
)


def is_recognized_type(abi_type: TypeStr) -> bool:
    return bool(re.match(TYPE_REGEX, abi_type))


def is_bool_type(abi_type: TypeStr) -> bool:
    return abi_type == "bool"


def is_uint_type(abi_type: TypeStr) -> bool:
    return abi_type in UINT_TYPES


def is_int_type(abi_type: TypeStr) -> bool:
    return abi_type in INT_TYPES


def is_address_type(abi_type: TypeStr) -> bool:
    return abi_type == "address"


def is_bytes_type(abi_type: TypeStr) -> bool:
    return abi_type in BYTES_TYPES + ["bytes"]


def is_string_type(abi_type: TypeStr) -> bool:
    return abi_type == "string"


@curry
def is_length(target_length: int, value: abc.Sized) -> bool:
    return len(value) == target_length


def size_of_type(abi_type: TypeStr) -> int:
    """
    Returns size in bits of abi_type
    """
    if "string" in abi_type:
        return None
    if "byte" in abi_type:
        return None
    if "[" in abi_type:
        return None
    if abi_type == "bool":
        return 8
    if abi_type == "address":
        return 160
    return int(re.sub(r"\D", "", abi_type))


END_BRACKETS_OF_ARRAY_TYPE_REGEX = r"\[[^]]*\]$"


def sub_type_of_array_type(abi_type: TypeStr) -> str:
    if not is_array_type(abi_type):
        raise Web3ValueError(f"Cannot parse subtype of nonarray abi-type: {abi_type}")

    return re.sub(END_BRACKETS_OF_ARRAY_TYPE_REGEX, "", abi_type, count=1)


def length_of_array_type(abi_type: TypeStr) -> int:
    if not is_array_type(abi_type):
        raise Web3ValueError(f"Cannot parse length of nonarray abi-type: {abi_type}")

    inner_brackets = (
        re.search(END_BRACKETS_OF_ARRAY_TYPE_REGEX, abi_type).group(0).strip("[]")
    )
    if not inner_brackets:
        return None
    else:
        return int(inner_brackets)


ARRAY_REGEX = ("^" "[a-zA-Z0-9_]+" "({sub_type})+" "$").format(sub_type=SUB_TYPE_REGEX)


def is_array_type(abi_type: TypeStr) -> bool:
    return bool(re.match(ARRAY_REGEX, abi_type))


NAME_REGEX = "[a-zA-Z_]" "[a-zA-Z0-9_]*"


ENUM_REGEX = ("^" "{lib_name}" r"\." "{enum_name}" "$").format(
    lib_name=NAME_REGEX, enum_name=NAME_REGEX
)


def is_probably_enum(abi_type: TypeStr) -> bool:
    return bool(re.match(ENUM_REGEX, abi_type))


@to_tuple
def normalize_event_input_types(
    abi_args: Collection[ABIEvent],
) -> Iterable[Union[ABIEvent, Dict[TypeStr, Any]]]:
    for arg in abi_args:
        if is_recognized_type(arg["type"]):
            yield arg
        elif is_probably_enum(arg["type"]):
            yield {k: "uint8" if k == "type" else v for k, v in arg.items()}
        else:
            yield arg


########################################################
#
#  Conditionally modifying data, tagged with ABI Types
#
########################################################


@curry
def map_abi_data(
    normalizers: Sequence[Callable[[TypeStr, Any], Tuple[TypeStr, Any]]],
    types: Sequence[TypeStr],
    data: Sequence[Any],
) -> Any:
    """
    Applies normalizers to your data, in the context of the relevant types.
    Each normalizer is in the format:

    def normalizer(datatype, data):
        # Conditionally modify data
        return (datatype, data)

    Where datatype is a valid ABI type string, like "uint".

    In case of an array, like "bool[2]", normalizer will receive `data`
    as an iterable of typed data, like `[("bool", True), ("bool", False)]`.

    Internals
    ---

    This is accomplished by:

    1. Decorating the data tree with types
    2. Recursively mapping each of the normalizers to the data
    3. Stripping the types back out of the tree
    """
    pipeline = itertools.chain(
        [abi_data_tree(types)],
        map(data_tree_map, normalizers),
        [partial(recursive_map, strip_abi_type)],
    )

    return pipe(data, *pipeline)


@curry
def abi_data_tree(types: Sequence[TypeStr], data: Sequence[Any]) -> List[Any]:
    """
    Decorate the data tree with pairs of (type, data). The pair tuple is actually an
    ABITypedData, but can be accessed as a tuple.

    As an example:

    >>> abi_data_tree(types=["bool[2]", "uint"], data=[[True, False], 0])
    [("bool[2]", [("bool", True), ("bool", False)]), ("uint256", 0)]
    """
    return [
        abi_sub_tree(data_type, data_value)
        for data_type, data_value in zip(types, data)
    ]


@curry
def data_tree_map(
    func: Callable[[TypeStr, Any], Tuple[TypeStr, Any]], data_tree: Any
) -> "ABITypedData":
    """
    Map func to every ABITypedData element in the tree. func will
    receive two args: abi_type, and data
    """

    def map_to_typed_data(elements: Any) -> "ABITypedData":
        if isinstance(elements, ABITypedData) and elements.abi_type is not None:
            return ABITypedData(func(*elements))
        else:
            return elements

    return recursive_map(map_to_typed_data, data_tree)


class ABITypedData(namedtuple("ABITypedData", "abi_type, data")):
    """
    Marks data as having a certain ABI-type.

    >>> a1 = ABITypedData(['address', addr1])
    >>> a2 = ABITypedData(['address', addr2])
    >>> addrs = ABITypedData(['address[]', [a1, a2]])

    You can access the fields using tuple() interface, or with
    attributes:

    >>> assert a1.abi_type == a1[0]
    >>> assert a1.data == a1[1]

    Unlike a typical `namedtuple`, you initialize with a single
    positional argument that is iterable, to match the init
    interface of all other relevant collections.
    """

    def __new__(cls, iterable: Iterable[Any]) -> "ABITypedData":
        return super().__new__(cls, *iterable)


def abi_sub_tree(
    type_str_or_abi_type: Optional[Union[TypeStr, ABIType]], data_value: Any
) -> ABITypedData:
    if type_str_or_abi_type is None:
        return ABITypedData([None, data_value])

    if isinstance(type_str_or_abi_type, TypeStr):
        abi_type = parse(type_str_or_abi_type)
    else:
        abi_type = type_str_or_abi_type

    # In the two special cases below, we rebuild the given data structures with
    # annotated items
    if abi_type.is_array:
        # If type is array, determine item type and annotate all
        # items in iterable with that type
        item_type_str = abi_type.item_type.to_type_str()
        value_to_annotate = [
            abi_sub_tree(item_type_str, item_value) for item_value in data_value
        ]
    elif isinstance(abi_type, TupleType):
        # Otherwise, if type is tuple, determine component types and annotate
        # tuple components in iterable respectively with those types
        value_to_annotate = type(data_value)(
            abi_sub_tree(comp_type.to_type_str(), comp_value)
            for comp_type, comp_value in zip(abi_type.components, data_value)
        )
    else:
        value_to_annotate = data_value

    return ABITypedData(
        [
            abi_type.to_type_str(),
            value_to_annotate,
        ]
    )


def strip_abi_type(elements: Any) -> Any:
    if isinstance(elements, ABITypedData):
        return elements.data
    else:
        return elements


def build_non_strict_registry() -> ABIRegistry:
    # We make a copy here just to make sure that eth-abi's default registry is not
    # affected by our custom encoder subclasses
    registry = default_registry.copy()  # type: ignore[no-untyped-call]

    registry.unregister("address")
    registry.unregister("bytes<M>")
    registry.unregister("bytes")
    registry.unregister("string")

    registry.register(
        BaseEquals("address"),  # type: ignore[no-untyped-call]
        AddressEncoder,
        decoding.AddressDecoder,
        label="address",
    )
    registry.register(
        BaseEquals("bytes", with_sub=True),  # type: ignore[no-untyped-call]
        BytesEncoder,
        decoding.BytesDecoder,
        label="bytes<M>",
    )
    registry.register(
        BaseEquals("bytes", with_sub=False),  # type: ignore[no-untyped-call]
        ByteStringEncoder,
        decoding.ByteStringDecoder,
        label="bytes",
    )
    registry.register(
        BaseEquals("string"),  # type: ignore[no-untyped-call]
        TextStringEncoder,
        decoding.StringDecoder,
        label="string",
    )
    return registry


def build_strict_registry() -> ABIRegistry:
    registry = default_registry.copy()  # type: ignore[no-untyped-call]

    registry.unregister("address")
    registry.unregister("bytes<M>")
    registry.unregister("bytes")
    registry.unregister("string")

    registry.register(
        BaseEquals("address"),  # type: ignore[no-untyped-call]
        AddressEncoder,
        decoding.AddressDecoder,
        label="address",
    )
    registry.register(
        BaseEquals("bytes", with_sub=True),  # type: ignore[no-untyped-call]
        ExactLengthBytesEncoder,
        decoding.BytesDecoder,
        label="bytes<M>",
    )
    registry.register(
        BaseEquals("bytes", with_sub=False),  # type: ignore[no-untyped-call]
        StrictByteStringEncoder,
        decoding.ByteStringDecoder,
        label="bytes",
    )
    registry.register(
        BaseEquals("string"),  # type: ignore[no-untyped-call]
        encoding.TextStringEncoder,
        decoding.StringDecoder,
        label="string",
    )
    return registry


def named_tree(
    abi: Iterable[
        Union[
            ABIComponent, ABIComponentIndexed, ABIFunction, ABIEvent, Dict[TypeStr, Any]
        ]
    ],
    data: Iterable[Tuple[Any, ...]],
) -> Dict[str, Any]:
    """
    Convert function inputs/outputs or event data tuple to dict with names from ABI.
    """
    names = [item["name"] for item in abi]
    items = [_named_subtree(*item) for item in zip(abi, data)]

    return dict(zip(names, items))


def _named_subtree(
    abi: Union[
        ABIComponent, ABIComponentIndexed, ABIFunction, ABIEvent, Dict[TypeStr, Any]
    ],
    data: Tuple[Any, ...],
) -> Union[Dict[str, Any], Tuple[Any, ...], List[Any]]:
    abi_type = parse(collapse_if_tuple(cast(Dict[str, Any], abi)))

    if abi_type.is_array:
        item_type = abi_type.item_type.to_type_str()
        item_abi = {**abi, "type": item_type, "name": ""}
        items = [_named_subtree(item_abi, item) for item in data]
        return items

    elif isinstance(abi_type, TupleType):
        if abi.get("indexed"):
            abi = cast(ABIComponentIndexed, abi)
        else:
            abi = cast(ABIComponent, abi)

        names = [item["name"] for item in abi["components"]]
        items = [_named_subtree(*item) for item in zip(abi["components"], data)]

        if len(names) == len(data):
            return dict(zip(names, items))
        else:
            raise MismatchedABI(
                f"ABI fields {names} has length {len(names)} but received "
                f"data {data} with length {len(data)}"
            )

    return data


def recursive_dict_to_namedtuple(data: Dict[str, Any]) -> Tuple[Any, ...]:
    def _dict_to_namedtuple(
        value: Union[Dict[str, Any], List[Any]]
    ) -> Union[Tuple[Any, ...], List[Any]]:
        if not isinstance(value, dict):
            return value

        keys, values = zip(*value.items()) if value else ((), ())
        return abi_decoded_namedtuple_factory(keys)(values)

    return recursive_map(_dict_to_namedtuple, data)


def abi_decoded_namedtuple_factory(
    fields: Tuple[Any, ...]
) -> Callable[..., Tuple[Any, ...]]:
    class ABIDecodedNamedTuple(namedtuple("ABIDecodedNamedTuple", fields, rename=True)):  # type: ignore # noqa: E501
        def __new__(self, args: Any) -> "ABIDecodedNamedTuple":
            return super().__new__(self, *args)

    return ABIDecodedNamedTuple


# -- async -- #


async def async_data_tree_map(
    async_w3: "AsyncWeb3",
    func: Callable[
        ["AsyncWeb3", TypeStr, Any], Coroutine[Any, Any, Tuple[TypeStr, Any]]
    ],
    data_tree: Any,
) -> "ABITypedData":
    """
    Map an awaitable method to every ABITypedData element in the tree.

    The awaitable method should receive three positional args:
        async_w3, abi_type, and data
    """

    async def async_map_to_typed_data(elements: Any) -> "ABITypedData":
        if isinstance(elements, ABITypedData) and elements.abi_type is not None:
            formatted = await func(async_w3, *elements)
            return ABITypedData(formatted)
        else:
            return elements

    return await async_recursive_map(async_w3, async_map_to_typed_data, data_tree)


@reject_recursive_repeats
async def async_recursive_map(
    async_w3: "AsyncWeb3",
    func: Callable[[Any], Coroutine[Any, Any, TReturn]],
    data: Any,
) -> TReturn:
    """
    Apply an awaitable method to data and any collection items inside data
    (using async_map_collection).

    Define the awaitable method so that it only applies to the type of value that you
    want it to apply to.
    """

    async def async_recurse(item: Any) -> TReturn:
        return await async_recursive_map(async_w3, func, item)

    items_mapped = await async_map_if_collection(async_recurse, data)
    return await func(items_mapped)


async def async_map_if_collection(
    func: Callable[[Any], Coroutine[Any, Any, Any]], value: Any
) -> Any:
    """
    Apply an awaitable method to each element of a collection or value of a dictionary.
    If the value is not a collection, return it unmodified.
    """
    datatype = type(value)
    if isinstance(value, Mapping):
        return datatype({key: await func(val) for key, val in value.values()})
    if is_string(value):
        return value
    elif isinstance(value, Iterable):
        return datatype([await func(item) for item in value])
    else:
        return value
