from collections import (
    abc,
)
import copy
import itertools
import re
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
    overload,
)

from eth_typing import (
    ABI,
    ABIComponent,
    ABIConstructor,
    ABIElement,
    ABIError,
    ABIEvent,
    ABIFallback,
    ABIFunction,
    ABIReceive,
)

from eth_utils.types import (
    is_list_like,
)

from .crypto import (
    keccak,
)


def _align_abi_input(
    arg_abi: ABIComponent, normalized_arg: Any
) -> Union[Any, Tuple[Any, ...]]:
    """
    Aligns the values of any mapping at any level of nesting in ``normalized_arg``
    according to the layout of the corresponding abi spec.
    """
    tuple_parts = _get_tuple_type_str_and_dims(arg_abi.get("type", ""))

    if tuple_parts is None:
        # normalized_arg is non-tuple.  Just return value.
        return normalized_arg

    tuple_prefix, tuple_dims = tuple_parts
    if tuple_dims is None:
        # normalized_arg is non-list tuple.  Each sub arg in `normalized_arg` will be
        # aligned according to its corresponding abi.
        sub_abis = cast(Iterable[ABIComponent], arg_abi.get("components", []))
    else:
        num_dims = tuple_dims.count("[")

        # normalized_arg is list tuple.  A non-list version of its abi will be used to
        # align each element in `normalized_arg`.
        new_abi = copy.copy(arg_abi)
        new_abi["type"] = tuple_prefix + "[]" * (num_dims - 1)

        sub_abis = itertools.repeat(new_abi)

    if isinstance(normalized_arg, abc.Mapping):
        # normalized_arg is mapping.  Align values according to abi order.
        aligned_arg = tuple(normalized_arg[abi["name"]] for abi in sub_abis)
    else:
        aligned_arg = normalized_arg

    if not is_list_like(aligned_arg):
        raise TypeError(
            f'Expected non-string sequence for "{arg_abi.get("type")}" '
            f"component type: got {aligned_arg}"
        )

    # convert NamedTuple to regular tuple
    typing = tuple if isinstance(aligned_arg, tuple) else type(aligned_arg)

    return typing(
        _align_abi_input(sub_abi, sub_arg)
        for sub_abi, sub_arg in zip(sub_abis, aligned_arg)
    )


def _get_tuple_type_str_and_dims(s: str) -> Optional[Tuple[str, Optional[str]]]:
    """
    Takes a JSON ABI type string.  For tuple type strings, returns the separated
    prefix and array dimension parts.  For all other strings, returns ``None``.
    """
    tuple_type_str_re = "^(tuple)((\\[([1-9]\\d*\b)?])*)??$"
    match = re.compile(tuple_type_str_re).match(s)

    if match is not None:
        tuple_prefix = match.group(1)
        tuple_dims = match.group(2)

        return tuple_prefix, tuple_dims

    return None


def _raise_if_not_function_abi(abi_element: ABIElement) -> None:
    if abi_element["type"] != "function":
        raise ValueError(
            f"Outputs only supported for ABI type `function`. Provided"
            f" ABI type was `{abi_element.get('type')}` and outputs were "
            f"`{abi_element.get('outputs')}`."
        )


def _raise_if_fallback_or_receive_abi(abi_element: ABIElement) -> None:
    if abi_element["type"] == "fallback" or abi_element["type"] == "receive":
        raise ValueError(
            f"Inputs not supported for function types `fallback` or `receive`. Provided"
            f" ABI type was `{abi_element.get('type')}` with inputs "
            f"`{abi_element.get('inputs')}`."
        )


def collapse_if_tuple(abi: Union[ABIComponent, Dict[str, Any], str]) -> str:
    """
    Extract argument types from a function or event ABI parameter.

    With tuple argument types, return a Tuple of each type.
    Returns the param if `abi` is an instance of str or another non-tuple
    type.

    :param abi: A Function or Event ABI component or a string with type info.
    :type abi: `Union[ABIComponent, Dict[str, Any], str]`
    :return: Type(s) for the function or event ABI param.
    :rtype: `str`

    .. doctest::

        >>> from eth_utils.abi import collapse_if_tuple
        >>> abi = {
        ...   'components': [
        ...     {'name': 'anAddress', 'type': 'address'},
        ...     {'name': 'anInt', 'type': 'uint256'},
        ...     {'name': 'someBytes', 'type': 'bytes'},
        ...   ],
        ...   'type': 'tuple',
        ... }
        >>> collapse_if_tuple(abi)
        '(address,uint256,bytes)'
    """
    if isinstance(abi, str):
        return abi

    element_type = abi.get("type")
    if not isinstance(element_type, str):
        raise TypeError(
            f"The 'type' must be a string, but got {repr(element_type)} of type "
            f"{type(element_type)}"
        )
    elif not element_type.startswith("tuple"):
        return element_type

    delimited = ",".join(collapse_if_tuple(c) for c in abi["components"])
    # Whatever comes after "tuple" is the array dims. The ABI spec states that
    # this will have the form "", "[]", or "[k]".
    array_dim = element_type[5:]
    collapsed = f"({delimited}){array_dim}"

    return collapsed


def abi_to_signature(abi_element: ABIElement) -> str:
    """
    Returns a string signature representation of the function or event ABI
    and arguments.

    Signatures consist of the name followed by a list of arguments.

    :param abi_element: ABI element.
    :type abi_element: `ABIElement`
    :return: Stringified ABI signature
    :rtype: `str`

    .. doctest::

        >>> from eth_utils import abi_to_signature
        >>> abi_element = {
        ...   'constant': False,
        ...   'inputs': [
        ...     {
        ...       'name': 's',
        ...       'type': 'uint256'
        ...     }
        ...   ],
        ...   'name': 'f',
        ...   'outputs': [],
        ...   'payable': False,
        ...   'stateMutability': 'nonpayable',
        ...   'type': 'function'
        ... }
        >>> abi_to_signature(abi_element)
        'f(uint256)'
    """
    signature = "{name}({input_types})"

    abi_type = str(abi_element.get("type", ""))
    if abi_type == "fallback" or abi_type == "receive":
        return signature.format(name=abi_type, input_types="")

    if abi_type == "constructor":
        fn_name = abi_type
    else:
        fn_name = str(abi_element.get("name", abi_type))

    return signature.format(
        name=fn_name, input_types=",".join(get_abi_input_types(abi_element))
    )


def filter_abi_by_name(abi_name: str, contract_abi: ABI) -> Sequence[ABIElement]:
    """
    Get one or more function and event ABIs by name.

    :param abi_name: Name of the function, event or error.
    :type abi_name: `str`
    :param contract_abi: Contract ABI.
    :type contract_abi: `ABI`
    :return: Function or event ABIs with matching name.
    :rtype: `Sequence[ABIElement]`

    .. doctest::

            >>> from eth_utils.abi import filter_abi_by_name
            >>> abi = [
            ...     {
            ...         "constant": False,
            ...         "inputs": [],
            ...         "name": "func_1",
            ...         "outputs": [],
            ...         "type": "function",
            ...     },
            ...     {
            ...         "constant": False,
            ...         "inputs": [
            ...             {"name": "a", "type": "uint256"},
            ...         ],
            ...         "name": "func_2",
            ...         "outputs": [],
            ...         "type": "function",
            ...     },
            ...     {
            ...         "constant": False,
            ...         "inputs": [
            ...             {"name": "a", "type": "uint256"},
            ...             {"name": "b", "type": "uint256"},
            ...         ],
            ...         "name": "func_3",
            ...         "outputs": [],
            ...         "type": "function",
            ...     },
            ...     {
            ...         "constant": False,
            ...         "inputs": [
            ...             {"name": "a", "type": "uint256"},
            ...             {"name": "b", "type": "uint256"},
            ...             {"name": "c", "type": "uint256"},
            ...         ],
            ...         "name": "func_4",
            ...         "outputs": [],
            ...         "type": "function",
            ...     },
            ... ]
            >>> filter_abi_by_name("func_1", abi)
            [{'constant': False, 'inputs': [], 'name': 'func_1', 'outputs': [], \
'type': 'function'}]
    """
    return [
        abi
        for abi in contract_abi
        if (
            (
                abi["type"] == "function"
                or abi["type"] == "event"
                or abi["type"] == "error"
            )
            and abi["name"] == abi_name
        )
    ]


@overload
def filter_abi_by_type(
    abi_type: Literal["function"],
    contract_abi: ABI,
) -> Sequence[ABIFunction]:
    pass


@overload
def filter_abi_by_type(
    abi_type: Literal["constructor"],
    contract_abi: ABI,
) -> Sequence[ABIConstructor]:
    pass


@overload
def filter_abi_by_type(
    abi_type: Literal["fallback"],
    contract_abi: ABI,
) -> Sequence[ABIFallback]:
    pass


@overload
def filter_abi_by_type(
    abi_type: Literal["receive"],
    contract_abi: ABI,
) -> Sequence[ABIReceive]:
    pass


@overload
def filter_abi_by_type(
    abi_type: Literal["event"],
    contract_abi: ABI,
) -> Sequence[ABIEvent]:
    pass


@overload
def filter_abi_by_type(
    abi_type: Literal["error"],
    contract_abi: ABI,
) -> Sequence[ABIError]:
    pass


def filter_abi_by_type(
    abi_type: Literal[
        "function", "constructor", "fallback", "receive", "event", "error"
    ],
    contract_abi: ABI,
) -> Sequence[
    Union[ABIFunction, ABIConstructor, ABIFallback, ABIReceive, ABIEvent, ABIError]
]:
    """
    Return a list of each ``ABIElement`` that is of type ``abi_type``.

    For mypy, function overloads ensures the correct type is returned based on the
    ``abi_type``. For example, if ``abi_type`` is "function", the return type will be
    ``Sequence[ABIFunction]``.

    :param abi_type: Type of ABI element to filter by.
    :type abi_type: `str`
    :param contract_abi: Contract ABI.
    :type contract_abi: `ABI`
    :return: List of ABI elements of the specified type.
    :rtype: `Sequence[Union[ABIFunction, ABIConstructor, ABIFallback, ABIReceive, \
ABIEvent, ABIError]]`

    .. doctest::

        >>> from eth_utils import filter_abi_by_type
        >>> abi = [
        ...   {"type": "function", "name": "myFunction", "inputs": [], "outputs": []},
        ...   {"type": "function", "name": "myFunction2", "inputs": [], "outputs": []},
        ...   {"type": "event", "name": "MyEvent", "inputs": []}
        ... ]
        >>> filter_abi_by_type("function", abi)
        [{'type': 'function', 'name': 'myFunction', 'inputs': [], 'outputs': []}, \
{'type': 'function', 'name': 'myFunction2', 'inputs': [], 'outputs': []}]
    """
    if abi_type == Literal["function"] or abi_type == "function":
        return [abi for abi in contract_abi if abi["type"] == "function"]
    elif abi_type == Literal["constructor"] or abi_type == "constructor":
        return [abi for abi in contract_abi if abi["type"] == "constructor"]
    elif abi_type == Literal["fallback"] or abi_type == "fallback":
        return [abi for abi in contract_abi if abi["type"] == "fallback"]
    elif abi_type == Literal["receive"] or abi_type == "receive":
        return [abi for abi in contract_abi if abi["type"] == "receive"]
    elif abi_type == Literal["event"] or abi_type == "event":
        return [abi for abi in contract_abi if abi["type"] == "event"]
    elif abi_type == Literal["error"] or abi_type == "error":
        return [abi for abi in contract_abi if abi["type"] == "error"]
    else:
        raise ValueError(f"Unsupported ABI type: {abi_type}")


def get_all_function_abis(contract_abi: ABI) -> Sequence[ABIFunction]:
    """
    Return interfaces for each function in the contract ABI.

    :param contract_abi: Contract ABI.
    :type contract_abi: `ABI`
    :return: List of ABIs for each function interface.
    :rtype: `Sequence[ABIFunction]`

    .. doctest::

        >>> from eth_utils import get_all_function_abis
        >>> contract_abi = [
        ...   {"type": "function", "name": "myFunction", "inputs": [], "outputs": []},
        ...   {"type": "function", "name": "myFunction2", "inputs": [], "outputs": []},
        ...   {"type": "event", "name": "MyEvent", "inputs": []}
        ... ]
        >>> get_all_function_abis(contract_abi)
        [{'type': 'function', 'name': 'myFunction', 'inputs': [], 'outputs': []}, \
{'type': 'function', 'name': 'myFunction2', 'inputs': [], 'outputs': []}]
    """
    return filter_abi_by_type("function", contract_abi)


def get_all_event_abis(contract_abi: ABI) -> Sequence[ABIEvent]:
    """
    Return interfaces for each event in the contract ABI.

    :param contract_abi: Contract ABI.
    :type contract_abi: `ABI`
    :return: List of ABIs for each event interface.
    :rtype: `Sequence[ABIEvent]`

    .. doctest::

        >>> from eth_utils import get_all_event_abis
        >>> contract_abi = [
        ...   {"type": "function", "name": "myFunction", "inputs": [], "outputs": []},
        ...   {"type": "function", "name": "myFunction2", "inputs": [], "outputs": []},
        ...   {"type": "event", "name": "MyEvent", "inputs": []}
        ... ]
        >>> get_all_event_abis(contract_abi)
        [{'type': 'event', 'name': 'MyEvent', 'inputs': []}]
    """
    return filter_abi_by_type("event", contract_abi)


def get_normalized_abi_inputs(
    abi_element: ABIElement,
    *args: Optional[Sequence[Any]],
    **kwargs: Optional[Dict[str, Any]],
) -> Tuple[Any, ...]:
    r"""
    Flattens positional args (``args``) and keyword args (``kwargs``) into a Tuple and
    uses the ``abi_element`` for validation.

    Checks to ensure that the correct number of args were given, no duplicate args were
    given, and no unknown args were given.  Returns a list of argument values aligned
    to the order of inputs defined in ``abi_element``.

    :param abi_element: ABI element.
    :type abi_element: `ABIElement`
    :param args: Positional arguments for the function.
    :type args: `Optional[Sequence[Any]]`
    :param kwargs: Keyword arguments for the function.
    :type kwargs: `Optional[Dict[str, Any]]`
    :return: Arguments list.
    :rtype: `Tuple[Any, ...]`

    .. doctest::

        >>> from eth_utils import get_normalized_abi_inputs
        >>> abi = {
        ...   'constant': False,
        ...   'inputs': [
        ...     {
        ...       'name': 'name',
        ...       'type': 'string'
        ...     },
        ...     {
        ...       'name': 's',
        ...       'type': 'uint256'
        ...     },
        ...     {
        ...       'name': 't',
        ...       'components': [
        ...         {'name': 'anAddress', 'type': 'address'},
        ...         {'name': 'anInt', 'type': 'uint256'},
        ...         {'name': 'someBytes', 'type': 'bytes'},
        ...       ],
        ...       'type': 'tuple'
        ...     }
        ...   ],
        ...   'name': 'f',
        ...   'outputs': [],
        ...   'payable': False,
        ...   'stateMutability': 'nonpayable',
        ...   'type': 'function'
        ... }
        >>> get_normalized_abi_inputs(
        ...   abi, *('myName', 123), **{'t': ('0x1', 1, b'\x01')}
        ... )
        ('myName', 123, ('0x1', 1, b'\x01'))
    """
    _raise_if_fallback_or_receive_abi(abi_element)

    function_inputs = cast(Sequence[ABIComponent], abi_element.get("inputs", []))
    if len(args) + len(kwargs) != len(function_inputs):
        raise TypeError(
            f"Incorrect argument count. Expected '{len(function_inputs)}'"
            f", got '{len(args) + len(kwargs)}'."
        )

    # If no keyword args were given, we don't need to align them
    if not kwargs:
        return cast(Tuple[Any, ...], args)

    kwarg_names = set(kwargs.keys())
    sorted_arg_names = tuple(arg_abi["name"] for arg_abi in function_inputs)
    args_as_kwargs = dict(zip(sorted_arg_names, args))

    # Check for duplicate args
    duplicate_args = kwarg_names.intersection(args_as_kwargs.keys())
    if duplicate_args:
        raise TypeError(
            f"{abi_element.get('name')}() got multiple values for argument(s) "
            f"'{', '.join(duplicate_args)}'."
        )

    # Check for unknown args
    # Arg names sorted to raise consistent error messages
    unknown_args = tuple(sorted(kwarg_names.difference(sorted_arg_names)))
    if unknown_args:
        message = "{} got unexpected keyword argument(s) '{}'."
        if abi_element.get("name"):
            raise TypeError(
                message.format(f"{abi_element.get('name')}()", ", ".join(unknown_args))
            )
        raise TypeError(
            message.format(
                f"Type: '{abi_element.get('type')}'", ", ".join(unknown_args)
            )
        )

    # Sort args according to their position in the ABI and unzip them from their
    # names
    sorted_args = tuple(
        zip(
            *sorted(
                itertools.chain(kwargs.items(), args_as_kwargs.items()),
                key=lambda kv: sorted_arg_names.index(kv[0]),
            )
        )
    )

    if len(sorted_args) > 0:
        return tuple(sorted_args[1])
    else:
        return tuple()


def get_aligned_abi_inputs(
    abi_element: ABIElement,
    normalized_args: Union[Tuple[Any, ...], Mapping[Any, Any]],
) -> Tuple[Tuple[str, ...], Tuple[Any, ...]]:
    """
    Returns a pair of nested Tuples containing a list of types and a list of input
    values sorted by the order specified by the ``abi``.

    ``normalized_args`` can be obtained by using
    :py:meth:`eth_utils.abi.get_normalized_abi_inputs`, which returns nested mappings
    or sequences corresponding to tuple-encoded values in ``abi``.

    :param abi_element: ABI element.
    :type abi_element: `ABIElement`
    :param normalized_args: Normalized arguments for the function.
    :type normalized_args: `Union[Tuple[Any, ...], Mapping[Any, Any]]`
    :return: Tuple of types and aligned arguments.
    :rtype: `Tuple[Tuple[str, ...], Tuple[Any, ...]]`

    .. doctest::

        >>> from eth_utils import get_aligned_abi_inputs
        >>> abi = {
        ...   'constant': False,
        ...   'inputs': [
        ...     {
        ...       'name': 'name',
        ...       'type': 'string'
        ...     },
        ...     {
        ...       'name': 's',
        ...       'type': 'uint256'
        ...     }
        ...   ],
        ...   'name': 'f',
        ...   'outputs': [],
        ...   'payable': False,
        ...   'stateMutability': 'nonpayable',
        ...   'type': 'function'
        ... }
        >>> get_aligned_abi_inputs(abi, ('myName', 123))
        (('string', 'uint256'), ('myName', 123))
    """
    _raise_if_fallback_or_receive_abi(abi_element)

    abi_element_inputs = cast(Sequence[ABIComponent], abi_element.get("inputs", []))
    if isinstance(normalized_args, abc.Mapping):
        # `args` is mapping.  Align values according to abi order.
        normalized_args = tuple(
            normalized_args[abi["name"]] for abi in abi_element_inputs
        )

    return (
        tuple(collapse_if_tuple(abi) for abi in abi_element_inputs),
        type(normalized_args)(
            _align_abi_input(abi, arg)
            for abi, arg in zip(abi_element_inputs, normalized_args)
        ),
    )


def get_abi_input_names(abi_element: ABIElement) -> List[str]:
    """
    Return names for each input from the function or event ABI.

    :param abi_element: ABI element.
    :type abi_element: `ABIElement`
    :return: Names for each input in the function or event ABI.
    :rtype: `List[str]`

    .. doctest::

        >>> from eth_utils import get_abi_input_names
        >>> abi = {
        ...   'constant': False,
        ...   'inputs': [
        ...     {
        ...       'name': 's',
        ...       'type': 'uint256'
        ...     }
        ...   ],
        ...   'name': 'f',
        ...   'outputs': [],
        ...   'payable': False,
        ...   'stateMutability': 'nonpayable',
        ...   'type': 'function'
        ... }
        >>> get_abi_input_names(abi)
        ['s']
    """
    _raise_if_fallback_or_receive_abi(abi_element)
    return [
        arg["name"]
        for arg in cast(Sequence[ABIComponent], abi_element.get("inputs", []))
    ]


def get_abi_input_types(abi_element: ABIElement) -> List[str]:
    """
    Return types for each input from the function or event ABI.

    :param abi_element: ABI element.
    :type abi_element: `ABIElement`
    :return: Types for each input in the function or event ABI.
    :rtype: `List[str]`

    .. doctest::

        >>> from eth_utils import get_abi_input_types
        >>> abi = {
        ...   'constant': False,
        ...   'inputs': [
        ...     {
        ...       'name': 's',
        ...       'type': 'uint256'
        ...     }
        ...   ],
        ...   'name': 'f',
        ...   'outputs': [],
        ...   'payable': False,
        ...   'stateMutability': 'nonpayable',
        ...   'type': 'function'
        ... }
        >>> get_abi_input_types(abi)
        ['uint256']
    """
    _raise_if_fallback_or_receive_abi(abi_element)
    return [
        collapse_if_tuple(arg)
        for arg in cast(Sequence[ABIComponent], abi_element.get("inputs", []))
    ]


def get_abi_output_names(abi_element: ABIElement) -> List[str]:
    """
    Return names for each output from the ABI element.

    :param abi_element: ABI element.
    :type abi_element: `ABIElement`
    :return: Names for each function output in the function ABI.
    :rtype: `List[str]`

    .. doctest::

        >>> from eth_utils import get_abi_output_names
        >>> abi = {
        ...   'constant': False,
        ...   'inputs': [
        ...     {
        ...       'name': 's',
        ...       'type': 'uint256'
        ...     }
        ...   ],
        ...   'name': 'f',
        ...   'outputs': [
        ...     {
        ...       'name': 'name',
        ...       'type': 'string'
        ...     },
        ...     {
        ...       'name': 's',
        ...       'type': 'uint256'
        ...     }
        ...   ],
        ...   'payable': False,
        ...   'stateMutability': 'nonpayable',
        ...   'type': 'function'
        ... }
        >>> get_abi_output_names(abi)
        ['name', 's']
    """
    _raise_if_not_function_abi(abi_element)
    return [
        arg["name"]
        for arg in cast(Sequence[ABIComponent], abi_element.get("outputs", []))
    ]


def get_abi_output_types(abi_element: ABIElement) -> List[str]:
    """
    Return types for each output from the function ABI.

    :param abi_element: ABI element.
    :type abi_element: `ABIElement`
    :return: Types for each function output in the function ABI.
    :rtype: `List[str]`

    .. doctest::

        >>> from eth_utils import get_abi_output_types
        >>> abi = {
        ...   'constant': False,
        ...   'inputs': [
        ...     {
        ...       'name': 's',
        ...       'type': 'uint256'
        ...     }
        ...   ],
        ...   'name': 'f',
        ...   'outputs': [
        ...     {
        ...       'name': 'name',
        ...       'type': 'string'
        ...     },
        ...     {
        ...       'name': 's',
        ...       'type': 'uint256'
        ...     }
        ...   ],
        ...   'payable': False,
        ...   'stateMutability': 'nonpayable',
        ...   'type': 'function'
        ... }
        >>> get_abi_output_types(abi)
        ['string', 'uint256']

    """
    _raise_if_not_function_abi(abi_element)
    return [
        collapse_if_tuple(arg)
        for arg in cast(Sequence[ABIComponent], abi_element.get("outputs", []))
    ]


def function_signature_to_4byte_selector(function_signature: str) -> bytes:
    r"""
    Return the 4-byte function selector from a function signature string.

    :param function_signature: String representation of the function name and arguments.
    :type function_signature: `str`
    :return: 4-byte function selector.
    :rtype: `bytes`

    .. doctest::

        >>> from eth_utils import function_signature_to_4byte_selector
        >>> function_signature_to_4byte_selector('myFunction()')
        b'\xc3x\n:'
    """
    return keccak(text=function_signature.replace(" ", ""))[:4]


def function_abi_to_4byte_selector(abi_element: ABIElement) -> bytes:
    r"""
    Return the 4-byte function signature of the provided function ABI.

    :param abi_element: ABI element.
    :type abi_element: `ABIElement`
    :return: 4-byte function signature.
    :rtype: `bytes`

    .. doctest::

        >>> from eth_utils import function_abi_to_4byte_selector
        >>> abi_element = {
        ...   'type': 'function',
        ...   'name': 'myFunction',
        ...   'inputs': [],
        ...   'outputs': []
        ... }
        >>> function_abi_to_4byte_selector(abi_element)
        b'\xc3x\n:'
    """
    function_signature = abi_to_signature(abi_element)
    return function_signature_to_4byte_selector(function_signature)


def event_signature_to_log_topic(event_signature: str) -> bytes:
    r"""
    Return the 32-byte keccak signature of the log topic for an event signature.

    :param event_signature: String representation of the event name and arguments.
    :type event_signature: `str`
    :return: Log topic bytes.
    :rtype: `bytes`

    .. doctest::

        >>> from eth_utils import event_signature_to_log_topic
        >>> event_signature_to_log_topic('MyEvent()')
        b'M\xbf\xb6\x8bC\xdd\xdf\xa1+Q\xeb\xe9\x9a\xb8\xfd\xedb\x0f\x9a\n\xc21B\x87\x9aO\x19*\x1byR\xd2'
    """
    return keccak(text=event_signature.replace(" ", ""))


def event_abi_to_log_topic(event_abi: ABIEvent) -> bytes:
    r"""
    Return the 32-byte keccak signature of the log topic from an event ABI.

    :param event_abi: Event ABI.
    :type event_abi: `ABIEvent`
    :return: Log topic bytes.
    :rtype: `bytes`

    .. doctest::

        >>> from eth_utils import event_abi_to_log_topic
        >>> abi = {
        ...   'type': 'event',
        ...   'anonymous': False,
        ...   'name': 'MyEvent',
        ...   'inputs': []
        ... }
        >>> event_abi_to_log_topic(abi)
        b'M\xbf\xb6\x8bC\xdd\xdf\xa1+Q\xeb\xe9\x9a\xb8\xfd\xedb\x0f\x9a\n\xc21B\x87\x9aO\x19*\x1byR\xd2'
    """
    event_signature = abi_to_signature(event_abi)
    return event_signature_to_log_topic(event_signature)
