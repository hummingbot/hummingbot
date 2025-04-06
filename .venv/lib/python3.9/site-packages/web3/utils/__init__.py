"""
NOTE: This is a public utility module. Any changes to these utility methods would
classify as breaking changes.
"""

from eth_utils.abi import (
    abi_to_signature,
    collapse_if_tuple,
    event_abi_to_log_topic,
    event_signature_to_log_topic,
    filter_abi_by_name,
    filter_abi_by_type,
    function_abi_to_4byte_selector,
    function_signature_to_4byte_selector,
    get_abi_input_names,
    get_abi_input_types,
    get_abi_output_names,
    get_abi_output_types,
    get_aligned_abi_inputs,
    get_all_event_abis,
    get_all_function_abis,
    get_normalized_abi_inputs,
)
from .abi import (  # NOQA
    check_if_arguments_can_be_encoded,
    get_abi_element_info,
    get_abi_element,
    get_event_abi,
    get_event_log_topics,
    log_topic_to_bytes,
)
from .address import (
    get_create_address,
)
from .async_exception_handling import (
    async_handle_offchain_lookup,
)
from .caching import (
    RequestCacheValidationThreshold,
    SimpleCache,
)
from .exception_handling import (
    handle_offchain_lookup,
)
from .subscriptions import (
    EthSubscription,
)

__all__ = [
    "abi_to_signature",
    "collapse_if_tuple",
    "event_abi_to_log_topic",
    "event_signature_to_log_topic",
    "filter_abi_by_name",
    "filter_abi_by_type",
    "function_abi_to_4byte_selector",
    "function_signature_to_4byte_selector",
    "get_abi_input_names",
    "get_abi_input_types",
    "get_abi_output_names",
    "get_abi_output_types",
    "get_aligned_abi_inputs",
    "get_all_event_abis",
    "get_all_function_abis",
    "get_normalized_abi_inputs",
    "check_if_arguments_can_be_encoded",
    "get_abi_element_info",
    "get_abi_element",
    "get_event_abi",
    "get_event_log_topics",
    "log_topic_to_bytes",
    "get_create_address",
    "async_handle_offchain_lookup",
    "RequestCacheValidationThreshold",
    "SimpleCache",
    "EthSubscription",
    "handle_offchain_lookup",
]
