from abc import ABC, abstractmethod
from typing import Generic, Iterable, List, Set, Tuple, TypeVar

T = TypeVar('T')
V = TypeVar('V')


class DataIterableMixin(Generic[T], ABC):
    @property
    @abstractmethod
    def iter_field_name(self) -> str:
        """
        This method should be overridden to provide the name of the field to be iterated over.
        """
        pass

    def iter(self) -> Iterable[T]:
        """
        Iterate over the field specified by `iter_field_name`.

        :return: An iterable of items from the specified field.
        """
        field = self.__getattribute__(self.iter_field_name)
        for item in field:
            yield item


class NestedDataIterableMixin(DataIterableMixin[T], Generic[T, V], ABC):
    def iter_nested(self) -> Iterable[V]:
        """
        Iterate over nested items in the field specified by `iter_field_name`.

        :return: An iterable of nested items from the specified field.
        """
        nested_iterable = self.__getattribute__(self.iter_field_name)
        for item in nested_iterable:
            if hasattr(item, 'iter_nested'):
                yield from item.iter_nested()
            elif hasattr(item, 'iter'):
                yield from item.iter()
            elif isinstance(item, (List, Tuple, Set)):
                yield from item
