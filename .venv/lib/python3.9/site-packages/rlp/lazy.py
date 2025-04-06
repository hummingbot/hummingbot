from collections.abc import (
    Iterable,
    Sequence,
)

from .atomic import (
    Atomic,
)
from .codec import (
    consume_length_prefix,
    consume_payload,
)
from .exceptions import (
    DecodingError,
)


def decode_lazy(rlp, sedes=None, **sedes_kwargs):
    """
    Decode an RLP encoded object in a lazy fashion.

    If the encoded object is a bytestring, this function acts similar to
    :func:`rlp.decode`. If it is a list however, a :class:`LazyList` is
    returned instead. This object will decode the string lazily, avoiding
    both horizontal and vertical traversing as much as possible.

    The way `sedes` is applied depends on the decoded object: If it is a string
    `sedes` deserializes it as a whole; if it is a list, each element is
    deserialized individually. In both cases, `sedes_kwargs` are passed on.
    Note that, if a deserializer is used, only "horizontal" but not
    "vertical lazyness" can be preserved.

    :param rlp: the RLP string to decode
    :param sedes: an object implementing a method ``deserialize(code)`` which
                  is used as described above, or ``None`` if no
                  deserialization should be performed
    :param `**sedes_kwargs`: additional keyword arguments that will be passed
                             to the deserializers
    :returns: either the already decoded and deserialized object (if encoded as
              a string) or an instance of :class:`rlp.LazyList`
    """
    item, end = consume_item_lazy(rlp, 0)
    if end != len(rlp):
        raise DecodingError("RLP length prefix announced wrong length", rlp)
    if isinstance(item, LazyList):
        item.sedes = sedes
        item.sedes_kwargs = sedes_kwargs
        return item
    elif sedes:
        return sedes.deserialize(item, **sedes_kwargs)
    else:
        return item


def consume_item_lazy(rlp, start):
    """
    Read an item from an RLP string lazily.

    If the length prefix announces a string, the string is read; if it
    announces a list, a :class:`LazyList` is created.

    :param rlp: the rlp string to read from
    :param start: the position at which to start reading
    :returns: a tuple ``(item, end)`` where ``item`` is the read string or a
              :class:`LazyList` and ``end`` is the position of the first
              unprocessed byte.
    """
    p, t, l, s = consume_length_prefix(rlp, start)
    if t is bytes:
        item, _, end = consume_payload(rlp, p, s, bytes, l)
        return item, end
    else:
        assert t is list
        return LazyList(rlp, s, s + l), s + l


class LazyList(Sequence):
    """
    A RLP encoded list which decodes itself when necessary.

    Both indexing with positive indices and iterating are supported.
    Getting the length with :func:`len` is possible as well but requires full
    horizontal encoding.

    :param rlp: the rlp string in which the list is encoded
    :param start: the position of the first payload byte of the encoded list
    :param end: the position of the last payload byte of the encoded list
    :param sedes: a sedes object which deserializes each element of the list,
                  or ``None`` for no deserialization
    :param `**sedes_kwargs`: keyword arguments which will be passed on to the
                             deserializer
    """

    def __init__(self, rlp, start, end, sedes=None, **sedes_kwargs):
        self.rlp = rlp
        self.start = start
        self.end = end
        self.index = start
        self._elements = []
        self._len = None
        self.sedes = sedes
        self.sedes_kwargs = sedes_kwargs

    def next(self):
        if self.index == self.end:
            self._len = len(self._elements)
            raise StopIteration
        assert self.index < self.end
        item, end = consume_item_lazy(self.rlp, self.index)
        self.index = end
        if self.sedes:
            item = self.sedes.deserialize(item, **self.sedes_kwargs)
        self._elements.append(item)
        return item

    def __getitem__(self, i):
        if isinstance(i, slice):
            if i.step is not None:
                raise TypeError("Step not supported")
            start = i.start
            stop = i.stop
        else:
            start = i
            stop = i + 1

        if stop is None:
            stop = self.end - 1

        try:
            while len(self._elements) < stop:
                self.next()
        except StopIteration:
            assert self.index == self.end
            raise IndexError("Index %s out of range" % i)

        if isinstance(i, slice):
            return self._elements[start:stop]
        else:
            return self._elements[start]

    def __len__(self):
        if not self._len:
            try:
                while True:
                    self.next()
            except StopIteration:
                self._len = len(self._elements)
        return self._len


def peek(rlp, index, sedes=None):
    """
    Get a specific element from an rlp encoded nested list.

    This function uses :func:`rlp.decode_lazy` and, thus, decodes only the
    necessary parts of the string.

    Usage example::

        >>> import rlp
        >>> rlpdata = rlp.encode([1, 2, [3, [4, 5]]])
        >>> rlp.peek(rlpdata, 0, rlp.sedes.big_endian_int)
        1
        >>> rlp.peek(rlpdata, [2, 0], rlp.sedes.big_endian_int)
        3

    :param rlp: the rlp string
    :param index: the index of the element to peek at (can be a list for
                  nested data)
    :param sedes: a sedes used to deserialize the peeked at object, or `None`
                  if no deserialization should be performed
    :raises: :exc:`IndexError` if `index` is invalid (out of range or too many
             levels)
    """
    ll = decode_lazy(rlp)
    if not isinstance(index, Iterable):
        index = [index]
    for i in index:
        if isinstance(ll, Atomic):
            raise IndexError("Too many indices given")
        ll = ll[i]
    if sedes:
        return sedes.deserialize(ll)
    else:
        return ll
