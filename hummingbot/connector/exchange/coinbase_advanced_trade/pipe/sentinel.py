from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .data_types import PipeTupleDataT


class Sentinel:
    def __init__(self):
        pass

    def __repr__(self):
        return "Sentinel()"


SENTINEL: Sentinel = Sentinel()


def sentinel_ize(items: "PipeTupleDataT") -> "PipeTupleDataT":
    """
    Returns a tuple with a sentinel value at the end. If a sentinel value is already present in the tuple,
    it returns a new tuple up to the first sentinel. If no sentinel is present, it adds one to the end of the tuple.

    :param items: A tuple of items, which may include a sentinel value.
    :return: A tuple with a sentinel value at the end.
    :raises ValueError: If there are multiple sentinel values in the tuple.
    """
    if not isinstance(items, tuple):
        items = (items,)

    try:
        sentinel_index = items.index(SENTINEL)
        return items[:sentinel_index + 1]
    except ValueError:
        return items + (SENTINEL,)
