from typing import (
    Any,
    Dict,
    Iterable,
    Set,
    Union,
)

from web3.types import (
    TxData,
    TxParams,
)


def all_in_dict(
    values: Iterable[Any], d: Union[Dict[Any, Any], TxData, TxParams]
) -> bool:
    """
    Returns a bool based on whether ALL of the provided values exist
    among the keys of the provided dict-like object.

    :param values: An iterable with values to look for within the dict-like object
    :param d:      A dict-like object
    :return:       True if ALL values exist in keys;
                   False if NOT ALL values exist in keys
    """
    return all(_ in dict(d) for _ in values)


def any_in_dict(
    values: Iterable[Any], d: Union[Dict[Any, Any], TxData, TxParams]
) -> bool:
    """
    Returns a bool based on whether ANY of the provided values exist
    among the keys of the provided dict-like object.

    :param values: An iterable with values to look for within the dict-like object
    :param d:      A dict-like object
    :return:       True if ANY value exists in keys;
                   False if NONE of the values exist in keys
    """
    return any(_ in dict(d) for _ in values)


def none_in_dict(
    values: Iterable[Any], d: Union[Dict[Any, Any], TxData, TxParams]
) -> bool:
    """
    Returns a bool based on whether NONE of the provided values exist
    among the keys of the provided dict-like object.

    :param values: An iterable with values to look for within the dict-like object
    :param d:      A dict-like object
    :return:       True if NONE of the values exist in keys;
                   False if ANY value exists in keys
    """
    return not any_in_dict(values, d)


def either_set_is_a_subset(
    set1: Set[Any],
    set2: Set[Any],
    percentage: int = 100,
) -> bool:
    """
    Returns a bool based on whether two sets might have some differences but are mostly
    the same. This can be useful when comparing formatters to an actual response for
    formatting.

    :param set1:        A set of values.
    :param set2:        A second set of values.
    :param percentage:  The percentage of either set that must be present in the
                        other set; defaults to 100.
    :return:            True if one set's intersection with the other set is greater
                        than or equal to the given percentage of the other set.
    """
    threshold = percentage / 100

    return (
        len(set1.intersection(set2)) >= len(set1) * threshold
        or len(set2.intersection(set1)) >= len(set2) * threshold
    )
