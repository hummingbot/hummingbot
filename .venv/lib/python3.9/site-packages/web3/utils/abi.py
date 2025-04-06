import functools
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from eth_abi import (
    codec,
)
from eth_abi.codec import (
    ABICodec,
)
from eth_abi.registry import (
    registry as default_registry,
)
from eth_typing import (
    ABI,
    ABICallable,
    ABIConstructor,
    ABIElement,
    ABIElementInfo,
    ABIEvent,
    ABIFallback,
    ABIReceive,
    HexStr,
    Primitives,
)
from eth_utils.abi import (
    abi_to_signature,
    event_abi_to_log_topic,
    filter_abi_by_name,
    filter_abi_by_type,
    function_abi_to_4byte_selector,
    get_abi_input_types,
    get_aligned_abi_inputs,
    get_normalized_abi_inputs,
)
from eth_utils.address import (
    is_binary_address,
    is_checksum_address,
)
from eth_utils.conversions import (
    hexstr_if_str,
    to_bytes,
)
from eth_utils.hexadecimal import (
    encode_hex,
)
from eth_utils.toolz import (
    pipe,
)
from eth_utils.types import (
    is_list_like,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.abi import (
    filter_by_argument_name,
    get_abi_element_signature,
    get_name_from_abi_element_identifier,
)
from web3._utils.decorators import (
    deprecated_for,
)
from web3._utils.validation import (
    validate_abi,
)
from web3.exceptions import (
    ABIConstructorNotFound,
    ABIFallbackNotFound,
    ABIReceiveNotFound,
    MismatchedABI,
    Web3ValidationError,
    Web3ValueError,
)
from web3.types import (
    ABIElementIdentifier,
)


def _filter_by_signature(signature: str, contract_abi: ABI) -> List[ABIElement]:
    return [abi for abi in contract_abi if abi_to_signature(abi) == signature]


def _filter_by_argument_count(
    num_arguments: int, contract_abi: ABI
) -> List[ABIElement]:
    return [
        abi
        for abi in contract_abi
        if abi["type"] != "fallback"
        and abi["type"] != "receive"
        and len(abi.get("inputs", [])) == num_arguments
    ]


def _filter_by_encodability(
    abi_codec: codec.ABIEncoder,
    args: Sequence[Any],
    kwargs: Dict[str, Any],
    contract_abi: ABI,
) -> List[ABICallable]:
    return [
        cast(ABICallable, function_abi)
        for function_abi in contract_abi
        if check_if_arguments_can_be_encoded(
            function_abi, *args, abi_codec=abi_codec, **kwargs
        )
    ]


def _get_constructor_function_abi(contract_abi: ABI) -> ABIConstructor:
    """
    Return the receive function ABI from the contract ABI.
    """
    filtered_abis = filter_abi_by_type("constructor", contract_abi)

    if len(filtered_abis) > 1:
        raise MismatchedABI("Multiple constructor functions found in the contract ABI.")

    if filtered_abis:
        return filtered_abis[0]
    else:
        raise ABIConstructorNotFound(
            "No constructor function was found in the contract ABI."
        )


def _get_receive_function_abi(contract_abi: ABI) -> ABIReceive:
    """
    Return the receive function ABI from the contract ABI.
    """
    filtered_abis = filter_abi_by_type("receive", contract_abi)

    if len(filtered_abis) > 1:
        raise MismatchedABI("Multiple receive functions found in the contract ABI.")

    if filtered_abis:
        return filtered_abis[0]
    else:
        raise ABIReceiveNotFound("No receive function was found in the contract ABI.")


def _get_fallback_function_abi(contract_abi: ABI) -> ABIFallback:
    """
    Return the fallback function ABI from the contract ABI.
    """
    filtered_abis = filter_abi_by_type("fallback", contract_abi)

    if len(filtered_abis) > 1:
        raise MismatchedABI("Multiple fallback functions found in the contract ABI.")

    if filtered_abis:
        return filtered_abis[0]
    else:
        raise ABIFallbackNotFound("No fallback function was found in the contract ABI.")


def _get_any_abi_signature_with_name(
    element_name: str, elements: Sequence[ABIElement]
) -> str:
    """
    Find an ABI identifier signature by element name. A signature identifier is
    returned, "name(arg1Type,arg2Type,...)".

    If multiple ABIs match the name and every one contain arguments, the first
    result is returned. Otherwise the signature without arguments is returned.
    Returns None if no ABI exists with the provided name.
    """
    element_signatures_with_name = [
        abi_to_signature(element)
        for element in elements
        if element.get("name", "") == get_name_from_abi_element_identifier(element_name)
    ]

    if len(element_signatures_with_name) == 1:
        return element_signatures_with_name[0]
    elif len(element_signatures_with_name) > 1:
        # Check for function signature without args
        signature_without_args = f"{element_name}()"
        if signature_without_args not in element_signatures_with_name:
            # Element without arguments not found, use the first available signature
            return element_signatures_with_name[0]
        else:
            return signature_without_args
    else:
        return None


def _build_abi_input_error(
    abi: ABI,
    num_args: int,
    *args: Any,
    abi_codec: ABICodec,
    **kwargs: Any,
) -> str:
    """
    Build a string representation of the ABI input error.
    """
    errors: Dict[str, str] = dict(
        {
            "zero_args": "",
            "invalid_args": "",
            "encoding": "",
            "unexpected_args": "",
        }
    )

    for abi_element in abi:
        abi_element_input_types = get_abi_input_types(abi_element)
        abi_signature = abi_to_signature(abi_element)
        abi_element_name = get_name_from_abi_element_identifier(abi_signature)
        types: Tuple[str, ...] = tuple()
        aligned_args: Tuple[Any, ...] = tuple()

        if len(abi_element_input_types) == num_args:
            if num_args == 0:
                if not errors["zero_args"]:
                    errors["zero_args"] += (
                        "The provided identifier matches multiple elements.\n"
                        f"If you meant to call `{abi_element_name}()`, "
                        "please specify the full signature.\n"
                    )

                errors["zero_args"] += (
                    f" - signature: {abi_to_signature(abi_element)}, "
                    f"type: {abi_element['type']}\n"
                )
            else:
                try:
                    arguments = get_normalized_abi_inputs(abi_element, *args, **kwargs)
                    types, aligned_args = get_aligned_abi_inputs(abi_element, arguments)
                except TypeError as e:
                    errors["invalid_args"] += (
                        f"Signature: {abi_signature}, type: {abi_element['type']}\n"
                        f"Arguments do not match types in `{abi_signature}`.\n"
                        f"Error: {e}\n"
                    )

            argument_errors = ""
            for position, (_type, arg) in enumerate(zip(types, aligned_args), start=1):
                if abi_codec.is_encodable(_type, arg):
                    argument_errors += f"Argument {position} value `{arg}` is valid.\n"
                else:
                    argument_errors += (
                        f"Argument {position} value `{arg}` is not compatible with "
                        f"type `{_type}`.\n"
                    )

            if argument_errors != "":
                errors["encoding"] += (
                    f"Signature: {abi_signature}, type: {abi_element['type']}\n"
                    + argument_errors
                )

        else:
            errors["unexpected_args"] += (
                f"Signature: {abi_signature}, type: {abi_element['type']}\n"
                f"Expected {len(abi_element_input_types)} argument(s) but received "
                f"{num_args} argument(s).\n"
            )

    return "".join(errors.values())


def _mismatched_abi_error_diagnosis(
    abi_element_identifier: ABIElementIdentifier,
    abi: ABI,
    num_matches: int = 0,
    num_args: int = 0,
    *args: Optional[Any],
    abi_codec: Optional[Any] = None,
    **kwargs: Optional[Any],
) -> str:
    """
    Raise a ``MismatchedABI`` when a function ABI lookup results in an error.

    An error may result from multiple functions matching the provided signature and
    arguments or no functions are identified.
    """
    name = get_name_from_abi_element_identifier(abi_element_identifier)
    abis_matching_names = filter_abi_by_name(name, abi)
    abis_matching_arg_count = [
        abi_to_signature(abi)
        for abi in _filter_by_argument_count(num_args, abis_matching_names)
    ]
    num_abis_matching_arg_count = len(abis_matching_arg_count)

    if abi_codec is None:
        abi_codec = ABICodec(default_registry)

    error = "ABI Not Found!\n"
    if num_matches == 0 and num_abis_matching_arg_count == 0:
        error += f"No element named `{name}` with {num_args} argument(s).\n"
    elif num_matches > 1 or num_abis_matching_arg_count > 1:
        error += (
            f"Found multiple elements named `{name}` that accept {num_args} "
            "argument(s).\n"
        )
    elif num_abis_matching_arg_count == 1:
        error += (
            f"Found {num_abis_matching_arg_count} element(s) named `{name}` that "
            f"accept {num_args} argument(s).\n"
            "The provided arguments are not valid.\n"
        )
    elif num_matches == 0:
        error += (
            f"Unable to find an element named `{name}` that matches the provided "
            "identifier and argument types.\n"
        )
    arg_types = _extract_argument_types(*args)
    kwarg_types = dict({(k, _extract_argument_types([v])) for k, v in kwargs.items()})
    error += (
        f"Provided argument types: ({arg_types})\n"
        f"Provided keyword argument types: {kwarg_types}\n\n"
    )

    if abis_matching_names:
        error += (
            f"Tried to find a matching ABI element named `{name}`, but encountered "
            "the following problems:\n"
        )

        error += _build_abi_input_error(
            abis_matching_names,
            num_args,
            *args,
            abi_codec=abi_codec,
            **kwargs,
        )

    return f"\n{error}"


def _extract_argument_types(*args: Sequence[Any]) -> str:
    """
    Takes a list of arguments and returns a string representation of the argument types,
    appropriately collapsing `tuple` types into the respective nested types.
    """
    collapsed_args = []

    for arg in args:
        if is_list_like(arg):
            collapsed_nested = []
            for nested in arg:
                if is_list_like(nested):
                    collapsed_nested.append(f"({_extract_argument_types(nested)})")
                else:
                    collapsed_nested.append(_get_argument_readable_type(nested))
            collapsed_args.append(",".join(collapsed_nested))
        else:
            collapsed_args.append(_get_argument_readable_type(arg))

    return ",".join(collapsed_args)


def _get_argument_readable_type(arg: Any) -> str:
    """
    Returns the class name of the argument, or `address` if the argument is an address.
    """
    if is_checksum_address(arg) or is_binary_address(arg):
        return "address"

    return arg.__class__.__name__


def _build_abi_filters(
    abi_element_identifier: ABIElementIdentifier,
    *args: Optional[Any],
    abi_codec: Optional[Any] = None,
    **kwargs: Optional[Any],
) -> List[Callable[..., Sequence[ABIElement]]]:
    """
    Build a list of ABI filters to find an ABI element within a contract ABI. Each
    filter is a partial function that takes a contract ABI and returns a filtered list.
    Each parameter is checked before applying the relevant filter.

    When the ``abi_element_identifier`` is a function name or signature and no arguments
    are provided, the returned filters include the function name or signature.

    A function ABI may take arguments and keyword arguments. When the ``args`` and
    ``kwargs`` values are passed, several filters are combined together. Available
    filters include the function name, argument count, argument name, argument type,
    and argument encodability.

    ``constructor``, ``fallback``, and ``receive`` ABI elements are handled only with a
    filter by type.
    """
    if not isinstance(abi_element_identifier, str):
        abi_element_identifier = get_abi_element_signature(abi_element_identifier)

    if abi_element_identifier in ["constructor", "fallback", "receive"]:
        return [functools.partial(filter_abi_by_type, abi_element_identifier)]

    filters: List[Callable[..., Sequence[ABIElement]]] = []

    arg_count = 0
    if args or kwargs:
        arg_count = len(args) + len(kwargs)

    # Filter by arg count only if the identifier contains arguments
    if "()" not in abi_element_identifier and arg_count:
        filters.append(functools.partial(_filter_by_argument_count, arg_count))

    if arg_count > 0:
        filters.append(
            functools.partial(
                filter_abi_by_name,
                get_name_from_abi_element_identifier(abi_element_identifier),
            )
        )

        if args or kwargs:
            if abi_codec is None:
                abi_codec = ABICodec(default_registry)

            filters.append(
                functools.partial(
                    _filter_by_encodability,
                    abi_codec,
                    args,
                    kwargs,
                )
            )

        if "(" in abi_element_identifier:
            filters.append(
                functools.partial(_filter_by_signature, abi_element_identifier)
            )
    else:
        filters.append(
            functools.partial(
                filter_abi_by_name,
                get_name_from_abi_element_identifier(abi_element_identifier),
            )
        )
        if "(" in abi_element_identifier:
            filters.append(
                functools.partial(_filter_by_signature, abi_element_identifier)
            )

    return filters


def get_abi_element_info(
    abi: ABI,
    abi_element_identifier: ABIElementIdentifier,
    *args: Optional[Sequence[Any]],
    abi_codec: Optional[Any] = None,
    **kwargs: Optional[Dict[str, Any]],
) -> ABIElementInfo:
    """
    Information about the function ABI, selector and input arguments.

    Returns the ABI which matches the provided identifier, named arguments (``args``)
    and keyword args (``kwargs``).

    :param abi: Contract ABI.
    :type abi: `ABI`
    :param abi_element_identifier: Find an element ABI with matching identifier.
    :type abi_element_identifier: `ABIElementIdentifier`
    :param args: Find a function ABI with matching args.
    :type args: `Optional[Sequence[Any]]`
    :param abi_codec: Codec used for encoding and decoding. Default with \
    `strict_bytes_type_checking` enabled.
    :type abi_codec: `Optional[Any]`
    :param kwargs: Find an element ABI with matching kwargs.
    :type kwargs: `Optional[Dict[str, Any]]`
    :return: Element information including the ABI, selector and args.
    :rtype: `ABIElementInfo`

    .. doctest::

        >>> from web3.utils.abi import get_abi_element_info
        >>> abi = [
        ...     {
        ...         "constant": False,
        ...         "inputs": [
        ...             {"name": "a", "type": "uint256"},
        ...             {"name": "b", "type": "uint256"},
        ...         ],
        ...         "name": "multiply",
        ...         "outputs": [{"name": "result", "type": "uint256"}],
        ...         "payable": False,
        ...         "stateMutability": "nonpayable",
        ...         "type": "function",
        ...     }
        ... ]
        >>> fn_info = get_abi_element_info(abi, "multiply", *[7, 3])
        >>> fn_info["abi"]
        {'constant': False, 'inputs': [{'name': 'a', 'type': 'uint256'}, {\
'name': 'b', 'type': 'uint256'}], 'name': 'multiply', 'outputs': [{\
'name': 'result', 'type': 'uint256'}], 'payable': False, \
'stateMutability': 'nonpayable', 'type': 'function'}
        >>> fn_info["selector"]
        '0x165c4a16'
        >>> fn_info["arguments"]
        (7, 3)
    """
    fn_abi = get_abi_element(
        abi, abi_element_identifier, *args, abi_codec=abi_codec, **kwargs
    )
    fn_selector = encode_hex(function_abi_to_4byte_selector(fn_abi))
    fn_inputs: Tuple[Any, ...] = tuple()

    if fn_abi["type"] == "fallback" or fn_abi["type"] == "receive":
        return ABIElementInfo(abi=fn_abi, selector=fn_selector, arguments=tuple())
    else:
        fn_inputs = get_normalized_abi_inputs(fn_abi, *args, **kwargs)
        _, aligned_fn_inputs = get_aligned_abi_inputs(fn_abi, fn_inputs)

        return ABIElementInfo(
            abi=fn_abi, selector=fn_selector, arguments=aligned_fn_inputs
        )


def get_abi_element(
    abi: ABI,
    abi_element_identifier: ABIElementIdentifier,
    *args: Optional[Any],
    abi_codec: Optional[Any] = None,
    **kwargs: Optional[Any],
) -> ABIElement:
    """
    Return the interface for an ``ABIElement`` from the ``abi`` that matches the
    provided identifier and arguments.

    ``abi`` may be a list of all ABI elements in a contract or a subset of elements.
    Passing only functions or events can be useful when names are not deterministic.
    For example, if names overlap between functions and events.

    The ``ABIElementIdentifier`` value may be a function name, signature, or a
    ``FallbackFn`` or ``ReceiveFn``. When named arguments (``args``) and/or keyword args
    (``kwargs``) are provided, they are included in the search filters.

    The `abi_codec` may be overridden if custom encoding and decoding is required. The
    default is used if no codec is provided. More details about customizations are in
    the `eth-abi Codecs Doc <https://eth-abi.readthedocs.io/en/latest/codecs.html>`__.

    :param abi: Contract ABI.
    :type abi: `ABI`
    :param abi_element_identifier: Find an element ABI with matching identifier. The \
    identifier may be a function name, signature, or ``FallbackFn`` or ``ReceiveFn``. \
    A function signature is in the form ``name(arg1Type,arg2Type,...)``.
    :type abi_element_identifier: `ABIElementIdentifier`
    :param args: Find an element ABI with matching args.
    :type args: `Optional[Sequence[Any]]`
    :param abi_codec: Codec used for encoding and decoding. Default with \
    `strict_bytes_type_checking` enabled.
    :type abi_codec: `Optional[Any]`
    :param kwargs: Find an element ABI with matching kwargs.
    :type kwargs: `Optional[Dict[str, Any]]`
    :return: ABI element for the specific ABI element.
    :rtype: `ABIElement`

    .. doctest::

        >>> from web3.utils.abi import get_abi_element
        >>> abi = [
        ...     {
        ...         "constant": False,
        ...         "inputs": [
        ...             {"name": "a", "type": "uint256"},
        ...             {"name": "b", "type": "uint256"},
        ...         ],
        ...         "name": "multiply",
        ...         "outputs": [{"name": "result", "type": "uint256"}],
        ...         "payable": False,
        ...         "stateMutability": "nonpayable",
        ...         "type": "function",
        ...     }
        ... ]
        >>> get_abi_element(abi, "multiply", *[7, 3])
        {'constant': False, 'inputs': [{'name': 'a', 'type': 'uint256'}, {\
'name': 'b', 'type': 'uint256'}], 'name': 'multiply', 'outputs': [{'name': 'result', \
'type': 'uint256'}], 'payable': False, 'stateMutability': 'nonpayable', \
'type': 'function'}
    """
    validate_abi(abi)

    if abi_codec is None:
        abi_codec = ABICodec(default_registry)

    abi_element_matches: Sequence[ABIElement] = pipe(
        abi,
        *_build_abi_filters(
            abi_element_identifier,
            *args,
            abi_codec=abi_codec,
            **kwargs,
        ),
    )

    num_matches = len(abi_element_matches)

    # Raise MismatchedABI unless one match is found
    if num_matches != 1:
        error_diagnosis = _mismatched_abi_error_diagnosis(
            abi_element_identifier,
            abi,
            num_matches,
            len(args) + len(kwargs),
            *args,
            abi_codec=abi_codec,
            **kwargs,
        )

        raise MismatchedABI(error_diagnosis)

    return abi_element_matches[0]


def check_if_arguments_can_be_encoded(
    abi_element: ABIElement,
    *args: Optional[Sequence[Any]],
    abi_codec: Optional[Any] = None,
    **kwargs: Optional[Dict[str, Any]],
) -> bool:
    """
    Check if the provided arguments can be encoded with the element ABI.

    :param abi_element: The ABI element.
    :type abi_element: `ABIElement`
    :param args: Positional arguments.
    :type args: `Optional[Sequence[Any]]`
    :param abi_codec: Codec used for encoding and decoding. Default with \
    `strict_bytes_type_checking` enabled.
    :type abi_codec: `Optional[Any]`
    :param kwargs: Keyword arguments.
    :type kwargs: `Optional[Dict[str, Any]]`
    :return: True if the arguments can be encoded, False otherwise.
    :rtype: `bool`

    .. doctest::

            >>> from web3.utils.abi import check_if_arguments_can_be_encoded
            >>> abi = {
            ...     "constant": False,
            ...     "inputs": [
            ...         {"name": "a", "type": "uint256"},
            ...         {"name": "b", "type": "uint256"},
            ...     ],
            ...     "name": "multiply",
            ...     "outputs": [{"name": "result", "type": "uint256"}],
            ...     "payable": False,
            ...     "stateMutability": "nonpayable",
            ...     "type": "function",
            ... }
            >>> check_if_arguments_can_be_encoded(abi, *[7, 3], **{})
            True
    """
    if abi_element["type"] == "fallback" or abi_element["type"] == "receive":
        return True

    try:
        arguments = get_normalized_abi_inputs(abi_element, *args, **kwargs)
    except TypeError:
        return False

    if len(abi_element.get("inputs", ())) != len(arguments):
        return False

    try:
        types, aligned_args = get_aligned_abi_inputs(abi_element, arguments)
    except TypeError:
        return False

    if abi_codec is None:
        abi_codec = ABICodec(default_registry)

    return all(
        abi_codec.is_encodable(_type, arg) for _type, arg in zip(types, aligned_args)
    )


@deprecated_for("get_abi_element")
def get_event_abi(
    abi: ABI,
    event_name: str,
    argument_names: Optional[Sequence[str]] = None,
) -> ABIEvent:
    """
    .. warning::
        This function is deprecated. It is unable to distinguish between
        overloaded events. Use ``get_abi_element`` instead.

    Find the event interface with the given name and/or arguments.

    :param abi: Contract ABI.
    :type abi: `ABI`
    :param event_name: Find an event abi with matching event name.
    :type event_name: `str`
    :param argument_names: Find an event abi with matching arguments.
    :type argument_names: `Optional[Sequence[str]]`
    :return: ABI for the event interface.
    :rtype: `ABIEvent`

    .. doctest::

        >>> from web3.utils import get_event_abi
        >>> abi = [
        ...   {"type": "function", "name": "myFunction", "inputs": [], "outputs": []},
        ...   {"type": "function", "name": "myFunction2", "inputs": [], "outputs": []},
        ...   {"type": "event", "name": "MyEvent", "inputs": []}
        ... ]
        >>> get_event_abi(abi, 'MyEvent')
        {'type': 'event', 'name': 'MyEvent', 'inputs': []}
    """
    filters: List[functools.partial[Sequence[ABIElement]]] = [
        functools.partial(filter_abi_by_type, "event"),
    ]

    if event_name is None or event_name == "":
        raise Web3ValidationError(
            "event_name is required in order to match an event ABI."
        )

    filters.append(functools.partial(filter_abi_by_name, event_name))

    if argument_names is not None:
        filters.append(functools.partial(filter_by_argument_name, argument_names))

    event_abi_candidates = cast(Sequence[ABIEvent], pipe(abi, *filters))

    if len(event_abi_candidates) == 1:
        return event_abi_candidates[0]
    elif len(event_abi_candidates) == 0:
        raise Web3ValueError("No matching events found")
    else:
        raise Web3ValueError("Multiple events found")


def get_event_log_topics(
    event_abi: ABIEvent,
    topics: Sequence[HexBytes],
) -> Sequence[HexBytes]:
    r"""
    Return topics for an event ABI.

    :param event_abi: Event ABI.
    :type event_abi: `ABIEvent`
    :param topics: Transaction topics from a `LogReceipt`.
    :type topics: `Sequence[HexBytes]`
    :return: Event topics for the event ABI.
    :rtype: `Sequence[HexBytes]`

    .. doctest::

        >>> from web3.utils import get_event_log_topics
        >>> abi = {
        ...   'type': 'event',
        ...   'anonymous': False,
        ...   'name': 'MyEvent',
        ...   'inputs': [
        ...     {
        ...       'name': 's',
        ...       'type': 'uint256'
        ...     }
        ...   ]
        ... }
        >>> keccak_signature = b'l+Ff\xba\x8d\xa5\xa9W\x17b\x1d\x87\x9aw\xder_=\x81g\t\xb9\xcb\xe9\xf0Y\xb8\xf8u\xe2\x84'  # noqa: E501
        >>> get_event_log_topics(abi, [keccak_signature, '0x1', '0x2'])
        ['0x1', '0x2']
    """
    if event_abi["anonymous"]:
        return topics
    elif not topics or len(topics) == 0:
        raise MismatchedABI("Expected non-anonymous event to have 1 or more topics")
    elif event_abi_to_log_topic(event_abi) != log_topic_to_bytes(topics[0]):
        raise MismatchedABI("The event signature did not match the provided ABI")
    else:
        return topics[1:]


def log_topic_to_bytes(
    log_topic: Union[Primitives, HexStr, str],
) -> bytes:
    r"""
    Return topic signature as bytes.

    :param log_topic: Event topic from a `LogReceipt`.
    :type log_topic: `Union[Primitives, HexStr, str]`
    :return: Topic signature as bytes.
    :rtype: `bytes`

    .. doctest::

        >>> from web3.utils import log_topic_to_bytes
        >>> log_topic_to_bytes('0xa12fd1')
        b'\xa1/\xd1'
    """
    return hexstr_if_str(to_bytes, log_topic)
