import parsimonious


class EncodingError(Exception):
    """
    Base exception for any error that occurs during encoding.
    """


class EncodingTypeError(EncodingError):
    """
    Raised when trying to encode a python value whose type is not supported for
    the output ABI type.
    """


class IllegalValue(EncodingError):
    """
    Raised when trying to encode a python value with the correct type but with
    a value that is not considered legal for the output ABI type.

    .. code-block:: python

        fixed128x19_encoder(Decimal('NaN'))  # cannot encode NaN

    """


class ValueOutOfBounds(IllegalValue):
    """
    Raised when trying to encode a python value with the correct type but with
    a value that appears outside the range of valid values for the output ABI
    type.

    .. code-block:: python

        ufixed8x1_encoder(Decimal('25.6'))  # out of bounds

    """


class DecodingError(Exception):
    """
    Base exception for any error that occurs during decoding.
    """


class InsufficientDataBytes(DecodingError):
    """
    Raised when there are insufficient data to decode a value for a given ABI type.
    """


class NonEmptyPaddingBytes(DecodingError):
    """
    Raised when the padding bytes of an ABI value are malformed.
    """


class InvalidPointer(DecodingError):
    """
    Raised when the pointer to a value in the ABI encoding is invalid.
    """


class ParseError(parsimonious.ParseError):  # type: ignore[misc] # subclasses Any
    """
    Raised when an ABI type string cannot be parsed.
    """

    def __str__(self) -> str:
        return (
            f"Parse error at '{self.text[self.pos : self.pos + 5]}' "
            f"(column {self.column()}) in type string '{self.text}'"
        )


class ABITypeError(ValueError):
    """
    Raised when a parsed ABI type has inconsistent properties; for example,
    when trying to parse the type string ``'uint7'`` (which has a bit-width
    that is not congruent with zero modulo eight).
    """


class PredicateMappingError(Exception):
    """
    Raised when an error occurs in a registry's internal mapping.
    """


class NoEntriesFound(ValueError, PredicateMappingError):
    """
    Raised when no registration is found for a type string in a registry's
    internal mapping.

    .. warning::

        In a future version of ``eth-abi``, this error class will no longer
        inherit from ``ValueError``.
    """


class MultipleEntriesFound(ValueError, PredicateMappingError):
    """
    Raised when multiple registrations are found for a type string in a
    registry's internal mapping.  This error is non-recoverable and indicates
    that a registry was configured incorrectly.  Registrations are expected to
    cover completely distinct ranges of type strings.

    .. warning::

        In a future version of ``eth-abi``, this error class will no longer
        inherit from ``ValueError``.
    """
