import collections

from eth_utils import (
    big_endian_to_int,
    int_to_big_endian,
    is_bytes,
)

from rlp.exceptions import (
    DecodingError,
    EncodingError,
)
from rlp.sedes import (
    big_endian_int,
    binary,
    boolean,
    text,
)
from rlp.sedes.binary import (
    Binary as BinaryClass,
)
from rlp.sedes.lists import (
    List,
    is_sedes,
    is_sequence,
)
from rlp.sedes.serializable import (
    Serializable,
)
from rlp.utils import (
    ALL_BYTES,
)

try:
    import rusty_rlp
except ImportError:
    import logging

    from rlp.atomic import (
        Atomic,
    )

    logger = logging.getLogger("rlp.codec")
    logger.debug(
        "Consider installing rusty-rlp to improve pyrlp performance with a rust based"
        "backend. Not currently functional for Python 3.11"
    )

    def encode_raw(item):
        r"""RLP encode (a nested sequence of) :class:`Atomic`\s."""
        if isinstance(item, Atomic):
            if len(item) == 1 and item[0] < 128:
                return item
            payload = item
            prefix_offset = 128  # string
        elif not isinstance(item, str) and isinstance(item, collections.abc.Sequence):
            payload = b"".join(encode_raw(x) for x in item)
            prefix_offset = 192  # list
        else:
            msg = f"Cannot encode object of type {type(item).__name__}"
            raise EncodingError(msg, item)

        try:
            prefix = length_prefix(len(payload), prefix_offset)
        except ValueError:
            raise EncodingError("Item too big to encode", item)

        return prefix + payload

    def decode_raw(item, strict, _):
        try:
            result, per_item_rlp, end = consume_item(item, 0)
        except IndexError:
            raise DecodingError("RLP string too short", item)
        if end != len(item) and strict:
            msg = f"RLP string ends with {len(item) - end} superfluous bytes"
            raise DecodingError(msg, item)

        return result, per_item_rlp

else:

    def decode_raw(item, strict, preserve_per_item_rlp):
        try:
            return rusty_rlp.decode_raw(item, strict, preserve_per_item_rlp)
        except (TypeError, rusty_rlp.DecodingError) as e:
            raise DecodingError(e, item)

    def encode_raw(obj):
        try:
            if isinstance(obj, bytearray):
                obj = bytes(obj)
            return rusty_rlp.encode_raw(obj)
        except rusty_rlp.EncodingError as e:
            raise EncodingError(e, obj)


def encode(obj, sedes=None, infer_serializer=True, cache=True):
    """
    Encode a Python object in RLP format.

    By default, the object is serialized in a suitable way first (using
    :func:`rlp.infer_sedes`) and then encoded. Serialization can be explicitly
    suppressed by setting `infer_serializer` to ``False`` and not passing an
    alternative as `sedes`.

    If `obj` has an attribute :attr:`_cached_rlp` (as, notably,
    :class:`rlp.Serializable`) and its value is not `None`, this value is
    returned bypassing serialization and encoding, unless `sedes` is given (as
    the cache is assumed to refer to the standard serialization which can be
    replaced by specifying `sedes`).

    If `obj` is a :class:`rlp.Serializable` and `cache` is true, the result of
    the encoding will be stored in :attr:`_cached_rlp` if it is empty.

    :param sedes: an object implementing a function ``serialize(obj)`` which will be
                  used to serialize ``obj`` before encoding, or ``None`` to use the
                  infered one (if any)
    :param infer_serializer: if ``True`` an appropriate serializer will be selected
                             using :func:`rlp.infer_sedes` to serialize `obj` before
                             encoding
    :param cache: cache the return value in `obj._cached_rlp` if possible
                  (default `True`)
    :returns: the RLP encoded item
    :raises: :exc:`rlp.EncodingError` in the rather unlikely case that the item is too
             big to encode (will not happen)
    :raises: :exc:`rlp.SerializationError` if the serialization fails
    """
    if isinstance(obj, Serializable):
        cached_rlp = obj._cached_rlp
        if sedes is None and cached_rlp:
            return cached_rlp
        else:
            really_cache = cache and sedes is None
    else:
        really_cache = False

    if sedes:
        item = sedes.serialize(obj)
    elif infer_serializer:
        item = infer_sedes(obj).serialize(obj)
    else:
        item = obj

    result = encode_raw(item)
    if really_cache:
        obj._cached_rlp = result
    return result


LONG_LENGTH = 256**8


def length_prefix(length, offset):
    """
    Construct the prefix to lists or strings denoting their length.

    :param length: the length of the item in bytes
    :param offset: ``0x80`` when encoding raw bytes, ``0xc0`` when encoding a
                   list
    """
    if length < 56:
        return ALL_BYTES[offset + length]
    elif length < LONG_LENGTH:
        length_string = int_to_big_endian(length)
        return ALL_BYTES[offset + 56 - 1 + len(length_string)] + length_string
    else:
        raise ValueError("Length greater than 256**8")


SHORT_STRING = 128 + 56


def consume_length_prefix(rlp, start):
    """
    Read a length prefix from an RLP string.

    :param rlp: the rlp byte string to read from
    :param start: the position at which to start reading
    :returns: a tuple ``(prefix, type, length, end)``, where ``type`` is either ``str``
              or ``list`` depending on the type of the following payload,
              ``length`` is the length of the payload in bytes, and ``end`` is
              the position of the first payload byte in the rlp string
    """
    b0 = rlp[start]
    if b0 < 128:  # single byte
        return (b"", bytes, 1, start)
    elif b0 < SHORT_STRING:  # short string
        if b0 - 128 == 1 and rlp[start + 1] < 128:
            raise DecodingError(
                "Encoded as short string although single byte was possible", rlp
            )
        return (rlp[start : start + 1], bytes, b0 - 128, start + 1)
    elif b0 < 192:  # long string
        ll = b0 - 183  # - (128 + 56 - 1)
        if rlp[start + 1 : start + 2] == b"\x00":
            raise DecodingError("Length starts with zero bytes", rlp)
        len_prefix = rlp[start + 1 : start + 1 + ll]
        l = big_endian_to_int(len_prefix)  # noqa: E741
        if l < 56:
            raise DecodingError("Long string prefix used for short string", rlp)
        return (rlp[start : start + 1] + len_prefix, bytes, l, start + 1 + ll)
    elif b0 < 192 + 56:  # short list
        return (rlp[start : start + 1], list, b0 - 192, start + 1)
    else:  # long list
        ll = b0 - 192 - 56 + 1
        if rlp[start + 1 : start + 2] == b"\x00":
            raise DecodingError("Length starts with zero bytes", rlp)
        len_prefix = rlp[start + 1 : start + 1 + ll]
        l = big_endian_to_int(len_prefix)  # noqa: E741
        if l < 56:
            raise DecodingError("Long list prefix used for short list", rlp)
        return (rlp[start : start + 1] + len_prefix, list, l, start + 1 + ll)


def consume_payload(rlp, prefix, start, type_, length):
    """
    Read the payload of an item from an RLP string.

    :param rlp: the rlp string to read from
    :param type_: the type of the payload (``bytes`` or ``list``)
    :param start: the position at which to start reading
    :param length: the length of the payload in bytes
    :returns: a tuple ``(item, per_item_rlp, end)``, where ``item`` is
              the read item, per_item_rlp is a list containing the RLP
              encoding of each item and ``end`` is the position of the
              first unprocessed byte
    """
    if type_ is bytes:
        item = rlp[start : start + length]
        return (item, [prefix + item], start + length)
    elif type_ is list:
        items = []
        per_item_rlp = []
        list_rlp = prefix
        next_item_start = start
        end = next_item_start + length
        while next_item_start < end:
            p, t, l, s = consume_length_prefix(rlp, next_item_start)
            item, item_rlp, next_item_start = consume_payload(rlp, p, s, t, l)
            per_item_rlp.append(item_rlp)
            # When the item returned above is a single element, item_rlp will also
            # contain a single element, but when it's a list, the first element will be
            # the RLP of the whole List, which is what we want here.
            list_rlp += item_rlp[0]
            items.append(item)
        per_item_rlp.insert(0, list_rlp)
        if next_item_start > end:
            raise DecodingError(
                "List length prefix announced a too small " "length", rlp
            )
        return (items, per_item_rlp, next_item_start)
    else:
        raise TypeError("Type must be either list or bytes")


def consume_item(rlp, start):
    """
    Read an item from an RLP string.

    :param rlp: the rlp string to read from
    :param start: the position at which to start reading
    :returns: a tuple ``(item, per_item_rlp, end)``, where ``item`` is
              the read item, per_item_rlp is a list containing the RLP
              encoding of each item and ``end`` is the position of the
              first unprocessed byte
    """
    p, t, l, s = consume_length_prefix(rlp, start)
    return consume_payload(rlp, p, s, t, l)


def decode(rlp, sedes=None, strict=True, recursive_cache=False, **kwargs):
    """
    Decode an RLP encoded object.

    If the deserialized result `obj` has an attribute :attr:`_cached_rlp` (e.g. if
    `sedes` is a subclass of :class:`rlp.Serializable`) it will be set to `rlp`, which
    will improve performance on subsequent :func:`rlp.encode` calls. Bear in mind
    however that `obj` needs to make sure that this value is updated whenever one of its
    fields changes or prevent such changes entirely (:class:`rlp.sedes.Serializable`
    does the latter).

    :param sedes: an object implementing a function ``deserialize(code)`` which will be
                  applied after decoding, or ``None`` if no deserialization should be
                  performed
    :param `**kwargs`: additional keyword arguments that will be passed to the
                       deserializer
    :param strict: if false inputs that are longer than necessary don't cause an
                   exception
    :returns: the decoded and maybe deserialized Python object
    :raises: :exc:`rlp.DecodingError` if the input string does not end after the root
             item and `strict` is true
    :raises: :exc:`rlp.DeserializationError` if the deserialization fails
    """
    if not is_bytes(rlp):
        raise DecodingError(
            "Can only decode RLP bytes, got type %s" % type(rlp).__name__, rlp
        )

    item, per_item_rlp = decode_raw(rlp, strict, recursive_cache)

    if len(per_item_rlp) == 0:
        per_item_rlp = [rlp]

    if sedes:
        obj = sedes.deserialize(item, **kwargs)
        if is_sequence(obj) or hasattr(obj, "_cached_rlp"):
            _apply_rlp_cache(obj, per_item_rlp, recursive_cache)
        return obj
    else:
        return item


def _apply_rlp_cache(obj, split_rlp, recursive):
    item_rlp = split_rlp.pop(0)
    if isinstance(obj, (int, bool, str, bytes, bytearray)):
        return
    elif hasattr(obj, "_cached_rlp"):
        obj._cached_rlp = item_rlp
    if not recursive:
        return
    for sub in obj:
        if isinstance(sub, (int, bool, str, bytes, bytearray)):
            split_rlp.pop(0)
        else:
            sub_rlp = split_rlp.pop(0)
            _apply_rlp_cache(sub, sub_rlp, recursive)


def infer_sedes(obj):
    """
    Try to find a sedes objects suitable for a given Python object.

    The sedes objects considered are `obj`'s class, `big_endian_int` and
    `binary`. If `obj` is a sequence, a :class:`rlp.sedes.List` will be
    constructed recursively.

    :param obj: the python object for which to find a sedes object
    :raises: :exc:`TypeError` if no appropriate sedes could be found
    """
    if is_sedes(obj.__class__):
        return obj.__class__
    elif not isinstance(obj, bool) and isinstance(obj, int) and obj >= 0:
        return big_endian_int
    elif BinaryClass.is_valid_type(obj):
        return binary
    elif not isinstance(obj, str) and isinstance(obj, collections.abc.Sequence):
        return List(map(infer_sedes, obj))
    elif isinstance(obj, bool):
        return boolean
    elif isinstance(obj, str):
        return text
    msg = f"Did not find sedes handling type {type(obj).__name__}"
    raise TypeError(msg)
