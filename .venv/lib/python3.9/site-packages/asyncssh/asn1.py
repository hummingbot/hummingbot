# Copyright (c) 2013-2024 by Ron Frederick <ronf@timeheart.net> and others.
#
# This program and the accompanying materials are made available under
# the terms of the Eclipse Public License v2.0 which accompanies this
# distribution and is available at:
#
#     http://www.eclipse.org/legal/epl-2.0/
#
# This program may also be made available under the following secondary
# licenses when the conditions for such availability set forth in the
# Eclipse Public License v2.0 are satisfied:
#
#    GNU General Public License, Version 2.0, or any later versions of
#    that license
#
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later
#
# Contributors:
#     Ron Frederick - initial implementation, API, and documentation

"""Utilities for encoding and decoding ASN.1 DER data

   The der_encode function takes a Python value and encodes it in DER
   format, returning a byte string. In addition to supporting standard
   Python types, BitString can be used to encode a DER bit string,
   ObjectIdentifier can be used to encode OIDs, values can be wrapped
   in a TaggedDERObject to set an alternate DER tag on them, and
   non-standard types can be encoded by placing them in a RawDERObject.

   The der_decode function takes a byte string in DER format and decodes
   it into the corresponding Python values.

"""

from typing import Dict, FrozenSet, Sequence, Set, Tuple, Type, TypeVar, Union
from typing import cast


_DERClass = Type['DERType']
_DERClassVar = TypeVar('_DERClassVar', bound='_DERClass')


# ASN.1 object classes
UNIVERSAL         = 0x00
APPLICATION       = 0x01
CONTEXT_SPECIFIC  = 0x02
PRIVATE           = 0x03

# ASN.1 universal object tags
END_OF_CONTENT    = 0x00
BOOLEAN           = 0x01
INTEGER           = 0x02
BIT_STRING        = 0x03
OCTET_STRING      = 0x04
NULL              = 0x05
OBJECT_IDENTIFIER = 0x06
UTF8_STRING       = 0x0c
SEQUENCE          = 0x10
SET               = 0x11
IA5_STRING        = 0x16

_asn1_class = ('Universal', 'Application', 'Context-specific', 'Private')

_der_class_by_tag: Dict[int, _DERClass] = {}
_der_class_by_type: Dict[Union[object, _DERClass], _DERClass] = {}


def _encode_identifier(asn1_class: int, constructed: bool, tag: int) -> bytes:
    """Encode a DER object's identifier"""

    if asn1_class not in (UNIVERSAL, APPLICATION, CONTEXT_SPECIFIC, PRIVATE):
        raise ASN1EncodeError('Invalid ASN.1 class')

    flags = (asn1_class << 6) | (0x20 if constructed else 0x00)

    if tag < 0x20:
        identifier = [flags | tag]
    else:
        identifier = [tag & 0x7f]

        while tag >= 0x80:
            tag >>= 7
            identifier.append(0x80 | (tag & 0x7f))

        identifier.append(flags | 0x1f)

    return bytes(identifier[::-1])


class ASN1Error(ValueError):
    """ASN.1 coding error"""


class ASN1EncodeError(ASN1Error):
    """ASN.1 DER encoding error"""


class ASN1DecodeError(ASN1Error):
    """ASN.1 DER decoding error"""


class DERType:
    """Parent class for classes which use DERTag decorator"""

    identifier: bytes = b''

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode value as a DER byte string"""

        raise NotImplementedError

    @classmethod
    def decode(cls, constructed: bool, content: bytes) -> object:
        """Decode a DER byte string into an object"""

        raise NotImplementedError


class DERTag:
    """A decorator used by classes which convert values to/from DER

       Classes which convert Python values to and from DER format
       should use the DERTag decorator to indicate what DER tag value
       they understand. When DER data is decoded, the tag is looked
       up in the list to see which class to call to perform the
       decoding.

       Classes which convert existing Python types to and from DER
       format can specify the list of types they understand in the
       optional "types" argument. Otherwise, conversion is expected
       to be to and from the new class being defined.

    """

    def __init__(self, tag: int, types: Sequence[object] = (),
                 constructed: bool = False):
        self._tag = tag
        self._types = types
        self._identifier = _encode_identifier(UNIVERSAL, constructed, tag)

    def __call__(self, cls: _DERClassVar) -> _DERClassVar:
        cls.identifier = self._identifier

        _der_class_by_tag[self._tag] = cls

        if self._types:
            for t in self._types:
                _der_class_by_type[t] = cls
        else:
            _der_class_by_type[cls] = cls

        return cls


class RawDERObject:
    """A class which can encode a DER object of an arbitrary type

       This object is initialized with an ASN.1 class, tag, and a
       byte string representing the already encoded data. Such
       objects will never have the constructed flag set, since
       that is represented here as a TaggedDERObject.

    """

    def __init__(self, tag: int, content: bytes, asn1_class: int):
        self.asn1_class = asn1_class
        self.tag = tag
        self.content = content

    def __repr__(self) -> str:
        return f'RawDERObject({_asn1_class[self.asn1_class]}, ' \
               f'{self.tag}, {self.content!r})'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RawDERObject): # pragma: no cover
            return NotImplemented

        return (self.asn1_class == other.asn1_class and
                self.tag == other.tag and self.content == other.content)

    def __hash__(self) -> int:
        return hash((self.asn1_class, self.tag, self.content))

    def encode_identifier(self) -> bytes:
        """Encode the DER identifier for this object as a byte string"""

        return _encode_identifier(self.asn1_class, False, self.tag)

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode the content for this object as a DER byte string"""

        return cast('RawDERObject', value).content


class TaggedDERObject:
    """An explicitly tagged DER object

       This object provides a way to wrap an ASN.1 object with an
       explicit tag. The value (including the tag representing its
       actual type) is then encoded as part of its value. By
       default, the ASN.1 class for these objects is CONTEXT_SPECIFIC,
       and the DER encoding always marks these values as constructed.

    """

    def __init__(self, tag: int, value: object,
                 asn1_class: int = CONTEXT_SPECIFIC):
        self.asn1_class = asn1_class
        self.tag = tag
        self.value = value

    def __repr__(self) -> str:
        if self.asn1_class == CONTEXT_SPECIFIC:
            return f'TaggedDERObject({self.tag}, {self.value!r})'
        else:
            return f'TaggedDERObject({_asn1_class[self.asn1_class]}, ' \
                   f'{self.tag}, {self.value!r})'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TaggedDERObject): # pragma: no cover
            return NotImplemented

        return (self.asn1_class == other.asn1_class and
                self.tag == other.tag and self.value == other.value)

    def __hash__(self) -> int:
        return hash((self.asn1_class, self.tag, self.value))

    def encode_identifier(self) -> bytes:
        """Encode the DER identifier for this object as a byte string"""

        return _encode_identifier(self.asn1_class, True, self.tag)

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode the content for this object as a DER byte string"""

        return der_encode(cast('TaggedDERObject', value).value)


@DERTag(NULL, (type(None),))
class _Null(DERType):
    """A null value"""

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode a DER null value"""

        # pylint: disable=unused-argument

        return b''

    @classmethod
    def decode(cls, constructed: bool, content: bytes) -> None:
        """Decode a DER null value"""

        if constructed:
            raise ASN1DecodeError('NULL should not be constructed')

        if content:
            raise ASN1DecodeError('NULL should not have associated content')

        return None


@DERTag(BOOLEAN, (bool,))
class _Boolean(DERType):
    """A boolean value"""

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode a DER boolean value"""

        return b'\xff' if value else b'\0'

    @classmethod
    def decode(cls, constructed: bool, content: bytes) -> bool:
        """Decode a DER boolean value"""

        if constructed:
            raise ASN1DecodeError('BOOLEAN should not be constructed')

        if content not in {b'\x00', b'\xff'}:
            raise ASN1DecodeError('BOOLEAN content must be 0x00 or 0xff')

        return bool(content[0])


@DERTag(INTEGER, (int,))
class _Integer(DERType):
    """An integer value"""

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode a DER integer value"""

        i = cast(int, value)
        l = i.bit_length()
        l = l // 8 + 1 if l % 8 == 0 else (l + 7) // 8
        result = i.to_bytes(l, 'big', signed=True)
        return result[1:] if result.startswith(b'\xff\x80') else result

    @classmethod
    def decode(cls, constructed: bool, content: bytes) -> int:
        """Decode a DER integer value"""

        if constructed:
            raise ASN1DecodeError('INTEGER should not be constructed')

        return int.from_bytes(content, 'big', signed=True)


@DERTag(OCTET_STRING, (bytes, bytearray))
class _OctetString(DERType):
    """An octet string value"""

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode a DER octet string"""

        return cast(bytes, value)

    @classmethod
    def decode(cls, constructed: bool, content: bytes) -> bytes:
        """Decode a DER octet string"""

        if constructed:
            raise ASN1DecodeError('OCTET STRING should not be constructed')

        return content


@DERTag(UTF8_STRING, (str,))
class _UTF8String(DERType):
    """A UTF-8 string value"""

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode a DER UTF-8 string"""

        return cast(str, value).encode('utf-8')

    @classmethod
    def decode(cls, constructed: bool, content: bytes) -> str:
        """Decode a DER UTF-8 string"""

        if constructed:
            raise ASN1DecodeError('UTF8 STRING should not be constructed')

        return content.decode('utf-8')


@DERTag(SEQUENCE, (list, tuple), constructed=True)
class _Sequence(DERType):
    """A sequence of values"""

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode a sequence of DER values"""

        seq_value = cast(Sequence[object], value)
        return b''.join(der_encode(item) for item in seq_value)

    @classmethod
    def decode(cls, constructed: bool, content: bytes) -> Sequence[object]:
        """Decode a sequence of DER values"""

        if not constructed:
            raise ASN1DecodeError('SEQUENCE should always be constructed')

        offset = 0
        length = len(content)

        value = []
        while offset < length:
            item, consumed = der_decode_partial(content[offset:])
            value.append(item)
            offset += consumed

        return tuple(value)


@DERTag(SET, (set, frozenset), constructed=True)
class _Set(DERType):
    """A set of DER values"""

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode a set of DER values"""

        set_value = cast(Union[FrozenSet[object], Set[object]], value)
        return b''.join(sorted(der_encode(item) for item in set_value))

    @classmethod
    def decode(cls, constructed: bool, content: bytes) -> FrozenSet[object]:
        """Decode a set of DER values"""

        if not constructed:
            raise ASN1DecodeError('SET should always be constructed')

        offset = 0
        length = len(content)

        value = set()
        while offset < length:
            item, consumed = der_decode_partial(content[offset:])
            value.add(item)
            offset += consumed

        return frozenset(value)


@DERTag(BIT_STRING)
class BitString(DERType):
    """A string of bits

       This object can be initialized either with a byte string and an
       optional count of the number of least-significant bits in the last
       byte which should not be included in the value, or with a string
       consisting only of the digits '0' and '1'.

       An optional 'named' flag can also be set, indicating that the
       BitString was specified with named bits, indicating that the proper
       DER encoding of it should strip any trailing zeroes.

    """

    def __init__(self, value: object, unused: int = 0, named: bool = False):
        if unused < 0 or unused > 7:
            raise ASN1EncodeError('Unused bit count must be between 0 and 7')

        if isinstance(value, bytes):
            if unused:
                if not value:
                    raise ASN1EncodeError('Can\'t have unused bits with empty '
                                          'value')
                elif value[-1] & ((1 << unused) - 1):
                    raise ASN1EncodeError('Unused bits in value should be '
                                          'zero')
        elif isinstance(value, str):
            if unused:
                raise ASN1EncodeError('Unused bit count should not be set '
                                      'when providing a string')

            used = len(value) % 8
            unused = 8 - used if used else 0
            value += unused * '0'
            value = bytes(int(value[i:i+8], 2)
                          for i in range(0, len(value), 8))
        else:
            raise ASN1EncodeError('Unexpected type of bit string value')

        if named:
            while value and not value[-1] & (1 << unused):
                unused += 1
                if unused == 8:
                    value = value[:-1]
                    unused = 0

        self.value = value
        self.unused = unused

    def __str__(self) -> str:
        result = ''.join(bin(b)[2:].zfill(8) for b in self.value)
        if self.unused:
            result = result[:-self.unused]
        return result

    def __repr__(self) -> str:
        return f"BitString('{self}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BitString): # pragma: no cover
            return NotImplemented

        return self.value == other.value and self.unused == other.unused

    def __hash__(self) -> int:
        return hash((self.value, self.unused))

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode a DER bit string"""

        bitstr_value = cast('BitString', value)
        return bytes((bitstr_value.unused,)) + bitstr_value.value

    @classmethod
    def decode(cls, constructed: bool, content: bytes) -> 'BitString':
        """Decode a DER bit string"""

        if constructed:
            raise ASN1DecodeError('BIT STRING should not be constructed')

        if not content or content[0] > 7:
            raise ASN1DecodeError('Invalid unused bit count')

        return cls(content[1:], unused=content[0])


@DERTag(IA5_STRING)
class IA5String(DERType):
    """An ASCII string value"""

    def __init__(self, value: Union[bytes, bytearray]):
        self.value = value

    def __str__(self) -> str:
        return self.value.decode('ascii')

    def __repr__(self) -> str:
        return f'IA5String({self.value!r})'

    def __eq__(self, other: object) -> bool: # pragma: no cover
        if not isinstance(other, IA5String):
            return NotImplemented

        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode a DER IA5 string"""

        # ASN.1 defines this type as only containing ASCII characters, but
        # some tools expecting ASN.1 allow IA5Strings to contain other
        # characters, so we leave it up to the caller to pass in a byte
        # string which has already done the appropriate encoding of any
        # non-ASCII characters.

        return cast('IA5String', value).value

    @classmethod
    def decode(cls, constructed: bool, content: bytes) -> 'IA5String':
        """Decode a DER IA5 string"""

        if constructed:
            raise ASN1DecodeError('IA5 STRING should not be constructed')

        # As noted in the encode method above, the decoded value for this
        # type is a byte string, leaving the decoding of any non-ASCII
        # characters up to the caller.

        return cls(content)


@DERTag(OBJECT_IDENTIFIER)
class ObjectIdentifier(DERType):
    """An object identifier (OID) value

       This object can be initialized from a string of dot-separated
       integer values, representing a hierarchical namespace. All OIDs
       show have at least two components, with the first being between
       0 and 2 (indicating ITU-T, ISO, or joint assignment). In cases
       where the first component is 0 or 1, the second component must
       be in the range 0 to 39 due to the way these first two components
       are encoded.

    """

    def __init__(self, value: str):
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"ObjectIdentifier('{self.value}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ObjectIdentifier): # pragma: no cover
            return NotImplemented

        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    @staticmethod
    def encode(value: object) -> bytes:
        """Encode a DER object identifier"""

        def _bytes(component: int) -> bytes:
            """Convert a single element of an OID to a DER byte string"""

            if component < 0:
                raise ASN1EncodeError('Components of object identifier must '
                                      'be greater than or equal to 0')

            result = [component & 0x7f]
            while component >= 0x80:
                component >>= 7
                result.append(0x80 | (component & 0x7f))

            return bytes(result[::-1])

        oid_value = cast('ObjectIdentifier', value)

        try:
            components = [int(c) for c in oid_value.value.split('.')]
        except ValueError:
            raise ASN1EncodeError('Component values must be '
                                  'integers') from None

        if len(components) < 2:
            raise ASN1EncodeError('Object identifiers must have at least two '
                                  'components')
        elif components[0] < 0 or components[0] > 2:
            raise ASN1EncodeError('First component of object identifier must '
                                  'be between 0 and 2')
        elif components[0] < 2 and (components[1] < 0 or components[1] > 39):
            raise ASN1EncodeError('Second component of object identifier must '
                                  'be between 0 and 39')

        components[0:2] = [components[0]*40 + components[1]]
        return b''.join(_bytes(c) for c in components)

    @classmethod
    def decode(cls, constructed: bool, content: bytes) -> 'ObjectIdentifier':
        """Decode a DER object identifier"""

        if constructed:
            raise ASN1DecodeError('OBJECT IDENTIFIER should not be '
                                  'constructed')

        if not content:
            raise ASN1DecodeError('Empty object identifier')

        b = content[0]
        components = list(divmod(b, 40)) if b < 80 else [2, b-80]

        component = 0
        for b in content[1:]:
            if b == 0x80 and component == 0:
                raise ASN1DecodeError('Invalid component')
            elif b < 0x80:
                components.append(component | b)
                component = 0
            else:
                component |= b & 0x7f
                component <<= 7

        if component:
            raise ASN1DecodeError('Incomplete component')

        return cls('.'.join(str(c) for c in components))


def der_encode(value: object) -> bytes:
    """Encode a value in DER format

       This function takes a Python value and encodes it in DER format.
       The following mapping of types is used:

       NoneType            -> NULL
       bool                -> BOOLEAN
       int                 -> INTEGER
       bytes, bytearray    -> OCTET STRING
       str                 -> UTF8 STRING
       list, tuple         -> SEQUENCE
       set, frozenset      -> SET
       BitString           -> BIT STRING
       ObjectIdentifier    -> OBJECT IDENTIFIER

       An explicitly tagged DER object can be encoded by passing in a
       TaggedDERObject which specifies the ASN.1 class, tag, and value
       to encode.

       Other types can be encoded by passing in a RawDERObject which
       specifies the ASN.1 class, tag, and raw content octets to encode.

    """

    t = type(value)
    if t in (RawDERObject, TaggedDERObject):
        value = cast(Union[RawDERObject, TaggedDERObject], value)
        identifier = value.encode_identifier()
        content = value.encode(value)
    elif t in _der_class_by_type:
        cls = _der_class_by_type[t]
        identifier = cls.identifier
        content = cls.encode(value)
    else:
        raise ASN1EncodeError(f'Cannot DER encode type {t.__name__}')

    length = len(content)
    if length < 0x80:
        len_bytes = bytes((length,))
    else:
        len_bytes = length.to_bytes((length.bit_length() + 7) // 8, 'big')
        len_bytes = bytes((0x80 | len(len_bytes),)) + len_bytes

    return identifier + len_bytes + content


def der_decode_partial(data: bytes) -> Tuple[object, int]:
    """Decode a value in DER format and return the number of bytes consumed"""

    if len(data) < 2:
        raise ASN1DecodeError('Incomplete data')

    tag = data[0]
    asn1_class, constructed, tag = tag >> 6, bool(tag & 0x20), tag & 0x1f
    offset = 1
    if tag == 0x1f:
        tag = 0
        for b in data[offset:]:
            offset += 1

            if b < 0x80:
                tag |= b
                break
            else:
                tag |= b & 0x7f
                tag <<= 7
        else:
            raise ASN1DecodeError('Incomplete tag')

    if offset >= len(data):
        raise ASN1DecodeError('Incomplete data')

    length = data[offset]
    offset += 1
    if length > 0x80:
        len_size = length & 0x7f
        length = int.from_bytes(data[offset:offset+len_size], 'big')
        offset += len_size
    elif length == 0x80:
        raise ASN1DecodeError('Indefinite length not allowed')

    end = offset + length
    content = data[offset:end]

    if end > len(data):
        raise ASN1DecodeError('Incomplete data')

    if asn1_class == UNIVERSAL and tag in _der_class_by_tag:
        cls = _der_class_by_tag[tag]
        value = cls.decode(constructed, content)
    elif constructed:
        value = TaggedDERObject(tag, der_decode(content), asn1_class)
    else:
        value = RawDERObject(tag, content, asn1_class)

    return value, end


def der_decode(data: bytes) -> object:
    """Decode a value in DER format

       This function takes a byte string in DER format and converts it
       to a corresponding set of Python objects. The following mapping
       of ASN.1 tags to Python types is used:

       NULL              -> NoneType
       BOOLEAN           -> bool
       INTEGER           -> int
       OCTET STRING      -> bytes
       UTF8 STRING       -> str
       SEQUENCE          -> tuple
       SET               -> frozenset
       BIT_STRING        -> BitString
       OBJECT IDENTIFIER -> ObjectIdentifier

       Explicitly tagged objects are returned as type TaggedDERObject,
       with fields holding the object class, tag, and tagged value.

       Other object tags are returned as type RawDERObject, with fields
       holding the object class, tag, and raw content octets.

       If partial_ok is True, this function returns a tuple of the decoded
       value and number of bytes consumed. Otherwise, all data bytes must
       be consumed and only the decoded value is returned.

    """

    value, end = der_decode_partial(data)

    if end < len(data):
        raise ASN1DecodeError('Data contains unexpected bytes at end')

    return value
