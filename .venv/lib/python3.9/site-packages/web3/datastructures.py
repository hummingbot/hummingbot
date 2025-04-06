from collections import (
    OrderedDict,
)
from collections.abc import (
    Hashable,
)
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    ValuesView,
    cast,
)

from eth_utils import (
    is_integer,
)

from web3.exceptions import (
    Web3AssertionError,
    Web3TypeError,
    Web3ValueError,
)

# Hashable must be immutable:
# "the implementation of hashable collections requires that a
# key's hash value is immutable"
# https://docs.python.org/3/reference/datamodel.html#object.__hash__

T = TypeVar("T")
TKey = TypeVar("TKey", bound=Hashable)
TValue = TypeVar("TValue")


class ReadableAttributeDict(Mapping[TKey, TValue]):
    """
    The read attributes for the AttributeDict types
    """

    def __init__(
        self, dictionary: Dict[TKey, TValue], *args: Any, **kwargs: Any
    ) -> None:
        # type ignored on 46/50 b/c dict() expects str index type not TKey
        self.__dict__ = dict(dictionary)  # type: ignore
        self.__dict__.update(dict(*args, **kwargs))

    def __getitem__(self, key: TKey) -> TValue:
        return self.__dict__[key]  # type: ignore

    def __iter__(self) -> Iterator[Any]:
        return iter(self.__dict__)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __repr__(self) -> str:
        return self.__class__.__name__ + f"({self.__dict__!r})"

    def _repr_pretty_(self, builder: Any, cycle: bool) -> None:
        """
        Custom pretty output for the IPython console
        https://ipython.readthedocs.io/en/stable/api/generated/IPython.lib.pretty.html#extending  # noqa: E501
        """
        builder.text(self.__class__.__name__ + "(")
        if cycle:
            builder.text("<cycle>")
        else:
            builder.pretty(self.__dict__)
        builder.text(")")

    @classmethod
    def recursive(cls, value: TValue) -> Any:
        """
        Recursively convert mappings to ReadableAttributeDict instances and
        process nested collections (e.g., lists, sets, and dictionaries).
        """
        if isinstance(value, Mapping):
            return cls({k: cls.recursive(v) for k, v in value.items()})
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return type(value)([cls.recursive(v) for v in value])  # type: ignore
        elif isinstance(value, set):
            return {cls.recursive(v) for v in value}
        return value


class MutableAttributeDict(
    MutableMapping[TKey, TValue], ReadableAttributeDict[TKey, TValue]
):
    def __setitem__(self, key: Any, val: Any) -> None:
        self.__dict__[key] = val

    def __delitem__(self, key: Any) -> None:
        del self.__dict__[key]


class AttributeDict(ReadableAttributeDict[TKey, TValue], Hashable):
    """
    Provides superficial immutability, someone could hack around it
    """

    def __setattr__(self, attr: str, val: TValue) -> None:
        if attr == "__dict__":
            super().__setattr__(attr, val)
        else:
            raise Web3TypeError(
                "This data is immutable -- create a copy instead of modifying"
            )

    def __delattr__(self, key: str) -> None:
        raise Web3TypeError(
            "This data is immutable -- create a copy instead of modifying"
        )

    def __hash__(self) -> int:
        return hash(tuple(sorted(tupleize_lists_nested(self).items())))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, AttributeDict):
            return hash(self) == hash(other)
        elif isinstance(other, Mapping):
            return self.__dict__ == dict(other)
        else:
            return False


def tupleize_lists_nested(d: Mapping[TKey, TValue]) -> AttributeDict[TKey, TValue]:
    """
    Unhashable types inside dicts will throw an error if attempted to be hashed.
    This method converts lists to tuples, rendering them hashable.
    Other unhashable types found will raise a TypeError
    """

    def _to_tuple(value: Union[List[Any], Tuple[Any, ...]]) -> Any:
        return tuple(_to_tuple(i) if isinstance(i, (list, tuple)) else i for i in value)

    ret = dict()
    for k, v in d.items():
        if isinstance(v, (list, tuple)):
            ret[k] = _to_tuple(v)
        elif isinstance(v, Mapping):
            ret[k] = tupleize_lists_nested(v)
        elif not isinstance(v, Hashable):
            raise Web3TypeError(f"Found unhashable type '{type(v).__name__}': {v}")
        else:
            ret[k] = v
    return AttributeDict(ret)


class NamedElementOnion(Mapping[TKey, TValue]):
    """
    Add layers to an onion-shaped structure. Optionally, inject to a specific layer.
    This structure is iterable, where the outermost layer is first, and innermost
    is last.
    """

    def __init__(
        self,
        init_elements: Sequence[Any],
        valid_element: Callable[..., bool] = callable,
    ) -> None:
        self._queue: "OrderedDict[Any, Any]" = OrderedDict()
        for element in reversed(init_elements):
            if valid_element(element):
                self.add(element)
            else:
                self.add(*element)

    def add(self, element: TValue, name: Optional[TKey] = None) -> None:
        if name is None:
            name = cast(TKey, element)

        name = self._build_name(name)

        if name in self._queue:
            if name is element:
                raise Web3ValueError("You can't add the same un-named instance twice")
            else:
                raise Web3ValueError(
                    "You can't add the same name again, use replace instead"
                )

        self._queue[name] = element

    def inject(
        self, element: TValue, name: Optional[TKey] = None, layer: Optional[int] = None
    ) -> None:
        """
        Inject a named element to an arbitrary layer in the onion.

        The current implementation only supports insertion at the innermost layer,
        or at the outermost layer. Note that inserting to the outermost is equivalent
        to calling :meth:`add` .
        """
        if not is_integer(layer):
            raise Web3TypeError("The layer for insertion must be an int.")
        elif layer != 0 and layer != len(self._queue):
            raise NotImplementedError(
                f"You can only insert to the beginning or end of a {type(self)}, "
                f"currently. You tried to insert to {layer}, but only 0 and "
                f"{len(self._queue)} are permitted. "
            )

        self.add(element, name=name)

        if layer == 0:
            if name is None:
                name = cast(TKey, element)

            name = self._build_name(name)

            self._queue.move_to_end(name, last=False)
        elif layer == len(self._queue):
            return
        else:
            raise Web3AssertionError(
                "Impossible to reach: earlier validation raises an error"
            )

    def clear(self) -> None:
        self._queue.clear()

    def replace(self, old: TKey, new: TKey) -> TValue:
        old_name = self._build_name(old)

        if old_name not in self._queue:
            raise Web3ValueError(
                "You can't replace unless one already exists, use add instead"
            )

        to_be_replaced = self._queue[old_name]
        if to_be_replaced is old:
            # re-insert with new name in old slot
            self._replace_with_new_name(old, new)
        else:
            self._queue[old_name] = new
        return to_be_replaced

    @staticmethod
    def _build_name(value: TKey) -> TKey:
        try:
            value.__hash__()
            return value
        except TypeError:
            # unhashable, unnamed elements
            if not callable(value):
                raise Web3TypeError(
                    f"Expected a callable or hashable type, got {type(value)}"
                )
            # This will either be ``Web3Middleware`` class or the ``build`` method of a
            # ``Web3MiddlewareBuilder``. Instantiate with empty ``Web3`` and use a
            # unique identifier with the ``__hash__()`` as the name.
            v = value(None)
            return cast(TKey, f"{v.__class__}<{v.__hash__()}>")

    def remove(self, old: TKey) -> None:
        old_name = self._build_name(old)
        if old_name not in self._queue:
            raise Web3ValueError("You can only remove something that has been added")
        del self._queue[old_name]

    @property
    def middleware(self) -> Sequence[Any]:
        """
        Returns middleware in the appropriate order to be imported into a new Web3
        instance (reversed _queue order) as a list of (middleware, name) tuples.
        """
        return [(val, key) for key, val in reversed(self._queue.items())]

    def _replace_with_new_name(self, old: TKey, new: TKey) -> None:
        old_name = self._build_name(old)
        new_name = self._build_name(new)

        self._queue[new_name] = new
        found_old = False
        for key in list(self._queue.keys()):
            if not found_old:
                if key == old_name:
                    found_old = True
                continue
            elif key != new_name:
                self._queue.move_to_end(key)
        del self._queue[old_name]

    def __add__(self, other: Any) -> "NamedElementOnion[TKey, TValue]":
        if not isinstance(other, NamedElementOnion):
            # you can only combine with another ``NamedElementOnion``
            return NotImplemented
        combined = self._queue.copy()
        combined.update(other._queue)
        return NamedElementOnion(cast(List[Any], combined.items()))

    def __contains__(self, element: Any) -> bool:
        element_name = self._build_name(element)
        return element_name in self._queue

    def __getitem__(self, element: TKey) -> TValue:
        element_name = self._build_name(element)
        return self._queue[element_name]

    def __len__(self) -> int:
        return len(self._queue)

    def __reversed__(self) -> Iterator[TValue]:
        elements = cast(List[Any], self._queue.values())
        if not isinstance(elements, Sequence):
            elements = list(elements)
        return iter(elements)

    # --- iter and tupleize methods --- #

    def _reversed_middleware(self) -> Iterator[TValue]:
        elements = self._queue.values()
        if not isinstance(elements, Sequence):
            # type ignored b/c elements is set as _OrderedDictValuesView[Any] on 210
            elements = list(elements)  # type: ignore
        return reversed(elements)

    def as_tuple_of_middleware(self) -> Tuple[TValue, ...]:
        """
        Helps with type hinting since we return `Iterator[TKey]` type, though it's
        actually a `Iterator[TValue]` type, for the `__iter__()` method. This is in
        order to satisfy the `Mapping` interface.
        """
        return tuple(self._reversed_middleware())

    def __iter__(self) -> Iterator[TKey]:
        # ``__iter__()`` for a ``Mapping``  returns ``Iterator[TKey]`` but this
        # implementation returns ``Iterator[TValue]`` on reversed values (not keys).
        # This leads to typing issues, so it's better to use
        # ``as_tuple_of_middleware()`` to achieve the same result.
        return iter(self._reversed_middleware())  # type: ignore

    def values(self) -> ValuesView[TValue]:
        return ValuesView(self._queue)
