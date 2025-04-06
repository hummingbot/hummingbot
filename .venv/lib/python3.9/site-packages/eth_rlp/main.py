import sys
from typing import (
    Any,
    Dict,
    Union,
    cast,
)

from eth_utils import (
    keccak,
)
from eth_utils.toolz import (
    pipe,
)
from hexbytes import (
    HexBytes,
)
import rlp

if sys.version_info >= (3, 11):
    from typing import (
        Self,
    )
else:
    from typing_extensions import (
        Self,
    )


class HashableRLP(rlp.Serializable):  # type: ignore
    r"""
    An extension of :class:`rlp.Serializable`. In addition to the below
    functions, the class is iterable.

    Use like:

    ::

        class MyRLP(HashableRLP):
            fields = (
                ('name1', rlp.sedes.big_endian_int),
                ('name2', rlp.sedes.binary),
                etc...
            )

        my_obj = MyRLP(name2=b'\xff', name1=1)
        list(my_obj) == [1, b'\xff']
        # note that the iteration order is always in RLP-defined order
    """

    @classmethod
    def from_dict(cls, field_dict: Dict[str, Any]) -> Self:
        r"""
        In addition to the standard initialization of.

        ::

            my_obj = MyRLP(name1=1, name2=b'\xff')

        This method enables initialization with.

        ::

            my_obj = MyRLP.from_dict({'name1': 1, 'name2': b'\xff'})

        In general, the standard initialization is preferred, but
        some approaches might favor this API, like when using
        :meth:`toolz.functoolz.pipe`.

        ::

            return eth_utils.toolz.pipe(
                my_dict,
                normalize,
                validate,
                MyRLP.from_dict,
            )

        :param dict field_dict: the dictionary of values to initialize with
        :returns: the new rlp object
        :rtype: HashableRLP
        """
        return cls(**field_dict)

    @classmethod
    def from_bytes(cls, serialized_bytes: Union[bytes, bytearray]) -> Self:
        """
        Shorthand invocation for :meth:`rlp.decode` using this class.

        :param bytes serialized_bytes: the byte string to decode
        :return: the decoded object
        :rtype: HashableRLP
        """
        decoded = rlp.decode(serialized_bytes, cls)
        return cast(Self, decoded)

    def hash(self) -> HexBytes:
        """
        :returns: the hash of the encoded bytestring
        :rtype: ~hexbytes.main.HexBytes
        """
        return HexBytes(
            pipe(
                self,
                rlp.encode,
                keccak,
            )
        )

    def __iter__(self) -> Any:
        if hasattr(self, "fields"):
            return iter(getattr(self, field) for field, _ in self.fields)
        else:
            return super().__iter__()

    def as_dict(self) -> Dict[str, Any]:
        """
        Convert rlp object to a dict

        :returns: mapping of RLP field names to field values
        :rtype: dict
        """
        try:
            _as_dict = super().as_dict()
            return cast(Dict[str, Any], _as_dict)
        except AttributeError:
            _as_dict = vars(self)
            return cast(Dict[str, Any], _as_dict)
